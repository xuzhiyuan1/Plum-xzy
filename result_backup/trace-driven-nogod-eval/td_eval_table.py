#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# trace-driven(无oracle) 预测收益「总体性能指标评估表」
# 口径: 合并均值(mean-of-means), 与 model-based(+17%)脚本完全一致
# 范围: policy=2(Plum), N=3..6
import sys, pandas as pd
CSV = sys.argv[1] if len(sys.argv)>1 else "results.csv"
NSET = [3,4,5,6]
df = pd.read_csv(CSV); df.columns = df.columns.str.strip()
df['policy']=df['policy'].astype(int); df['nclient']=df['nclient'].astype(int); df['mlpred']=df['mlpred'].astype(int)
df = df[(df['policy']==2) & (df['nclient'].isin(NSET))].copy()
df['ML_Prediction'] = df['mlpred'].map({0:'w/o ML Pred (0)', 1:'w/ ML Pred (1)'})
summary = df.groupby('ML_Prediction')[['avg_thp','qoe']].mean()

t0=df[df['mlpred']==0]['avg_thp'].mean(); t1=df[df['mlpred']==1]['avg_thp'].mean()
q0=df[df['mlpred']==0]['qoe'].mean();     q1=df[df['mlpred']==1]['qoe'].mean()
pct_thp=(t1-t0)/t0*100; pct_qoe=(q1-q0)/q0*100

print("="*50)
print("                总体性能指标评估表")
print("="*50)
print()
print(summary.to_string(float_format=lambda x: f"{x:.4f}"))
print("-"*50)
print(f"吞吐量 (avg_thp) 提升比例：{pct_thp:+.2f}%")
print(f"体验质量 (qoe) 提升比例：  {pct_qoe:+.2f}%")
print("="*50)
print(f"\n[口径] trace-driven无oracle; policy=2(Plum); mlpred 0 vs 1; "
      f"nclient={NSET}; simTime=600; 每档 N×seed 全聚合(合并均值, 同 model-based)")
print(f"[样本] w/o={len(df[df['mlpred']==0])} runs, w/={len(df[df['mlpred']==1])} runs")
