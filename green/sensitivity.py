#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 参数敏感性: 电池紧张场景下, 每个关键能耗参数 x{0.5..1.5}, 验证 green 保连接优势鲁棒
import os, sys, copy, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from green_plum_study import P as P0, make_clients, run_episode, ep_metrics, load_traces
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

TD=os.path.expanduser('~/Plum-for-award/Plum/bwpred/traces/restaurant'); traces=load_traces(TD)
dt=20; T_steps=60*60//dt; SEEDS=range(5); BSCALE=0.5  # 电池紧张
VARY=['Penc0','Pdec0','ebit_a','tx_asym','t_enc','k_lambda','Pbase']
FACTORS=[0.5,0.75,1.0,1.25,1.5]

def run_point(P, pol):
    al=[]; ef=[]
    for sd in SEEDS:
        rng=np.random.default_rng(sd); cl=make_clients(rng,BSCALE)
        hs,hq,*_=run_episode(pol,cl,traces,P,T_steps,dt,np.random.default_rng(300+sd))
        m=ep_metrics(hs,hq,dt); al.append(m['alive_end']); ef.append(m['effQoE'])
    return np.mean(al), np.mean(ef)

res={}
for param in VARY:
    res[param]={'f':FACTORS,'green_alive':[],'plum_alive':[],'green_eff':[],'plum_eff':[]}
    for f in FACTORS:
        P=copy.deepcopy(P0); P[param]=P0[param]*f
        ga,ge=run_point(P,'green'); pa,pe=run_point(P,'plum')
        res[param]['green_alive'].append(ga); res[param]['plum_alive'].append(pa)
        res[param]['green_eff'].append(ge); res[param]['plum_eff'].append(pe)
    print(f"[{param}] green_alive={[round(x,1) for x in res[param]['green_alive']]} plum_alive={[round(x,1) for x in res[param]['plum_alive']]}", flush=True)

# 图: 每个参数一条子图, green vs plum 存活 across factor
fig,axes=plt.subplots(2,4,figsize=(18,8)); axes=axes.flatten()
for i,param in enumerate(VARY):
    ax=axes[i]
    ax.plot(FACTORS,res[param]['green_alive'],'-o',color='green',label='Green-PLUM')
    ax.plot(FACTORS,res[param]['plum_alive'],'-o',color='red',label='PLUM')
    ax.set_title(f'{param} sensitivity'); ax.set_xlabel(f'{param} x factor'); ax.set_ylabel('# alive at end /6')
    ax.set_ylim(0,6.5); ax.grid(alpha=.3); ax.legend(fontsize=7)
axes[-1].axis('off')
plt.suptitle('Green-PLUM survival robustness to energy-param uncertainty (battery-tight, 5seed)')
plt.tight_layout(); plt.savefig('fig_D_sensitivity.png',dpi=110); plt.close()
json.dump(res, open('sensitivity_results.json','w'), indent=2, default=str)
# 汇总: green 存活优势 = green_alive - plum_alive, 是否恒正
print("=== green 存活优势 (green_alive - plum_alive), 应恒正 ===")
allpos=True
for param in VARY:
    adv=[round(g-p,1) for g,p in zip(res[param]['green_alive'],res[param]['plum_alive'])]
    print(f"  {param}: {adv}")
    if min(adv)<=0: allpos=False
print("green 存活优势对所有参数扰动恒正?", allpos)
print("saved fig_D_sensitivity.png")
