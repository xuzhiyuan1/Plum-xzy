# 预测驱动与能耗感知的双向带宽协调：面向半双工瓶颈的实时视频流（草稿 v2）

> 中文初稿。保留中文，英文术语/变量/LaTeX 公式保留。
> 诚实声明：**【待补设计】**/**【待补实验】**/**【待验证假设】** 为缺口，未完成不得包装为贡献。所有数字来自 `result_backup/` 实际文件（经脚本复核），模型能耗为文献锚定建模值非真机实测。
> 参考文献键 `tonNNNN` 对应 `docs/past_ton/ton_2025_2026_references_v2.bib`（本次用新 ISSN 2998-4157 校正收集的 2025–2026 TON 论文）。
> **本稿结构为方案 A（Prediction+Green 统一）；若联合实验不支持统一，改方案 B（Green 主线，Prediction 作 future extension），见 §17。**

---

## 中文标题
预测驱动与能耗感知的双向带宽协调：面向半双工瓶颈的实时视频流

## 英文标题候选
1. Prediction-Driven, Energy-Aware Bidirectional Bandwidth Coordination under Half-Duplex Bottlenecks for Real-Time Video Streaming
2. Green-PLUM: Unifying Bandwidth Prediction and Energy Awareness in Bidirectional Rate Coordination

## 中文摘要
WLAN 半双工信道使上下行流共享物理信道并趋于公平分配，但对双向体积流应用（视频会议、AR/VR、远程驾驶【ton0580】）次优。本文在 Plum（ICNP'24）双向带宽协调基础上探索两条扩展：(1) 预测增强 PLUM，用 Transformer 带宽预测参与容量观测与分配；(2) Green-PLUM，在分配中引入设备剩余电量 SoC 与温度，探索画质、存活和热稳定之间的权衡。初步结果【口径受限】：在 model-based 原生 Wi-Fi、N∈{3,4,6}、10 seeds 下，预测使吞吐 +17.04%、QoE +6.73%；Green 目前只有 trace-driven、N=8、3 seeds 的方向性结果，而且功耗/温度模型尚未校准，因此暂不在摘要中报告其绝对数值。Prediction 与 Green 当前尚未形成联合控制闭环。**【待补设计与实验：预测—能耗耦合机制、Pred+Green 联合对照、Green ≥10 seeds 与置信区间、预测失效边界、能耗模型校准】**。完成这些验证后，才能判断是否可以统一为“预测驱动、能耗感知的双向协调”。

## 关键词
双向带宽协调；半双工瓶颈；视频流；QoE；带宽预测；能耗感知；过热降频；Wi-Fi

## 1. Introduction
双向体积流应用（AR/VR 社交、4K 视频会议、远程驾驶）普遍产生上下行并重流量【ton0580,ton0191,ton0289】。WLAN 半双工信道下，上下行依据 802.11 MAC 趋于统计公平分配，但应用视角的"不公平"分配可最大化 QoE。Plum（ICNP'24）提出应用层双向带宽协调：以 Hossfeld 多用户 QoE 效用为目标，SLSQP 求解最优双向分配，entangled state machine 一致执行，不修改 MAC。

期刊扩展需超越会议版。本文提出两条扩展并论证可统一：
- **预测增强**：现有 Plum 容量检测反应式（BBR），滞后于信道波动。引入 Transformer 预测前瞻参与容量观测，model-based Wi-Fi 下吞吐 +17.04%【已有初步结果】。但 trace-driven 部分配置存在"吞吐对预测结构性不敏感"的失效边界——本文给出该边界与机理【待补实验+理论】。
- **Green-PLUM**：Plum 只优化画质，忽略电量与温度。低电设备掉线、过热降频致画面崩塌。Green 叠加 SoC/温度约束，对低电/过热设备按 $\lambda$ 缩放码率，换存活与温度稳定，代价为部分画质。

**贡献**（仅列已有证据支撑者）：
1. 扩展 Plum 为预测增强与能耗感知双向协调，给出统一的多目标优化框架形式（§5）【统一性待 Pred+Green 联合实验证实】。
2. 实现 `--green`/`--obsdeliv` 的 C++/solver 闭环协议与 SoC/温度状态机（§11）【已实现】。
3. 在 model-based 与 trace-driven 两平台评估五对照【部分已有初步结果，P0 实验待补】。
4. 【待验证假设】预测误差对最优分配的扰动界——**未推导，暂不作为定理贡献**。

## 2. Background and Motivation
双向体积流：远程驾驶【ton0580】、视频会议、AR/VR 均上下行并重。WLAN 半双工：AP 下行与客户端上行竞争同信道，DCF 下趋于统计公平。应用视角的不公平分配可最大化 QoE。现有速率控制单向：ABR 与 CC 均只控出流，缺双向协调【ton0066 Pudica 单向 CC，ton0191 Conflux 多链路，ton0450 BIFROST CDN-CC】。能耗/热新维度：长会议中设备耗电发热，过热降频致画面崩塌【ton0205,ton0534】。

## 3. 原始 Plum 回顾
系统模型：N 客户端经 SFU，$u_i+d_i\le B_i$，下行受内容源约束。QoE 效用 $U=(1-\rho)Q(\mathbf d)+\rho F$，$F=1-2\sigma(Q)$。优化 $\max_{\mathbf d} U$，SLSQP 求解，Theorem 1/2（网络/应用受限）。系统：服务器主导 entangled state machine，不侵入 CC。实验 +48–59%。

## 4. System Model
沿用 Plum 并扩展：每客户端新增 SoC$_i\in[0,1]$、温度 $T_i$、充电 $c_i$。瞬时功率（文献锚定建模）：
$$E_i(u,d)=P_\text{base}+(1.3u+d)e_\text{bit}(u+d)+P_\text{enc}(u/u_\text{ref})^{t_\text{enc}}+P_\text{dec}(d/d_\text{ref})$$
热模型（一阶 RC + 滞回节流）：$T_i\leftarrow T_i+\frac{\Delta t}{\tau_T}(T_\text{amb}+R_\text{th}E_i-T_i)$，$T\ge41°C$ 触发降频。

## 5. Problem Formulation
统一目标：$\max_{\mathbf d} U(\mathbf d)-\sum_i\lambda_i\frac{E_i(u_i,d_i)-P_\text{base}}{P_\text{ref}}$，$\lambda_i=k(1-\text{SoC}_i)^m$（充电 $\lambda_i=0$），$u_i=B_i-d_i$ 受 UL cap 约束。**【待验证假设】**预测误差 $\epsilon$ 对 $\mathbf d^*$ 的扰动界——计划用灵敏度分析，需假设效用 Lipschitz、误差有界；**未推导前不写入贡献**。

## 6. Prediction-Enhanced PLUM
Transformer 预测服务 + solver 并发查询；`--mlpred` 下容量观测从反应式 BBR 切换为预测融合（vca_client 权重 0.6）。结果【已有初步结果，model-based 802.11p@10MHz, policy=2, N∈{3,4,6}, 10 seeds】：

| 指标 | w/o ML Pred | w/ ML Pred | 提升 |
|---|---|---|---|
| 吞吐 avg_thp | 317231.71 | 371283.09 | +17.04% |
| QoE | 0.1140 | 0.1217 | +6.73% |

适用范围：仅 model-based + N∈{3,4,6}。trace-driven 部分配置结构性不敏感（天花板实验）【待补：失效边界机理解释】。

## 7. Green-PLUM
三套实现严格区分（禁止混用数字）：
- (1) 独立数值模型（`green/`，6 设备 60min）【已有初步结果】：first_death Vanilla 32min / Plum 38.7min / Green 52min；alive_end Vanilla 3 / Plum 4 / Green 4；过热累计 Plum 260→Green 89 设备·分钟。
- (2) solver 闭环（`--green`）【实现但未可靠验证：结果缺失】。
- (3) trace-driven 包级（`test_half_duplex_paper.cc`，N=8, 3 seeds）【已有初步结果，统计不足】：

| 指标 | Vanilla | Plum | Green |
|---|---|---|---|
| 平均下行码率 | 4.75 | 9.33 | 5.40 Mbps |
| 最差用户下行 | 2.18 | 6.57 | 3.73 Mbps |
| 存活（均值） | ~1.3/8 | 2/8 | 4/8 |
| 峰值温度 | ~92°C | ~60°C | ~47°C |

注：92°C 与单设备峰值功率 ~20W 为模型 artifact，物理偏极端，投稿前须校准（§17）。Green 代价：吞吐比 Plum 低约 42%。

## 8–10.（并入 §5–7）

## 11. Implementation
`--green` 扩展 C++/solver 协议（run_id, sim_time, 每客户端 UL/DL 送达速率）；solver 积分 SoC/温度返回 DL 分配 + UL cap。`--obsdeliv`：接收侧送达字节 EWMA(0.7/0.3) 替代 pacing，带下限。`green_energy.py`：`GreenState` 维护 SoC/温度/存活，`solve_green` 叠加 $\lambda$ 加权能耗项。UL cap：$u_i\le u_\text{max}/(1+2\lambda_i)$。默认关闭，旧实验行为不变。

## 12. 统一控制与优化
**【待补设计】** 预测→能耗决策的耦合机制：当前 Green 的 UL cap/λ 仅依赖当前 SoC/温度，**不依赖未来带宽信息**，故预测与 Green 当前为松耦合。统一叙事成立需：(a) 让 Green 决策受预测未来容量调制（如预判信道变差时提前降速省电降温）；(b) Pred+Green 联合实验证实预测改善能耗/温度。**当前两者未形成统一系统**。

## 13. Evaluation Methodology
平台：NS-3.37 + videoconf SFU, TCP+BBR。两套：model-based 原生 Wi-Fi；trace-driven Fig.11 独立接入（餐厅 WiFi trace 11–36Mbps）。对照：Vanilla/Plum/Pred/Green/Pred+Green。N∈{3,4,6,8}；目标 ≥10 seeds（Green 当前 3）。指标：吞吐/QoE/最差用户/fairness/RTT/功率/总能耗/掉线时间/存活/过热时间/solver 开销/控制开销。**【待补：置信区间、RTT/solver开销/控制开销记录】**。

## 14. 已有初步结果
见 §6、§7 表。所有数字须以 ≥10-seed 重跑结果替换。

## 15. 实验缺口
见 `docs/ton26/TON投稿准备度与缺口分析.md` 与 `当前实验进度与证据清单.md`。投稿前最重要：统计严谨性(3→10 seed+CI)、Pred+Green 联合、预测失效边界、能耗模型校准(92°C/20W artifact)、Green 主线选定，以及取得 seq312 等候选全文后确认真正可比的相关工作。

## 16. Related Work（基于新 ISSN 校正收集的 2025–2026 TON）
**当前尚未确认 R1 直接竞争论文。** seq312 Bi-Level Bandwidth Coordination for Video Inference 是最接近的候选，但场景是边缘视频推理且全文未取得，暂列 R2。
**R2（方法借鉴）**：seq312 多路视频推理带宽协调；Conflux【ton0191】多链路 ABR；Pudica【ton0066】交互视频 CC；Libra【ton0033】通用 CC 框架；INCC【ton0231】主动瓶颈 CC；QoE-Fairness【ton0383】异构 CC 公平；NeuroBA【ton0442】神经符号 ABR；5G-RAN-QUIC【ton0420】跨层分析；BIFROST【ton0450】CDN-CC 解耦；Compass【ton0495】（含 Plum 作者）；FAR【ton0467】速率控制；AraLivePro【ton0583】RL 奖励自适应；QoE-UAV-MEC【ton0205】能耗约束；EEFL【ton0534】移动设备能耗；Edge bitrate re-adaptation【ton0491】预测精度≠QoE。
**动机**：Teleop-AV【ton0580】双向体积流。
（注：引用键 tonNNNN 对应 catalog_v2 的 sequence_id；正式引用前需核对作者全名与卷期。）

## 17. Discussion and Limitations
- 能耗为文献建模值，非真机实测；92°C/20W 模型 artifact 须校准。
- 3 seeds 不足；无置信区间。
- 预测失效边界未解释。
- 三套 Green 实现禁止混用；建议 trace-driven 为主线、green/ 作支撑。
- **Pred+Green 当前未实现联合**，统一性为设想。
- **方案 A（统一）**需证据：Pred+Green 联合实验 + 预测-能耗耦合机制 + 扰动界。
- **方案 B（Green 主线，Prediction 作 future extension）**：若联合实验显示预测对能耗无增益。方案 B 需证据：Green 主线 ≥10 seed + 能耗校准 + 经全文确认的相关方法对比；预测作 §Future Work。**当前证据不足以确定 A/B，倾向待联合实验后决定。**

## 18. Conclusion
将 Plum 扩展为预测驱动、能耗感知的双向带宽协调，给出统一多目标框架与实现，及初步结果。统一性、预测失效边界、统计严谨性、能耗校准为投稿前必须补齐项。【待补全部 P0 后定稿】

## 19. 参考文献
见 `docs/past_ton/ton_2025_2026_references_v2.bib`（新 ISSN 2998-4157 校正，664 篇研究论文）。原 Plum（ICNP'24）见 `docs/plum-icnp24.pdf`。
