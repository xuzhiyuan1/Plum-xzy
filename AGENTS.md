# Plum 项目记忆

## 当前分支布局（2026-08-10）

- master：ICNP 基线。
- xzy-prediction：在 ICNP 基线上加入 Transformer 带宽预测，主要代码位于 bwpred/。
- xzy-green：继承 Prediction，并加入功耗/温度方向，主要代码位于 green/；docs/ 暂只保存在本分支。
- 下一研究方向等内容明确后，再从合适基点新建分支。

最后更新：2026-08-10（Asia/Shanghai）。本文件用于为以后在该仓库工作的 Codex/编程智能体保存长期项目上下文。

## 工作环境与仓库

- 权威工作副本位于远端：`school-server:/home/xuzy/Plum-for-award/Plum`。
- SSH 别名：`school-server`；远端用户：`xuzy`；远端主机名：`streaming177`。
- 这是 ICNP'24 Plum 论文《Bidirectional Bandwidth Coordination under Half-Duplex Bottlenecks for Video Streaming》的实验仓库。仓库包含 NS-3.37 包级仿真、`videoconf` SFU 模块、Python/SLSQP 带宽分配、带宽预测和 Android 流量跟踪程序。
- Git、编译和实验命令应在远端项目目录执行，不要把本地 Codex 工作目录误当作项目源码目录。

## 工作区安全注意事项——操作前必读

- 工作区应保持 clean；切换分支前先检查状态，不要删除服务器上被忽略的备份、下载论文和实验日志。
- 编辑前先运行 `git status --short --branch`，完整保留已有的 tracked 和 untracked 工作。
- 大型日志、PDF、生成的图片和结果目录与源代码混在一起。不要不加区分地把它们全部加入 Git。
- AGENTS.md 用于保存项目背景、分支约定和实验口径，应随主线状态更新。

## 2026-07-23 的分支状态

- 当前分支：`energy`，位于 `c65075c`，跟踪 `origin/energy`，ahead 0 / behind 0。
- `xzy-ml` 和 `origin/xzy-ml` 也指向 `c65075c`。也就是说，`energy` 当前从已完成的 ML/trace-driven 主线分出，但 Green 工作仍在工作区中，尚未进入该分支的提交历史。
- `xzy-master` 位于 `cc2b37b`，`origin/xzy-master` 包含该提交。这是基于上游 Plum 建立的较薄个人基线。
- `origin/master` 是上游 ICNP 实验仓库历史。其他远端分支，如 `lastn`、`sharedAP*`、`s2c-lambda` 等，是较旧或不同方向的实验分支，不是当前工作主线。
- `origin/forAward` 位于 `42496f7`，提交标题为 `Save my local changes before switching remote`，其中包含较早版本的 trace-driven 评测脚本拆分，不是当前实现的基础。
- reflog 中仍有提交 `84c9165`：`feat(energy): Green-PLUM ... v1`。它于 2026-07-15 创建，随后从 `energy` 分支上 reset 掉。该提交只包含早期四文件独立原型：`green/green_plum_sim.py`、`metrics.json`、一张图片和参考文献。不要直接 reset 或盲目 cherry-pick：当前未跟踪的 `green/` 已经是明显更新、内容更多的研究版本。

## 当前主线上已经提交完成的工作

从 `cc2b37b` 开始，`xzy-ml`/当前基础主线完成了以下工作：

1. 增加 ML 带宽预测代码（`24ba2f3`）。
2. 打通 Plum 与预测服务，并把 Python solver 改为并发处理（`23a2278`）。
3. 保存 model-based 正向结果（`b8d0c1c`）：在 NS-3 原生 Wi-Fi、Plum policy 2、`n={3,4,6}`、10 个 seed 的口径下，ML 预测使总体吞吐提高 17.04%，QoE 提高 6.73%。自包含报告和实验材料位于 `result_backup/mlpred-gain-17pct/`。
4. 探索 trace-driven/shared-bandwidth 的因果关系，增加干净观测和由开关控制的诊断逻辑（`20c6a23`）；天花板实验表明，在部分配置中吞吐对预测存在结构性不敏感（`cfbaf64`）。
5. 修复遗漏的诊断字段声明，并接通服务端分配到物理链路控制的桥接（`fc3b37e`、`20f6034`）。
6. 整理结果备份并完成 1200 秒 trace-driven、N=3..8 的全量实验（`49b3ee8`、`9bb1d1f`、`f33a530`）。已提交记录中的 N=3..6 结论约为吞吐提高 15.6%、QoE 提高 9%；引用时必须明确适用范围，并使用结果备份中的 evaluator，不要直接推广到所有 N。
7. 修复 ML/CC 融合权重：`vca_client` 中预测权重从 0.8 改为 0.6，使总权重为 1.0；同时加入 trace-driven 预测和 Wi-Fi tuned scratch 实验脚手架（`c65075c`）。

## xzy-green 已提交的 Green-PLUM 工作

目前存在三个有关联但并不相同的层次。不要混用它们的实验结果或场景含义。

### 一、独立的能耗与温度研究模型

- 目录：`green/`。
- 主要文件：`green_plum_study.py`、`sensitivity.py`、`FINDINGS.md`、`ENERGY_REFERENCES.md`、JSON 输出和 A-E 图。
- 目的：使用 2020 年以后的文献参数，对电池、设备功耗、温度变化、过热降频以及 QoE/能耗 Pareto 权衡进行建模。
- `FINDINGS.md` 中 6 设备、60 分钟代表场景的结果：Vanilla 第一台设备在 32 分钟掉线，Plum 在约 38.7 分钟掉线，Green 在 52 分钟掉线；相较 Plum，Green 把累计过热降频时间从约 260 设备·分钟降到 89 设备·分钟，但代表实验中的有效 QoE 比 Plum 低约 20%～22%。
- 应诚实描述研究结论：Green 用一部分画质换取更好的存活和温度稳定性，它不是无条件提高 QoE。
- 这些能耗和温度来自文献参数模型，不是真实手机测量值。

### 二、接入 `test_wifi_channel` 的 Green 闭环

当前被修改的 tracked 文件：

- `emulation/scratch/test_wifi_channel.cc`
- `emulation/videoconf/model/vca_server.cc`
- `emulation/videoconf/model/vca_server.h`
- `scripts/solver/solver.py`

主要实现和配置文件：

- `scripts/solver/green_energy.py`
- `scripts/solver/green_cfg*.json`
- `evaluation/test-wifi-green.sh`
- `evaluation/test-green-n3-arms.sh`
- `evaluation/run_armC2.sh`
- `evaluation/run_armVanEnergy.sh`
- `evaluation/run_contention_sweep.sh`
- `evaluation/batch-run-fig14-repro.sh`

实现概况：

- `--green` 启用扩展后的 C++/Python solver 通信协议，传输 run、仿真时间和实际送达的 UL/DL 速率；solver 负责积分更新 SoC 和温度，并同时返回 DL 分配和能耗/温度约束下的 UL cap。
- `--obsdeliv` 把容量观测从 pacing/目标速率改为接收侧实际送达字节统计，同时带有 EWMA 平滑和防止恢复被扼杀的下限逻辑。
- 两个开关默认都是关闭的，因此旧协议和旧实验在默认情况下应保持原行为。
- `.bak_green` 和 `solver.py.bak_green` 是接入 Green 之前有意保留的备份。在 Green 工作安全进入版本历史之前，不要删除。
- 多个 arm/sweep 日志显示实验执行完成，但当前 Green/Fig.14 汇总 CSV 已不存在。部分日志还记录了某一轮结束后 solver 进程被 `Killed`。该路径仍处于进行中，引用结果前必须重新验证。
- `evaluation/results/result_contention_sweep.csv` 仍存在，但其中许多 policy 对照完全相同或表现不稳定；它属于诊断结果，不是最终正向结果。

### 三、trace-driven Green 论文场景实验

- 主要 scratch：`emulation/scratch/test_half_duplex_paper.cc`。
- 整理后的备份和报告：`result_backup/green-plum-tracedriven/`。
- 这是独立接入、trace-driven 的论文 Fig.11 风格场景：每个客户端拥有各自的半双工 UL/DL 瓶颈，不是多个客户端共享同一个 Wi-Fi PHY/MAC。
- `traceMode=0/1/2` 分别表示 Vanilla 上下行均分、Plum 协调分配、Green 缩放分配。
- 报告中的初步 N=8、3-seed 结果：Vanilla / Plum / Green 的平均 DL 吞吐分别是 4.75 / 9.33 / 5.40 Mbps；最差用户 DL 分别是 2.18 / 6.57 / 3.73 Mbps。模型中的会议结束存活设备数为 1 / 2 / 4，平均模型功率为 5.31 / 4.02 / 3.21 W。
- 报告明确把这些结果标记为初步结果。Green 的网络表现仍好于 Vanilla，但在该工作点比 Plum 牺牲约 42% 平均吞吐。对外使用温度结论前，应重新检查温度数值的物理合理性和公平性。

## 当前 Git 状态摘要

- xzy-prediction 固定在 Prediction 提交 c65075c。
- xzy-green 在其上保存 Green 实现、实验材料和 docs/。
- 本地备份、批量论文 PDF、缓存和生成日志由 gitignore 排除。

## TON 2026 投稿文档与 LaTeX 环境

- TON 草稿目录：`docs/ton26/`；主文件为 `main.tex`，参考文献库为 `references.bib`，中文使用说明见该目录的 `README.md`。
- 使用 IEEEtran journal 双栏骨架。标题、作者、摘要、参考文献作者信息和正文目前均为起草占位，正式投稿前必须核对。
- 用户级 TinyTeX/TeX Live 2026 安装于 `~/.TinyTeX`，不需要 sudo；命令链接位于 `~/.local/bin`，该目录已加入 `~/.zshrc` 的 PATH。
- 已安装并验证 `pdflatex`、`latexmk`、BibTeX、Biber、IEEEtran 及常用数学/表格/引用宏包。
- 编译命令：`cd /home/xuzy/Plum-for-award/Plum/docs/ton26 && latexmk -pdf main.tex`。2026-07-27 已通过完整多轮编译，生成 `main.pdf`，最终日志无 LaTeX warning/error。

## 建议的下一步

1. 确定下一份论文或评奖材料以哪套 Green 实现为主：solver-integrated model-based Wi-Fi、trace-driven 论文风格实验，或者两套都保留但严格区分结论。
2. 从一套干净、明确的复现命令重新跑选定路径，重新生成汇总 CSV，并调查 solver 生命周期和 `Killed` 记录。
3. 跨 seed 和不同 N 验证功率/温度范围、存活定义以及网络性能与能耗的权衡；不要混用独立数值模型和包级仿真的结果。
4. 验证完成后按逻辑拆分提交：Green 核心状态/模型、C++/solver 协议、实验脚本/配置、精简后的结果与报告。提交或推送前先征得用户同意。
