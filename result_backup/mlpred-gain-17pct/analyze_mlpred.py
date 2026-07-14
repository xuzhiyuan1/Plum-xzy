#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取 channel-model mlpred 消融结果, 输出「总体性能指标评估表」
(加预测 mlpred=1 vs 不加预测 mlpred=0 的 avg_thp / qoe 对比与提升比例)。
用法: python3 analyze_mlpred.py [result_channel_model_independent.csv]
"""
import sys
import pandas as pd

DATA = sys.argv[1] if len(sys.argv) > 1 else "result_channel_model_independent.csv"

df = pd.read_csv(DATA)
df.columns = df.columns.str.strip()
df["ML_Prediction"] = df["mlpred"].map({0: "w/o ML Pred (0)", 1: "w/ ML Pred (1)"})

summary = df.groupby("ML_Prediction")[["avg_thp", "qoe"]].mean()

thp0 = df[df["mlpred"] == 0]["avg_thp"].mean()
thp1 = df[df["mlpred"] == 1]["avg_thp"].mean()
qoe0 = df[df["mlpred"] == 0]["qoe"].mean()
qoe1 = df[df["mlpred"] == 1]["qoe"].mean()
pct_thp = (thp1 - thp0) / thp0 * 100
pct_qoe = (qoe1 - qoe0) / qoe0 * 100

print("=" * 50)
print("                总体性能指标评估表")
print("=" * 50)
print()
print(summary.to_string(float_format=lambda x: f"{x:.4f}"))
print("-" * 50)
print(f"吞吐量 (avg_thp) 提升比例：{pct_thp:+.2f}%")
print(f"体验质量 (qoe) 提升比例：  {pct_qoe:+.2f}%")
print("=" * 50)

# 附: 数据覆盖范围(便于汇报时说明口径,非挑 seed)
seeds = sorted(df["seed"].unique(), key=int)
ns = sorted(df["nclient"].unique(), key=int)
print(f"\n[口径] policy=2(Plum), qoeType=2, simTime=1200; "
      f"nclient={ns}; seeds({len(seeds)})={seeds}; 每组 n×seed 全聚合")
