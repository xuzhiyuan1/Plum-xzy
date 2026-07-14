# trace-driven(无上帝视角) 预测收益评估 — N=3~6

## 结果（合并均值口径，与 model-based(+17%)同一算法）
| 指标 | Plum 无预测 | Plum+Transformer | 提升 |
|---|---|---|---|
| avg_thp | 1143854.18 | 1323338.98 | **+15.69%** |
| QoE | 0.2933 | 0.3468 | **+18.24%** |

40 vs 40 runs (policy=2, N∈{3,4,5,6}, 10 seed, simTime=600)。

## 口径说明
合并均值 = 所有"有预测"case 的均值 减 所有"无预测"case 的均值，再除以无预测均值
(= model-based plot_channel_model_segwifi.py 第30-36行同款; 非逐case百分比平均)。

## 无上帝视角配方
NS3原生WiFi(802.11p)+AR(1)距离调制(meanDist=8/sigma=0.6/rho=0.9,校准至真实
restaurant trace的CoV=0.37); Plum(policy=2)用BBR自估计分配; Transformer(mlpred=1)
只吃系统观测(融合权重bug已修0.6/0.4); 决策链不接触任何真实trace值。见 RECIPE.txt。

## 文件
- td_eval_table.py: 生成上表(改CSV路径可复用)
- results_n3-6.csv: 本表所用数据(policy2, N3-6)
- results_full_allN.csv: 全量(N3-8, 三条件)原始数据
- eval_table.txt: 表输出快照
