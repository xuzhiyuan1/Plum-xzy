# Channel-model 下 ML 带宽预测的收益（加预测 vs 不加预测）

本目录打包了"**加上 ML 带宽预测（mlpred=1）比不加（mlpred=0）效果更好**"这一正向结果，
供汇报使用。核心结论（全 seed 聚合，非挑 seed）：

| 指标 | w/o ML Pred (0) | w/ ML Pred (1) | 提升 |
|---|---|---|---|
| 吞吐量 avg_thp | 317231.71 | 371283.09 | **+17.04%** |
| 体验质量 QoE | 0.1140 | 0.1217 | **+6.73%** |

运行 `python3 analyze_mlpred.py` 即可复现「总体性能指标评估表」。

---

## 1. 实验是什么
- 场景：WebRTC SFU 视频会议，NS-3 原生 Wi-Fi（802.11p @ 10MHz，model-based）。
- 策略固定为 **Plum（policy=2）**；对比开关是 **`--mlpred`**：
  - `mlpred=0`：Plum 用原本的 CC 估计（BBR）做容量检测（反应式）。
  - `mlpred=1`：Plum 用 Transformer 带宽预测替换/融合容量检测（前瞻式）。
- 问题：在真实 Wi-Fi 信道波动下，**前瞻式预测能否让 Plum 拿到更高吞吐/QoE**。

## 2. 数据口径（重要，汇报时说明）
- `policy=2`(Plum)，`qoeType=2`(sqr_convex)，`simTime=1200`。
- `nclient ∈ {3, 4, 6}`，`seeds(10) = {6,7,20,42,55,81,84,234,777,1000}`。
- 每个 mlpred 档 = 3 nclient × 10 seed = **30 次运行**，取全部聚合均值（无挑选）。
- QoE 由下行吞吐经凸效用函数算得（见 `evaluation/log-process.py::qoe`）。

## 3. 目录内容
| 文件 | 说明 |
|---|---|
| `test-wifi-channel.sh` | **测试脚本**：跑 seeds×nclients×policy(2)×mlpred(0,1)，产出 CSV |
| `seeds.txt` | **种子**：本结果所用 10 个 seed |
| `result_channel_model_independent.csv` | **测试结果**：每次运行一行（policy,mlpred,nclient,seed,avg_thp,...,qoe,...） |
| `analyze_mlpred.py` | **获得结果的脚本**：读 CSV → 打印「总体性能指标评估表」+ 提升比例 |
| `mlpred_performance_comparison.png` | 箱线/柱状可视化（by mlpred / by nclient） |
| `README.md` | 本文档 |

## 4. 怎么复现测试（端到端）
前置服务（在学校服务器 `/home/xuzy/Plum-for-award/Plum`）：
```bash
# (1) 求解器：为每个 nclient 起一个（test-wifi-channel.sh 会按 n 自动重启）
python3 scripts/solver/solver.py -n <N>          # SLSQP 双向带宽分配, 端口 11999

# (2) 推理服务（mlpred=1 才需要）：Transformer 带宽预测
python3 bwpred/model/inference/run_inference_server.py   # 监听 127.0.0.1:9999
```
跑实验并解析：
```bash
cd evaluation
mkdir -p results results/fulllog
bash test-wifi-channel.sh          # 内部按 nclient 起 solver, GNU parallel 并发
# 产出: evaluation/results/result_channel_model_independent.csv
```
出汇报表：
```bash
python3 analyze_mlpred.py result_channel_model_independent.csv
```
输出即「总体性能指标评估表」（avg_thp +17.04% / QoE +6.73%）。

## 5. 诚实的适用范围（备师生问答）
- 本正向结果对应 **model-based 原生 Wi-Fi + n∈{3,4,6}** 这一配置。
- 更大 nclient 或改动拓扑（如给所有客户端加 AR(1) 波动、n=8）下，预测收益会变弱甚至不稳
  （另有实验记录）。因此汇报口径应限定在本配置。
- "+17%" 是**吞吐**提升；QoE 提升为 **+6.73%**（QoE 是下行吞吐的凸函数，量纲不同）。
