#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Green-PLUM 能耗感知双向带宽分配 — 研究套件 v2
按 PPT 大纲: U=(1-rho)mean(Q)+rho*min(Q) - sum_i lambda_i*E_i(u,d)_norm
产出3张期刊级图 + 多seed指标: (A)代表场景时序 (B)电池紧张度sweep (C)lambda-Pareto
参数来源见 ENERGY_REFERENCES.md
"""
import os, glob, json
import numpy as np
from scipy.optimize import minimize

P = dict(
    # --- 网络能耗: E_bit = a/Th + b (nJ/bit), TX/RX不对称 [WiFi energy-per-bit 模型, 2022复用; 新标准实验2025] ---
    ebit_a=305.3, ebit_b=13.1, tx_asym=1.3,
    # --- 编解码(现代手机=硬件编解码) [Benmoussa JSA'21; IEEE'21 285设备解码; Herglotz'22 编码能耗建模] ---
    Penc0=0.8, uref=2.0, t_enc=1.2,   # 硬编 ~0.8W @2Mbps, 超线性
    Pdec0=0.5, dref=6.0,              # 硬解 ~0.5W @6Mbps
    # --- 基础功耗(屏幕+摄像头+系统, 分配省不掉) [MacMillan IMC'21: audio-only省50% => base≈整机一半] ---
    Pbase=2.0,
    Pref=4.0,   # 归一化锚点: IMC'21 整机视频会议 ~4W (1h耗2600mAh的40%)
    dhalf=3.0, umin=0.3, umax=4.0, dmax=20.0,
    rho=0.5, k_lambda=1.5, m_lambda=2.0,
    # --- 热模型(RC/牛顿冷却) [SciReports'23 视频通话温度实测~40C+; 手机表面节流阈值~41-43C] ---
    T_amb=25.0, R_th=4.5, tau_T=360.0, T_throttle=41.0, T_release=39.0, throttle_ufrac=0.4,
)

def load_traces(tracedir):
    T=[]
    for f in sorted(glob.glob(os.path.join(tracedir,'*.trace'))):
        bw=[float(l.split()[0].replace('Mbps','')) for l in open(f) if l.strip() and 'Mbps' in l]
        if bw: T.append(np.array(bw))
    return T

def qoe(eff_d,p): return eff_d/(eff_d+p['dhalf'])
def energy_W(u,d,R,p):
    # R 保留签名兼容(未用); 模型锚定2020+文献, 典型点(u=2,d=6)≈3.7W ≈ IMC'21整机4W
    thr=max(u+d,0.1)
    ebit=(p['ebit_a']/thr+p['ebit_b'])*1e-9          # J/bit
    net=(p['tx_asym']*u + d)*1e6*ebit                 # W
    enc=p['Penc0']*(max(u,1e-6)/p['uref'])**p['t_enc']
    dec=p['Pdec0']*(d/p['dref'])
    return p['Pbase']+net+enc+dec

def solve_alloc(policy,C,lam,alive,p,k_lambda=None,umax_eff=None):
    n=len(C); idx=[i for i in range(n) if alive[i]]; m=len(idx)
    if m==0: return np.zeros(n),np.zeros(n)
    UM = umax_eff if umax_eff is not None else np.full(n,p['umax'])
    if policy=='vanilla':
        u=np.zeros(n); d=np.zeros(n)
        for i in idx:
            h=min(C[i]/2,UM[i]); u[i]=max(p['umin'],h); d[i]=max(0,C[i]-u[i])
        return u,d
    kl=p['k_lambda'] if k_lambda is None else k_lambda
    def unpack(x):
        uu=np.zeros(n);dd=np.zeros(n)
        for j,i in enumerate(idx): uu[i]=x[j];dd[i]=x[m+j]
        return uu,dd
    def negU(x):
        uu,dd=unpack(x); Q=[]
        for i in idx:
            ou=sum(uu[k] for k in idx if k!=i); Q.append(qoe(min(dd[i],ou),p))
        Q=np.array(Q); util=(1-p['rho'])*Q.mean()+p['rho']*Q.min()
        if policy=='green':
            util-=sum(lam[i]*(energy_W(uu[i],dd[i],25.0,p)-p['Pbase'])/p['Pref'] for i in idx)
        return -util
    cons=[]
    for j,i in enumerate(idx):
        cons.append({'type':'ineq','fun':lambda x,j=j,i=i:C[i]-x[j]-x[m+j]})
        cons.append({'type':'ineq','fun':lambda x,j=j,idx=idx,m=m:sum(x[jj] for jj,kk in enumerate(idx) if kk!=idx[j])-x[m+j]})
    bnds=[(p['umin'],max(p['umin'],UM[i])) for i in idx]+[(0,p['dmax'])]*m
    x0=np.array([min(max(p['umin'],UM[i]),max(p['umin'],C[i]*0.4)) for i in idx]+[min(p['dmax'],max(0.,C[i]*0.5)) for i in idx])
    r=minimize(negU,x0,method='SLSQP',bounds=bnds,constraints=cons,options={'maxiter':40,'ftol':1e-4})
    return unpack(r.x)

def make_clients(rng, batt_scale=1.0):
    base=[('phone-low',12,0.30),('phone-low2',12,0.27),('phone-mid',12,0.60),
          ('phone-mid2',12,0.65),('laptop',45,0.80),('plugged',45,0.90)]
    cl=[]
    for i,(nm,wh,soc) in enumerate(base):
        charging = 1 if nm=='plugged' else 0
        cmean=float(rng.uniform(16,26))
        cl.append(dict(name=nm, batt_Wh=wh*batt_scale, soc0=soc, charging=charging, cmean=cmean))
    return cl

def run_episode(policy,clients,traces,p,T_steps,dt,rng,k_lambda=None):
    n=len(clients); tr=[traces[rng.integers(len(traces))] for _ in range(n)]
    SoC=np.array([c['soc0'] for c in clients],float); capJ=np.array([c['batt_Wh']*3600 for c in clients])
    charging=np.array([c['charging'] for c in clients]); alive=np.array([True]*n)
    hs=np.zeros((T_steps,n)); hq=np.zeros((T_steps,n)); tot_e=0.0
    Temp=np.full(n,p['T_amb']); throttled=np.array([False]*n); ht=np.zeros((T_steps,n)); thr_time=np.zeros(n)
    for s in range(T_steps):
        C=np.array([max(0.5,float(tr[i][s%len(tr[i])])) for i in range(n)])
        lam=np.array([0. if charging[i] else p['k_lambda' if k_lambda is None else 'k_lambda']*(1-SoC[i])**p['m_lambda'] for i in range(n)])
        if k_lambda is not None:
            lam=np.array([0. if charging[i] else k_lambda*(1-SoC[i])**p['m_lambda'] for i in range(n)])
        umax_eff=np.array([p['umax']*(p['throttle_ufrac'] if throttled[i] else 1.0) for i in range(n)])
        u,d=solve_alloc(policy,C,lam,alive,p,k_lambda,umax_eff)
        for i in range(n):
            if not alive[i]: continue
            ou=sum(u[k] for k in range(n) if k!=i and alive[k]); hq[s,i]=qoe(min(d[i],ou),p)
            Ew=energy_W(u[i],d[i],25.0,p); tot_e+=Ew*dt
            # RC 热模型 + 节流滞回
            Temp[i]+= dt/p['tau_T']*(p['T_amb']+p['R_th']*Ew-Temp[i])
            if Temp[i]>=p['T_throttle']: throttled[i]=True
            elif Temp[i]<=p['T_release']: throttled[i]=False
            if throttled[i]: thr_time[i]+=dt
            ht[s,i]=Temp[i]
            if not charging[i]:
                SoC[i]-=Ew*dt/capJ[i]
                if SoC[i]<=0: SoC[i]=0; alive[i]=False
            hs[s,i]=SoC[i]*100
    return hs,hq,tot_e,ht,thr_time

def ep_metrics(hs,hq,dt):
    eff=hq.sum(axis=0)*dt
    fd=next((s*dt/60 for s in range(hs.shape[0]) if (hs[s]<=0).any()),None)
    ae=int((hs[-1]>0).sum())
    return dict(effQoE=float(eff.sum()), first_death=fd, alive_end=ae)

if __name__=='__main__':
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    TD=os.path.expanduser('~/Plum-for-award/Plum/bwpred/traces/restaurant'); traces=load_traces(TD)
    T_min=60; dt=20; T_steps=T_min*60//dt; SEEDS=range(4); POL=['vanilla','plum','green']
    col={'vanilla':'gray','plum':'red','green':'green'}
    OUT={}

    # ===== A: 代表场景(batt_scale=0.7 电池偏紧) 单seed 时序图 =====
    rng=np.random.default_rng(2); cl=make_clients(rng,0.7)
    tsdata={}; tsheat={}
    for pol in POL:
        hs,hq,_,ht,tt_=run_episode(pol,cl,traces,P,T_steps,dt,np.random.default_rng(2)); tsdata[pol]=(hs,hq); tsheat[pol]=(ht,tt_)
    tt=np.arange(T_steps)*dt/60
    fig,ax1=plt.subplots(figsize=(9,5)); ax2=ax1.twinx()
    for pol in POL:
        hs,hq=tsdata[pol]
        ax1.plot(tt,hs.mean(1),color=col[pol],lw=2,label=f'{pol} Battery')
        ax2.plot(tt,[hq[s][hs[s]>0].mean() if (hs[s]>0).any() else 0 for s in range(T_steps)],'--',color=col[pol],alpha=.7,label=f'{pol} QoE')
    ax1.set_xlabel('Meeting Duration (min)');ax1.set_ylabel('Avg Battery SoC (%)');ax2.set_ylabel('Avg QoE')
    ax1.set_ylim(0,100);ax2.set_ylim(0,1);ax1.legend(loc='lower left',fontsize=8);ax2.legend(loc='upper right',fontsize=8)
    plt.title('(A) Battery & QoE over meeting (battery-constrained)');plt.tight_layout();plt.savefig('fig_A_timeseries.png',dpi=120);plt.close()
    print('[A done]', {pol:ep_metrics(*tsdata[pol],dt) for pol in POL}, flush=True)
    print('[A heat] peakT/throttle_min:', {pol:(round(float(tsheat[pol][0].max()),1), round(float(tsheat[pol][1].sum())/60,1)) for pol in POL}, flush=True)
    figh,axh=plt.subplots(figsize=(9,4.5))
    for pol in POL:
        axh.plot(tt, tsheat[pol][0].max(axis=1), color=col[pol], label=f'{pol} hottest device')
    axh.axhline(P['T_throttle'],ls=':',color='k',label='throttle 41C')
    axh.set_xlabel('Meeting Duration (min)'); axh.set_ylabel('Device temperature (C)')
    axh.legend(fontsize=8); axh.grid(alpha=.3); plt.title('(E) Thermal: hottest device temperature')
    plt.tight_layout(); plt.savefig('fig_E_thermal.png',dpi=120); plt.close()

    # ===== B: 电池紧张度 sweep (多seed) =====
    scales=[0.4,0.6,0.8,1.0,1.3]
    Bres={pol:{'alive':[],'eff':[]} for pol in POL}
    for sc in scales:
        for pol in POL:
            ae=[];ef=[]
            for sd in SEEDS:
                rng=np.random.default_rng(sd); cl=make_clients(rng,sc)
                hs,hq,_,ht,tt_=run_episode(pol,cl,traces,P,T_steps,dt,np.random.default_rng(100+sd)); m=ep_metrics(hs,hq,dt)
                ae.append(m['alive_end']); ef.append(m['effQoE'])
            Bres[pol]['alive'].append(np.mean(ae)); Bres[pol]['eff'].append(np.mean(ef))
    fig,(axa,axb)=plt.subplots(1,2,figsize=(12,4.5))
    for pol in POL:
        axa.plot(scales,Bres[pol]['alive'],'-o',color=col[pol],label=pol)
        axb.plot(scales,Bres[pol]['eff'],'-o',color=col[pol],label=pol)
    axa.set_xlabel('Battery scale (smaller = tighter)');axa.set_ylabel('# devices alive at end (/6, mean)');axa.set_title('(B1) Survival vs battery tightness');axa.legend();axa.grid(alpha=.3)
    axb.set_xlabel('Battery scale');axb.set_ylabel('Effective QoE integral (mean)');axb.set_title('(B2) Effective QoE vs battery tightness');axb.legend();axb.grid(alpha=.3)
    plt.tight_layout();plt.savefig('fig_B_severity_sweep.png',dpi=120);plt.close()
    print('[B done] scales',scales,'green_alive',[round(x,1) for x in Bres['green']['alive']],'plum_alive',[round(x,1) for x in Bres['plum']['alive']],'vanilla_alive',[round(x,1) for x in Bres['vanilla']['alive']], flush=True)
    print('[B eff] green',[round(x) for x in Bres['green']['eff']],'plum',[round(x) for x in Bres['plum']['eff']], flush=True)

    # ===== C: lambda-Pareto (green扫k_lambda: 从0(=plum)到激进) =====
    kls=[0,0.5,1.0,1.5,2.5,4.0]; Pareto={'k':[],'eff':[],'energy':[],'alive':[]}
    for kl in kls:
        ef=[];en=[];al=[]
        for sd in SEEDS:
            rng=np.random.default_rng(sd); cl=make_clients(rng,0.7)
            pol='plum' if kl==0 else 'green'
            hs,hq,te,ht,tt_=run_episode(pol,cl,traces,P,T_steps,dt,np.random.default_rng(200+sd),k_lambda=kl); m=ep_metrics(hs,hq,dt)
            ef.append(m['effQoE']); en.append(te); al.append(m['alive_end'])
        Pareto['k'].append(kl);Pareto['eff'].append(np.mean(ef));Pareto['energy'].append(np.mean(en));Pareto['alive'].append(np.mean(al))
    fig,ax=plt.subplots(figsize=(7,5))
    sc=ax.scatter(Pareto['energy'],Pareto['eff'],c=Pareto['k'],cmap='viridis',s=80)
    for i,kl in enumerate(kls): ax.annotate(f'λk={kl}',(Pareto['energy'][i],Pareto['eff'][i]),fontsize=7)
    ax.set_xlabel('Total energy (J, mean)');ax.set_ylabel('Effective QoE integral',);ax.set_title('(C) Green-PLUM energy vs effective-QoE Pareto');plt.colorbar(sc,label='λ weight k');plt.tight_layout();plt.savefig('fig_C_pareto.png',dpi=120);plt.close()

    OUT=dict(A_timeseries={pol:ep_metrics(*tsdata[pol],dt) for pol in POL},
             B_severity={'scales':scales,**{pol:Bres[pol] for pol in POL}},
             C_pareto=Pareto)
    json.dump(OUT,open('study_results.json','w'),indent=2,default=str)
    print("=== A 代表场景(batt0.7) ===")
    for pol in POL: print(f"  {pol}: {OUT['A_timeseries'][pol]}")
    print("=== B 存活 vs 紧张度 (scales="+str(scales)+") ===")
    for pol in POL: print(f"  {pol} alive: {[round(x,1) for x in Bres[pol]['alive']]}")
    print("  green eff:",[round(x) for x in Bres['green']['eff']]); print("  plum  eff:",[round(x) for x in Bres['plum']['eff']])
    print("saved: fig_A_timeseries.png fig_B_severity_sweep.png fig_C_pareto.png study_results.json")
