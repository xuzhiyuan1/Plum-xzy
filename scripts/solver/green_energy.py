#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Green-PLUM in-loop green/thermal state for solver.py (A2 closed loop).
Only engaged for green-format requests (legacy requests untouched).
Config via env GREEN_CFG (json path); params mirror green/green_plum_study.py."""
import json, os, time as _time
import numpy as np
import scipy.optimize as _opt

DEF = dict(
    ebit_a=305.3, ebit_b=13.1, tx_asym=1.3,
    Penc0=0.8, uref=2.0, t_enc=1.2, Pdec0=0.5, dref=6.0,
    Pbase=2.0, Pref=4.0,
    T_amb=25.0, R_th=4.5, tau_T=360.0, T_throttle=41.0, T_release=39.0,
    throttle_ufrac=0.4, k_lambda=1.5, m_lambda=2.0,
    umax_mbps=4.0, dmax_mbps=20.0, batt_scale=0.7, time_accel=3.0,
)
DEF_PROFILES = [
    dict(batt_Wh=12, soc0=0.30, charging=0), dict(batt_Wh=12, soc0=0.27, charging=0),
    dict(batt_Wh=12, soc0=0.60, charging=0), dict(batt_Wh=12, soc0=0.65, charging=0),
    dict(batt_Wh=45, soc0=0.80, charging=0), dict(batt_Wh=45, soc0=0.90, charging=1),
]

class GreenState(object):
    def __init__(self, N, run_id=0):
        self.p = dict(DEF)
        cfg = {}
        cfgp = os.environ.get('GREEN_CFG')
        if cfgp and os.path.exists(cfgp):
            cfg = json.load(open(cfgp))
        for k, v in cfg.items():
            if k not in ('profiles', 'csv_dir'):
                self.p[k] = v
        profs = cfg.get('profiles') or DEF_PROFILES
        self.N = N
        self.batt_J = np.array([profs[i % len(profs)]['batt_Wh'] * 3600.0 * self.p['batt_scale'] for i in range(N)])
        self.soc = np.array([profs[i % len(profs)]['soc0'] for i in range(N)], float)
        self.charging = np.array([profs[i % len(profs)].get('charging', 0) for i in range(N)])
        self.temp = np.full(N, self.p['T_amb'])
        self.throttled = np.zeros(N, bool)
        self.alive = np.ones(N, bool)
        self.last_t = None
        d = cfg.get('csv_dir') or '/tmp/green_logs'
        os.makedirs(d, exist_ok=True)
        fn = os.path.join(d, 'green_run%d_n%d_%d.csv' % (int(run_id), N, int(_time.time() * 1000) % 1000000))
        self.csv = open(fn, 'w', buffering=1)
        self.csv.write('sim_t,client,soc,temp,throttled,alive,ul_kbps,dl_kbps,power_W,lam\n')

    def energy_W(self, u, d):  # u,d Mbps
        p = self.p
        thr = max(u + d, 0.1)
        ebit = (p['ebit_a'] / thr + p['ebit_b']) * 1e-9
        net = (p['tx_asym'] * u + d) * 1e6 * ebit
        enc = p['Penc0'] * (max(u, 1e-6) / p['uref']) ** p['t_enc']
        dec = p['Pdec0'] * (d / p['dref'])
        return p['Pbase'] + net + enc + dec

    def lam(self):
        return np.where(self.charging > 0, 0.0, self.p['k_lambda'] * (1 - self.soc) ** self.p['m_lambda'])

    def step(self, sim_t, ul_kbps, dl_kbps):
        if self.last_t is None:
            self.last_t = sim_t
            return
        dt = (sim_t - self.last_t) * self.p['time_accel']
        self.last_t = sim_t
        if dt <= 0:
            return
        lamv = self.lam()
        for i in range(self.N):
            u = min(ul_kbps[i] / 1000.0, self.p['umax_mbps'])   # clamp: pacing 虚高, 限进模型有效域
            d = min(dl_kbps[i] / 1000.0, self.p['dmax_mbps'])
            P = self.energy_W(u, d) if self.alive[i] else 0.15
            self.temp[i] += dt / self.p['tau_T'] * (self.p['T_amb'] + self.p['R_th'] * P - self.temp[i])
            if self.temp[i] >= self.p['T_throttle']:
                self.throttled[i] = True
            elif self.temp[i] <= self.p['T_release']:
                self.throttled[i] = False
            if self.alive[i] and not self.charging[i]:
                self.soc[i] -= P * dt / self.batt_J[i]
                if self.soc[i] <= 0:
                    self.soc[i] = 0.0
                    self.alive[i] = False
            self.csv.write('%.1f,%d,%.4f,%.2f,%d,%d,%.1f,%.1f,%.3f,%.3f\n' % (
                sim_t, i, self.soc[i], self.temp[i], int(self.throttled[i]), int(self.alive[i]),
                ul_kbps[i], dl_kbps[i], P, lamv[i]))

    def ulcap_kbps(self):
        p = self.p
        cap = np.full(self.N, p['umax_mbps'] * 1000.0)
        cap[self.throttled] = p['umax_mbps'] * 1000.0 * p['throttle_ufrac']
        cap[~self.alive] = 1.0
        return cap

    def solve_green(self, B, params, utility_fn):
        """dl allocation maximizing PLUM utility minus lambda-weighted energy. B kbps."""
        N = self.N
        lamv = self.lam()
        p = self.p
        B_ul_max = params[1] / params[5]
        def obj(x):
            base = utility_fn(x, params)
            en = 0.0
            for i in range(N):
                if not self.alive[i]:
                    continue
                u = min(max(min(B[i] - x[i], B_ul_max), 0.0) / 1000.0, p['umax_mbps'])
                d = min(max(x[i], 0.0) / 1000.0, p['dmax_mbps'])
                en += lamv[i] * (self.energy_W(u, d) - p['Pbase']) / p['Pref']
            return base + en
        cons = [{'type': 'ineq', 'fun': lambda x: np.sum(np.minimum(B - x, B_ul_max * np.ones(N))) - np.max(np.minimum(B, B_ul_max * np.ones(N) + x))}]
        bnds = [(0.0, (min(B[i], params[1]) if self.alive[i] else 1.0)) for i in range(N)]
        r = _opt.minimize(obj, x0=np.minimum(np.ones(N) * params[7], np.array([b[1] for b in bnds])),
                          constraints=tuple(cons), bounds=tuple(bnds), method='SLSQP',
                          options={'maxiter': 60, 'ftol': 1e-4})
        # [v3] lambda-driven UL energy budget: uplink is the expensive direction (tx asym +
        # superlinear encode) and ns-3 couples ul = C - dl, so shrinking dl alone RAISES ul.
        # Cap uplink explicitly: umax/(1+2*lambda), gentle for healthy, ~2.5x cut when drained.
        base_cap = self.ulcap_kbps()
        e_cap = np.maximum(300.0, np.minimum(base_cap, self.p['umax_mbps'] * 1000.0 / (1.0 + 2.0 * lamv)))
        e_cap[~self.alive] = 1.0
        return np.clip(r.x, 0.0, None), e_cap
