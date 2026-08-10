# TON 相关论文精读 v2

- 生成：2026-07-27
- 范围：人工复核的关键 R2 候选。当前没有基于可得全文确认的 R1 直接竞争论文。证据标注【全文精读】/【摘要精读】。
- 诚实声明：仅 2 篇 R2 有 OA 全文（NeuroBA、5G-RAN-QUIC）；其余基于摘要，"数学模型/算法细节/实验规模"等字段标注"待核实全文"，不臆造。
- 上一轮 v1 的 8 篇 A 类复核结论见末尾。

---

## 最接近的相关候选（暂列 R2）

### R2-0. Bi-Level Bandwidth Coordination for Multiple Video Inference at the Edge
- 引用：IEEE Trans. Netw., vol. 34, 2026. DOI: 10.1109/ton.2025.3615604 | seq 312
- 证据：【摘要精读】（无 OA 全文）
- 研究问题：多路 HD 视频（监控/交通）帧卸载到边缘服务器，多流竞争下的带宽协调。
- 核心观察：多流竞争边缘带宽，需双层（前端设备↔边缘）协调。
- 创新点：双层（bi-level）带宽协调框架。
- 技术方案：待核实全文。
- 理论分析：待核实全文。
- 实验平台/数据集/baseline/消融/统计：待核实全文。
- 局限性：待核实全文。
- 与 PLUM 关系：是目前标题和摘要层面最接近的“多终端带宽协调”工作，但本文是边缘视频推理（帧卸载），Plum 是双向体积流视频会议；本文“双层”指设备-边缘，Plum“双向”指 UL/DL。**因无全文，暂不能称为直接竞争或确认可作 baseline。**
- PLUM 可借鉴：双层协调的建模思路；须在论文中明确区分"双向(UL/DL)"与"双层(设备-边缘)"。
- 适合 baseline：**是**（须取得全文确认场景可比性后）。
- **关键动作：必须获取全文精读并对比**。

---

## R2（关键方法相关）

### R2-1. NeuroBA: Neuro-Symbolic Bitrate Adaptation for IRS-Aided Mobile Video Streaming
- 引用：IEEE Trans. Netw., vol. 34, 2026. DOI: 10.1109/ton.2025.3650266 | seq 442
- 证据：【全文精读】（OA: mdsoar.org）
- 研究问题：边缘视频 ABR 在时变带宽、部分可观测下，纯 RL 采样效率低、缺视频质量感知。
- 核心观察：现有智能 ABR 缺逻辑推理能力，采样效率低。
- 创新点：神经符号深度 RL（一阶逻辑符号知识驱动视频质量感知 + 神经网络决策）；IRS 相移增强无线吞吐。
- 技术方案：神经符号 DRL + IRS 相移优化（具体网络结构/奖励待核实全文细节）。
- 理论分析：无（算法+实验为主）。
- 实验平台：trace-driven + real-world。
- baseline：BOLA、Fugu 等 SOTA ABR。
- 消融/敏感性：待核实全文。
- 统计严谨性：报 QoE +16.58%(vs BOLA)~+25.34%(vs Fugu)；seed/CI 待核实全文。
- 局限性：IRS 假设；符号逻辑依赖视频文本摘要质量。
- 与 PLUM 关系：ABR 评测口径（QoE +16–25%）与 Plum model-based +17% 吞吐同量级，可作横向参照；神经符号/可解释是 2026 ABR 新趋势。
- 借鉴：可解释性叙事；ABR 量化粒度参照。
- 适合 baseline：否（场景不同：IRS 移动边缘 ABR vs Plum 双向 WiFi 协调）。
- 证据：全文。

### R2-2. From 5G RAN Queue Dynamics to Playback (QUIC Video Streaming)
- 引用：IEEE Trans. Netw., vol. 34, 2026. DOI: 10.1109/ton.2025.3646971 | seq 420
- 证据：【全文精读】（OA: arxiv 2508.15087）
- 研究问题：ABR×CC×5G RLC 排队跨层交互，孤立优化不足。
- 核心观察：AQM(RED/L4S) 效果与 QUIC 实现/CC/ABR 强耦合，孤立优化不足。
- 创新点：跨层交互的综合性能分析（非新机制，是分析）。
- 技术方案：多种 QUIC 实现 × AQM × CC × ABR 的对照实验。
- 理论分析：无（经验分析）。
- 实验平台：5G 仿真/测试。
- baseline：多 QUIC 实现/CC/ABR 组合。
- 消融/统计：待核实全文。
- 局限性：5G 特定；未提出新机制。
- 与 PLUM 关系：强调"跨层协同必要性"——与 Plum"不改 MAC、在传输层以上协调"形成对照。可在 Discussion 引用：Plum 选择应用层协调避跨层复杂度，但需承认 5G 跨层必要。
- 借鉴：跨层论证；Discussion 反衬。
- 适合 baseline：否（分析论文非协调机制）。
- 证据：全文。

### R2-3. Conflux: A Multi-Homed Adaptive Bitrate Protocol for On-Site Live Video Streaming
- 引用：IEEE Trans. Netw., vol. 33, iss 6, 2025. DOI: 10.1109/ton.2025.3577974 | seq 191
- 证据：【摘要精读】
- 研究问题：现场直播多无线链路聚合，需决定每链路数据量、码率、冗余。
- 创新点：多宿主 ABR 联合调度多链路 + 冗余。
- 与 PLUM 关系：同属应用层码率协调家族；Conflux 是多链路（空间维度），Plum 是双向（UL/DL 维度）。
- 借鉴："联合决策码率与传输分配"建模。
- 适合 baseline：否（多链路 vs 双向，维度不同），但 related work 必引。
- 技术方案/理论/实验规模：待核实全文。
- 证据：摘要。

### R2-4. Pudica: A Practical CC Algorithm for Low-Latency Interactive Video Streaming
- 引用：IEEE Trans. Netw., vol. 33, iss 3, 2025. DOI: 10.1109/ton.2024.3519902 | seq 66
- 证据：【摘要精读】
- 研究问题：端到端 CC 在交互视频（云游戏）引起自诱导排队。
- 创新点：paced frame 探测带宽利用率，近零排队 + 高利用率 + 跨流公平。
- 与 PLUM 关系：同"交互视频+传输层速率控制"；Pudica 单向 CC，Plum 双向协调。其 pacing 探测与 Plum `--obsdeliv` 接收侧观测可对比。
- 借鉴：接收侧/探测观测方法对照。
- 适合 baseline：可考虑（同为交互视频速率控制，需全文确认场景）。
- 证据：摘要。

### R2-5. Toward QoE-Fairness for Video Streaming Over Heterogeneous Networks
- 引用：IEEE Trans. Netw., vol. 34, 2026. DOI: 10.1109/ton.2025.3638882 | seq 383
- 证据：【摘要精读】
- 研究问题：异构 CC 协议破坏多流 QoE 公平性。
- 创新点：跨 CC 协议的 QoE-公平带宽分配。
- 与 PLUM 关系：Plum 效用含公平性项 F=1-2σ；本文是异构 CC 同向多流公平。须区分"Plum 公平性是双向协调副产品"。
- 借鉴：公平性建模对照。
- 适合 baseline：否（同向多流 vs 双向）。
- 证据：摘要。

### R2-6. Compass: Congestion Control for Disobedient Traffic
- 引用：IEEE Trans. Netw., vol. 34, 2026. DOI: 10.1109/ton.2026.3663789 | seq 495
- 证据：【摘要精读】（作者含 Zili Meng，Plum 作者之一）
- 研究问题：数据中心 sender-driven CC 反馈延迟，disobedient traffic 逃逸控制。
- 与 PLUM 关系：作者重叠（Zili Meng）→ 同组系统设计口味；"反馈延迟致控制失效"与 Plum 容量检测滞后相关。
- 借鉴：反馈延迟分析。
- 适合 baseline：否（数据中心 vs WiFi 接入）。
- 证据：摘要。

### R2-7. Accurate is Not Necessarily the Best: Edge-Assisted Bitrate Re-Adaptation
- 引用：IEEE Trans. Netw., vol. 34, 2026. DOI: 10.1109/ton.2026.3661954 | seq 491
- 证据：【摘要精读】
- 研究问题：边缘缓存透明致客户端码率决策次优。
- 核心命题："准确未必最好"——对 Plum 预测有警示：预测精度提升不必然带来 QoE 提升（呼应 Plum trace-driven 天花板实验：吞吐对预测结构性不敏感）。
- 借鉴：预测精度≠下游收益的论证。
- 适合 baseline：否。
- 证据：摘要。

### R2-8. Teleoperating Autonomous Vehicles Over Commercial 5G Networks
- 引用：IEEE Trans. Netw., vol. 34, 2026. DOI: 10.1109/ton.2026.3686751 | seq 580
- 证据：【摘要精读】
- 研究问题：商用 5G 上 AV 遥操作（远程驾驶）可行性，跨层+端到端。
- 与 PLUM 关系：遥操作是典型双向体积流（上行视频/控制+下行视频），与 Plum 动机场景一致。**动机强佐证**。
- 借鉴：Motivation 引用。
- 适合 baseline：否（测量论文）。
- 证据：摘要。

### R2-9. AraLivePro: Automatic Reward Adaption for Learning-Based Live Video Streaming
- 引用：IEEE Trans. Netw., vol. 34, 2026. DOI: 10.1109/ton.2026.3687061 | seq 583
- 证据：【摘要精读】
- 问题：RL-based BCA 奖励函数固定，难适应动态环境。
- 创新：自动奖励学习，可插拔。
- 借鉴：若 Plum 转 RL，奖励/效用设计参照；"可插拔"思路。
- 证据：摘要。

### R2-10. QoE Maximization for Multiple-UAV-Assisted MEC
- 引用：IEEE Trans. Netw., vol. 33, iss 6, 2025. DOI: 10.1109/ton.2025.3581531 | seq 205
- 证据：【摘要精读】
- 问题：UAV-MEC 电池/算力/频谱受限，在线 QoE 优化。
- 与 Green-PLUM 关系：同为"能耗约束下 QoE 优化"，借鉴在线联合优化建模与电池容量约束写法。
- 证据：摘要。

### R2-11. Wireless-Aware Energy-Efficient FL Over Mobile Devices
- 引用：IEEE Trans. Netw., vol. 34, 2026. DOI: 10.1109/ton.2026.3671076 | seq 534
- 证据：【摘要精读】
- 问题：FL 中无线通信能耗 vs 本地训练能耗权衡。
- 与 Green-PLUM 关系：同为移动设备能耗建模；借鉴能耗拆分（通信 vs 计算）叙述。
- 证据：摘要。

### R2-12. BIFROST / INCC / Libra / FAR / MARL-CC（简列，【摘要精读】）
- BIFROST(seq450)：关注解耦的 CDN-CC，解耦哲学与 Plum 不侵入 CC 一致。
- INCC(seq231)：主动瓶颈感知 CC，VR/AR 延迟敏感；方法可借鉴 Plum 服务器侧协调。
- Libra(seq33)：通用 CC 框架适配多样应用偏好/网络条件，理念接近 Plum 适配应用需求。
- FAR(seq467)/MARL-CC(seq456)：速率控制/多智能体 CC 公平，方法论对照。
- 均非直接 baseline（场景不同），related work 引用。

---

## v1 的 8 篇 A 类复核结论
- v1 A1 NeuroBA → v2 R2（保留，全文）。
- v1 A2 Conflux → v2 R2（保留，摘要）。
- v1 A3 JumpDASH → v2 R3（降级，LLM 内容感知 DASH，非带宽协调）。
- v1 A4 Teleop-AV → v2 R2（保留，动机）。
- v1 A5 Full-duplex AAV → v2 R3（降级，物理层正交）。
- v1 A6 Strategic Profit(AoI) → v2 R4（剔除，关键词噪声）。
- v1 A7 Bidirectional Path(LEO) → v2 R4（剔除，路由非带宽）。
- v1 A8 Early Attack → v2 R4（剔除，攻击识别）。
- 结论：v1 的 8 篇 A 类中，**真正方法相关仅 2 篇（NeuroBA、Conflux）+ 1 篇动机相关（Teleop-AV）**，其余为关键词噪声或弱相关，已剔除/降级。v2 新增 seq312 作为最接近的 R2 候选；是否属于直接竞争需取得全文后再判断。
