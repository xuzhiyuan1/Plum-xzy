#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 结果分析: 读本目录结果 CSV, 过滤 policy=2(Plum) & N∈{3,4,5,6},
# 打印「总体性能指标评估表」(合并均值口径, 与 model-based +17% 脚本一致)
# 用法: python3 eval_table.py [某个.csv]   (不给则自动识别本目录结果CSV)
import sys, os, glob
import pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
NSET = [3, 4, 5, 6]

def find_csv():
    p = os.path.join(here, "results.csv")
    if os.path.exists(p):
        return p
    for c in sorted(glob.glob(os.path.join(here, "*.csv"))):
        if "n3-6" in os.path.basename(c):
            continue
        try:
            h = open(c).readline()
            if all(k in h for k in ("avg_thp", "qoe", "mlpred", "nclient")):
                return c
        except Exception:
            pass
    raise SystemExit("未找到合适的结果CSV")

CSV = sys.argv[1] if len(sys.argv) > 1 else find_csv()
df = pd.read_csv(CSV); df.columns = df.columns.str.strip()
for c in ("policy", "nclient", "mlpred"):
    df[c] = df[c].astype(int)
df = df[(df["policy"] == 2) & (df["nclient"].isin(NSET))].copy()
df["ML_Prediction"] = df["mlpred"].map({0: "w/o ML Pred (0)", 1: "w/ ML Pred (1)"})
summary = df.groupby("ML_Prediction")[["avg_thp", "qoe"]].mean()
t0 = df[df.mlpred == 0].avg_thp.mean(); t1 = df[df.mlpred == 1].avg_thp.mean()
q0 = df[df.mlpred == 0].qoe.mean();     q1 = df[df.mlpred == 1].qoe.mean()
print("=" * 50)
print("                总体性能指标评估表")
print("=" * 50); print()
print(summary.to_string(float_format=lambda x: f"{x:.4f}"))
print("-" * 50)
print(f"吞吐量 (avg_thp) 提升比例：{(t1-t0)/t0*100:+.2f}%")
print(f"体验质量 (qoe) 提升比例：  {(q1-q0)/q0*100:+.2f}%")
print("=" * 50)
ns = sorted(df.nclient.unique())
print(f"\n[数据源] {os.path.basename(CSV)}")
print(f"[口径] policy=2(Plum); mlpred 0 vs 1; N={ns}(本数据存在的N∈3~6); 合并均值(mean-of-means); "
      f"w/o={len(df[df.mlpred==0])} runs, w/={len(df[df.mlpred==1])} runs")
