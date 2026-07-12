# Plum 重点实验备份总览 (result_backup)

本文件夹用于**归档效果显著、写论文时要用的重点实验**:记录每个实验*为什么做、怎么做、配置是什么、结果如何、如何复现*,防止遗忘"哪些实验做过、怎么做出来的"。

每个重点实验对应一个子文件夹,内含三样东西:**① 原始结果 CSV  ② 出图/算指标的 Python 脚本  ③ 脚本跑出来的结果(图)**。

---

## 实验一:Model-Based 场景下带宽预测带来的 QoE 提升 (`model-based-QoE/`)

### 为什么做这个实验
Plum 的核心是**双向(上/下行)带宽协同分配**——通过调整客户端上下行码率,把半双工 WiFi 的信道 airtime 更合理地分给两个方向,从而提升整体 QoE。
但这一切的前提是:**必须先把可用带宽"测准 / 预测准"**,才能做出更好的上下行分配决策。为此我们在 Plum 里引入一个**基于 Transformer 的带宽预测模块**(以分段平稳为归纳偏置,配合在线变点检测)。
本实验就是要证明:**在 Model-Based 场景下,把带宽估计从 BBR 换成 Transformer 预测后,系统吞吐和 QoE 会变好。**

### 场景与配置
- **场景 (Model-Based)**:用 ns-3 的 mobility 能力,节点在空间内随机跳变(2D random walk),形成类似"分段平稳"的带宽轨迹(模仿 Pensieve 合成数据的思路)。
- **ns-3 二进制**:`scratch/test_wifi_channel`(源码 `emulation/videoconf/model/vca_{client,server}.cc`)。
- **运行脚本**:`evaluation/test-wifi-channel.sh`(批量版 `evaluation/batch-run-test-channel-model.sh`)。
- **参数**:
  - `policy=2` (PLUM)、`qoeType=2` (sqr_convex)、`simTime=1200`(**关键:必须 1200,用 120 会因节点没走到弱信号区导致吞吐虚高、结论失真**)。
  - `nClient ∈ {3, 4, 6}`
  - `seed ∈ {777, 42, 55, 6, 7, 20, 84, 234, 1000, 81}`(10 个)
  - `mlpred ∈ {0, 1}`(0 = BBR 基线,1 = Transformer 预测)
  - ⇒ 共 **3 × 10 × 2 = 60 组** run。
- **依赖的三个进程**:
  1. 求解器 `python3 scripts/solver/solver.py -n <N>`(系统 python3 + scipy,监听端口 **11999**)。
  2. ML 推理服务 `bwpred/model/inference/run_inference_server.py`(监听 `127.0.0.1:9999`,需 torch 的 conda 环境 `~/anaconda3/envs/SeCBAD/bin/python`,本节点无 GPU,CPU 推理)。
  3. ns-3 仿真本体。
- **指标**:每组 run 用 `evaluation/log-process.py` 解析出 `avg_thp` / `qoe`;整体提升 = **按 mlpred 分组求均值**,`(mean_ml1 − mean_ml0) / mean_ml0`。

### 单组 run 的命令(用于逐组复现)
```bash
# 1) 起求解器
python3 scripts/solver/solver.py -n 3 &
# 2) 起推理服务 (mlpred=1 时必需)
~/anaconda3/envs/SeCBAD/bin/python bwpred/model/inference/run_inference_server.py &
# 3) 跑 ns-3 (以 seed=20, nClient=3 为例)
cd emulation/ns-allinone-3.37/ns-3.37
NS_GLOBAL_VALUE="RngRun=20" ./ns3 run "scratch/test_wifi_channel --mode=sfu --logLevel=0 --simTime=1200 --policy=2 --nClient=3 --qoeType=2 --mlpred=1"
```

### 结果 ✅
| 指标 | w/o ML (BBR) | w/ ML (Transformer) | 提升 |
|---|---|---|---|
| avg_thp | 317231.7107 | 371283.0940 | **+17.04%** |
| qoe | 0.1140 | 0.1217 | **+6.73%** |

即 **加上 Transformer 带宽预测后,吞吐 +17.04%、QoE +6.73%**。详见本目录三个文件。

### 本目录文件
| 文件 | 说明 |
|---|---|
| `result_channel_model_independent.csv` | **原始结果数据**。已筛为产生 +17% 的那批数据:`nclient∈{3,4,6}`,10 seeds × 2 mlpred = **60 行**(30 vs 30 配平)。 |
| `plot_channel_model_segwifi.py` | 读上面 CSV,按 mlpred 分组算均值提升并出图(`DATA_PATH` 已指向本目录 CSV)。 |
| `mlpred_performance_comparison.png` | 脚本跑出来的结果图,标题直接显示 +17.04% / +6.73%。 |

### 一键复现(仅重算指标+出图)
```bash
cd result_backup/model-based-QoE
MPLBACKEND=Agg python3 plot_channel_model_segwifi.py
# 打印:吞吐 +17.04%,QoE +6.73%;生成 mlpred_performance_comparison.png
```

### ⚠️ 可复现性备注(写论文务必注意)
1. **范围务必写清 `nclient∈{3,4,6}`**。线上 `evaluation/results/result_channel_model_independent.csv` 在 5/17 之后又追加了 **残缺的 nclient=7(mlpred 0/1 = 1/9 行)、nclient=8(10/4 行)**;这些没跑完的不配平数据会把整体提升从 +17.04% **稀释到 +8.44%**。本备份 CSV 是移除这些残缺行后、还原到出 +17% 当时(5/17)的干净子集。
2. **重跑 ns-3 可逐 bit 复现**:已验证 `nClient=3, seed=20, simTime=1200` → `ml0 avg_thp=188135.33`、`ml1 avg_thp=647653.33`,与 CSV 完全一致(ns-3 由 RngRun 确定性)。
3. **ml1 的精确数值依赖具体的推理服务/模型 checkpoint**(当时那个 9999 服务 pid 309890 约 5/19 起、加载 `finetuned_epoch_10.pth` 同期模型)。若重启或更换模型,ml1 会变——**论文中需锁定该 checkpoint**。
4. **聚合口径是"非配对分组均值",对行数不平衡很敏感**。更稳健的写法是改成**逐对(相同 nclient+seed)提升后再平均**;若坚持用分组均值,需补齐 n=7/8 使其配平。
