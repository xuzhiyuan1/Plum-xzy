# 会议扩展到 TON 的经验与 PLUM 扩刊建议

- 生成:2026-08-05 | 中文,面向作者与导师
- 本报告新增研究维度:"网络会议论文扩展为 ToN 期刊论文时通常增加什么内容,对 Plum(ICNP'24)扩刊的启示"。沿用既有分析的结论与证据口径(`TON_2025_2026论文分析与投稿启示_v2.md`、`TON相关论文精读_v2.md`、`TON投稿准备度与缺口分析.md`、`当前实验进度与证据清单.md`),不重复项目考古与写作风格分析。
- 案例来源:2026-08-05 通过 WebSearch/DBLP/Semantic Scholar/OpenAlex/作者主页/arXiv 交叉核验,共确认 **14 组**真实扩刊配对(ICNP→ToN 6 组、SIGCOMM/NSDI→ToN 4 组、INFOCOM/CoNEXT→ToN 4 组)。**未编造任何配对**;核验中被证伪的候选(如 FTrack 会议版实为 SenSys 而非 ICNP)已列入排除清单防止误用。
- 证据分层标注:【脚注原文】= 期刊版 PDF 原句声明扩展关系;【全文diff】= 两版全文逐节/逐词对比;【摘要对比】= 摘要/元数据层对比;【配对确认,细节未确认】= 扩展关系可信但新增内容无全文可查;【推断】= 由页数/标题等间接推断。

---

## 1. 为什么需要研究会议→ToN 扩刊案例

1. Plum 的期刊版本质是 ICNP'24 的扩展投稿,ToN 明文要求 cover letter 中"articulate any changes made to improve and/or expand on those conference publications"——**差异说明是投稿硬件**,写什么增量、怎么讲增量,直接决定编辑与审稿人的第一印象。
2. 既有分析(投稿启示 §18)对"会议→TON 扩展通常新增什么"只有【综合推断】,没有真实案例支撑。本报告用 14 组可验证案例把它落到实处。
3. 两个关键政策事实(本次核实,附出处):
   - **ToN 没有"30% 新增"量化门槛**。ToN 官方:"there is neither a strict guideline regarding how different a submission must be from a previous version, nor a minimum requirement for additional or extended material";新增材料"does not necessarily need to include new results, and could be elaboration on existing results, technical proofs, etc."(comsoc.org ToN author guidelines;ComSoc 另有专页辟谣 30% 说法:"this is not IEEE policy, nor is it ComSoc policy")。约束是**定性**的:不得逐字重发,须有实质技术增量,且必须披露(附信列出会议版+公开链接+差异说明,会议版列入参考文献)。违规后果严重(两 venue 同拒 + IEEE ~6 个月禁投 + ComSoc 另加 ≥6 个月)。
   - **ICNP Best Paper 有 ToN fast-track 通道**("will be fast tracked to the IEEE/ACM Transactions on Networking, with a streamlined journal review process",ICNP 2021-2023 CFP)。Plum 非 best paper,走常规投稿,则更需要把增量做实——常规通道的 GEMINI(ICNP'19→ToN'22)修订历时约 2.5 年,提示常规扩刊评审并不轻松。

## 2. ICNP→ToN 的代表性案例(6 组)

| # | 案例 | 会议版 | ToN 版 | 标题变化 | 已确认新增 | 证据强度 |
|---|---|---|---|---|---|---|
| I-1 | GEMINI(跨DC拥塞控制,HKUST) | ICNP'19 | 30(5) 2022, 10.1109/TNET.2022.3161580 | 无 | 更完整实验数据(4 baseline 大小流 FCT 全口径),16 页 | 【脚注原文】"This work is an extended version of an ICNP'19 paper [1]" |
| I-2 | Virtual Filter(流量测量,U Florida) | ICNP'21 **Best Paper** | 30(6) 2022, 10.1109/TNET.2022.3182694 | 加副标题 "With Network Applications" | 新算法模块 **VF+**(会议版 0 次→期刊版 25 次);**两个新应用案例**(flow spread 测量、super spreader 检测,4→35 次);11→16 页 | 【脚注原文】+【全文diff】 |
| I-3 | AlignTrack(LoRa 冲突解码,清华) | ICNP'21 | 31(5) 2023, 10.1109/TNET.2023.3235041 | "Push the Limit"→"Push the **SNR** Limit" | 理论证明强化(minimal SNR loss)+ HackRF 实现;11→16 页 | 配对【元数据】高;细节【摘要对比/推断】 |
| I-4 | Proteus(无损DC负载均衡,HKUST) | ICNP'23 **Best Paper**(fast-track 实例) | 32(3) 2024, 10.1109/TNET.2024.3366336 | 完全重写:"Enabling Load Balancing for…"→"Load Balancing **With Multi-Level Signals** for…"(机制入题) | 未确认(非 OA) | 配对高(作者 8/8 一致 + fast-track 通道明文) |
| I-5 | GeneWave(声学认证,清华) | ICNP'17 | 26(4) 2018 | 无 | 未确认 | 配对中-高(作者官方发表页并列) |
| I-6 | CDN Transit Routing(Verizon 数据) | ICNP'16 | 26(1) 2018 | 无 | 未确认(10→14 页) | 配对中-高 |

ICNP 侧观察:
- **两条通道**:Best Paper fast-track(I-2/I-4,会议后约 1 年刊出)与常规投稿(I-1,修订 2.5 年)。Plum 走常规通道,应按 I-1/I-2 的增量标准准备,并预期多轮修订。
- **最硬的样本 I-2 的增量公式 = 新算法模块 + 新应用案例 ×2 + 页数 +45%**——不是"同一实验加量",而是给算法配上"应用生态"。
- 【诚实说明】视频流方向经多轮定向搜索(HotDASH 等)未找到可确认的 ICNP→ToN 案例;已验证 ICNP→ToN 样本集中在传输/测量/无线。与 Plum 场景最近的扩刊先例在其他会议(见 §3 Pudica/BOLA/Zhuge)。

## 3. 其他网络会议→ToN 的补充案例(8 组)

### 3.1 与 Plum 最相关的四组

| # | 案例 | 路径 | 与 Plum 的关系 | 已确认新增/变化 |
|---|---|---|---|---|
| S-1 | **Zhuge**(无线 RTC 低时延) | SIGCOMM'22 → ToN 33(2) 2025, 10.1109/TNET.2024.3502822 | **作者即 Plum 团队**(Bo Wang、Zili Meng、Mingwei Xu、Yaning Guo 等;会议版 7 人全保留,+2 人,一作 Zili Meng→Bo Wang) | 改题(系统名入题,"Shortest"→"Minimal" 更严谨);摘要结果 17–95%→22–95%(实验更新);14→16 页。【摘要对比】,章节级新增未确认(非 OA) |
| S-2 | **Pudica**(交互视频 CC,腾讯) | NSDI'24 → ToN 33(3) 2025, 10.1109/TON.2024.3519902 | **即精读清单 R2-4 的 ton0066**——现确认其为 NSDI'24 扩展版 | 彻底改题:"…for Cloud Gaming"→"A Practical CC Algorithm for Low-Latency Interactive Video Streaming"(**场景泛化** + 强调 Practical/部署,数百万玩家);作者 13→10,工程作者升第二位。【摘要对比】 |
| S-3 | **TACK**(无线 ACK 机制) | SIGCOMM'20 → ToN 29(6) 2021, 10.1109/TNET.2021.3101011 | **TACK 是 Plum ICNP'24 的 baseline [44]** | 彻底改题:"TACK: Improving Wireless Transport…"→"Revisiting Acknowledgment Mechanism for Transport Control: **Modeling, Analysis**, and Implementation"——从系统叙事升维为机制研究,理论化;作者 7/7 一致。【摘要对比】(网传"新增 IACK"未确认,不采信) |
| S-4 | **BOLA**(ABR 视频流) | INFOCOM'16 → ToN 28(4) 2020, 10.1109/TNET.2020.2996964 | ABR 家族,Plum 会议版引用 [23] | 全新 **Deployment 节**:进入 dash.js 参考播放器,Akamai/BBC/CBS/Orange 生产使用 + 衍生算法 DYNAMIC;更新记号与理论;更多实验;12→15 页。【脚注原文】+【全文diff】(arXiv v1/v3) |

### 3.2 其余四组(方法论参照)

| # | 案例 | 路径 | 已确认新增 |
|---|---|---|---|
| S-5 | Aeolus(DC 主动传输) | SIGCOMM'20 → ToN 30(2) 2022 | 【脚注原文】+【全文diff】:新增"How Does This Work?"集成小节、probe 机制**消融**、多队列场景变体、扩展到其他传输协议的讨论;13→15 页,正文 +20% |
| S-6 | FEDL(无线联邦学习) | INFOCOM'19 → ToN 29(1) 2021 | 【脚注原文】:**新增线性收敛率定理**;非凸损失 PyTorch 实验 vs FedAvg;标题后半句由"Optimization Model Design and Analysis"改写为"**Convergence Analysis** and Resource Allocation",精确对应新增理论 |
| S-7 | AoI 无线调度 | INFOCOM'18 Best Paper → ToN 27(4) 2019 | 【脚注原文】+【全文diff】:全新 **Drift-Plus-Penalty 第四策略节**(0→15 次);12→16 页;标题加前缀 "Scheduling Algorithms for" |
| S-8 | OLIA/MPTCP | CoNEXT'12 → ToN 21(5) 2013 | 完整理论证明入正文(会议版仅 sketch);12→15 页。配对高,细节【推断】。另注:2023 起 CoNEXT 论文改入 PACMNET,该通道近年收窄 |

## 4. 常见扩刊方式总结("期刊版为什么不只是加长版")

对 14 组案例中**新增内容可确认**的 7 组(I-1/I-2/S-4/S-5/S-6/S-7/S-8)归纳,扩刊增量可分五型(一篇通常组合 2–3 型):

1. **新模块型**:在原框架内加一个结构性新算法/新机制,并配独立小节与实验——VF+(I-2)、Drift-Plus-Penalty(S-7)、DYNAMIC(S-4)、Aeolus 集成机制(S-5)。**特征:新东西在会议版中出现次数为 0,可用全文词频干净验证。**
2. **新理论型**:新增定理/证明/建模——FEDL 收敛率(S-6)、OLIA 完整证明(S-8)、AlignTrack SNR 最优性(I-3,推断)、TACK "Modeling, Analysis"(S-3)。呼应 ToN 政策原文:新增材料"could be … technical proofs"——**纯理论补强是 ToN 明确认可的合法增量**。
3. **新应用/场景泛化型**:把机制推向新应用或更广场景——Virtual Filter 两个应用案例(I-2)、Pudica 云游戏→低时延交互视频(S-2)、Aeolus 多队列+其他协议(S-5)。
4. **部署/实用性强化型**:生产部署与真实影响力入正文——BOLA dash.js/Akamai(S-4)、Pudica 数百万玩家(S-2)。
5. **实验完备化型**:更全的 baseline 口径、更新的数字、消融补齐——GEMINI 全口径 FCT(I-1)、Zhuge 数字更新(S-1)、Aeolus probe 消融(S-5)。**单独使用此型的案例最弱**(I-1 仅此一型可确认,修订 2.5 年)。
- 篇幅规律:典型 11–13 页 → 15–16 页,正文约 **+20–45%**;间隔 1–3 年。
- **标题即增量声明**:14 组中 8 组改题,且改动方向精确指向新增轴——FEDL 后半句改成新定理名、Virtual Filter 副标题指向新应用、AlignTrack 聚焦到理论卖点、TACK/Pudica 从系统名升维为机制/问题名。**若 Plum 期刊版说不出标题该怎么改,通常意味着增量轴还不清晰。**
- 故事线共同规律:**从"一个能工作的系统"升维为"一类机制/框架 + 生态"**。会议版讲 point solution,期刊版讲 generalizable mechanism(TACK、Pudica)或 algorithm + ecosystem(VF、BOLA)。"加长版"(只做第 5 型)在样本中几乎不存在独立成功案例。

## 5. Plum ICNP'24 会议版已有贡献

(依据 `plum-icnp24.pdf` 通读;与 `TON投稿准备度与缺口分析.md` §1 一致,此处按"扩刊起点盘点"口径重述)

1. **问题识别与测量**:WLAN 半双工瓶颈下 MAC per-station fairness 对双向体积流次优;quintile-split 理论收益 +58.1%(Fig.4)、testbed 带宽让渡验证(Fig.5)、真机 app 并行度测量(Fig.6,5 志愿者)。
2. **政策层**:Hossfeld 多用户效用 U=(1-ρ)Q̄+ρ(1-2σ);三约束优化问题;**Theorem 1/2**(network-/application-limited)+ KKT 五类极值点分析;SLSQP 求解;4 种 QoE 函数。
3. **系统层**:server-dominant 三模块(capacity detection 反应式 5s/20% 阈值、coordinated rate optimization、bitrate state control);entangled state machine;不修改 MAC;与 BBR 集成;协调开销一个 float 字段。
4. **评估**:三平台(trace-driven NS-3、channel model-based+mobility、Salsify testbed);+48–59% 平均码率、90%ile +49.8%、JFI≥0.79、ρ 与 QoE 函数敏感性、优化延迟 <100ms@20 参与者、testbed 2.8× 上行提升与 PSNR。
- **扩刊视角的含义**:会议版已经是"理论+系统+三平台实验"的完整结构,**第 5 型(实验完备化)对 Plum 只能算修补,撑不起期刊增量**;必须至少落一个 1/2/3 型的新轴。这与既有判断("使用预测本身不构成创新")一致。

## 6. Prediction 与 Green 属于什么类型的期刊增量

按 §4 类型学对号:

- **Prediction(`--mlpred`,Transformer 容量预测融合)= 第 1 型(新模块)**,当前证据 model-based Wi-Fi、N∈{3,4,6}、10 seeds、+17.04%/+6.73%【已验证,口径受限】。
  - 对标 I-2 的 VF+ 与 S-7 的 Drift-Plus-Penalty:模块本身合格。
  - 但 2025–2026 TON 相关论文中 ML/RL 常见(投稿启示 §19),"加了预测"不新;**它的升格路径是叠加第 2 型**:预测失效边界机理(A2 trace-driven 结构性不敏感)+ 扰动界 T1。做成后,Plum 反而握有比"预测有效"更稀缺的主张——"预测何时无效"(与 R2-7 "Accurate is Not Necessarily the Best" 的命题呼应,而我们给出机理+理论)。
- **Green(SoC/温度感知分配)= 第 3 型(新问题维度)为主**:它改写 problem formulation 本身(效用 → QoE×能耗×热×存活多目标),不是在原目标下加模块——这在样本中是**比第 1 型更实质**的增量(类似把"分带宽"问题变成"分带宽+管设备生死"问题)。当前证据:trace-driven N=8 仅 3 seeds 方向性结果 + 92°C/20W artifact【初步,统计不足】。
  - 若补上真机/功率计校准(E1),还能挂上第 4 型(实用性)的边。
- **Pred+Green 统一(若 D1 耦合 + P0-2 联合实验成立)= 框架升维**:相当于 TACK 式的故事升级——从"一个双向分带宽系统"到"**前瞻式、设备状态感知的双向协调框架**"(预测提供未来网络状态,SoC/温度提供设备状态演化,统一为跨时间的状态感知协调)。这是 14 组样本中最强的一档叙事,但**门槛也最高:当前联合实验为零(证据账本 A6),统一性只是设想**。

## 7. Plum 与典型扩刊案例的差距

| 维度 | 典型 ToN 扩刊(已确认样本) | Plum 计划增量 | Plum 当前证据状态 |
|---|---|---|---|
| 新模块 | VF+/DPP/DYNAMIC,1 个,带独立节+实验 | Prediction + Green,2 个 | Pred 可信但口径受限;Green 3 seeds 初步 |
| 新理论 | FEDL 定理/OLIA 证明/AlignTrack 最优性 | T1 扰动界(设想)、T2(可选) | **无推导,零**——这是与 S-6/I-3 档案例最刺眼的差距 |
| 新场景/应用 | VF 两案例/Pudica 泛化 | 能耗-热新维度;(trace 多样性 P1-1) | Green 方向性结果;trace 单一 |
| 部署/真实性 | BOLA 生产部署/Pudica 百万级 | 无部署计划;E1 真机校准可补"真实性" | 能耗为文献锚定模型,92°C/20W artifact 未修 |
| 实验完备化 | GEMINI 全口径/Aeolus 消融 | 五对照两平台、≥10 seeds+CI | Green 3 seeds、全线无 CI、联合实验空白、无外部 SOTA baseline |
| 篇幅增量 | +20–45% 正文 | 两条线做完远超此量 | ——量不是问题,质(统一性+统计)才是 |

结论:
1. **计划体量足够,当前证据不够。** 若 P0 全部完成,Plum 增量= 2 个新模块 + 1 个新问题维度 + (若 T1 落地)新理论 + 五对照两平台——超过样本中任何单一案例的增量;但以**当前**状态(无联合实验、Green 3 seeds、无 CI、无新定理、能耗未校准)对照,连最弱的 I-1 档都未达到——I-1 至少有完整可信的实验数字。
2. **样本给出的隐性合格线**:至少一个"会议版出现次数为 0"的结构性新轴(模块/定理/应用)+ 完备实验。Plum 的 Green 天然满足"结构性新轴"判据(能耗/温度/存活指标在 ICNP 版中出现次数为 0);Prediction 需要失效边界+理论才算满轴。
3. **两条线不等于两倍增量**:样本中没有"两个松耦合模块拼一篇"的成功先例;所有多轴案例(I-2、S-4、S-5)的多个轴都服务同一主线故事。这从案例侧再次印证既有判断:**统一性(或明确的主从结构)是骨架问题,优先级最高。**

## 8. 推荐的 Plum→ToN 扩刊故事

**推荐:门槛化的方案 A(统一叙事),以 P0-2 联合实验为 4–6 周内的 go/no-go 判据;判据不过则果断落到方案 B(Green 主线,Prediction 降为带失效边界分析的次要节)。** 与既有文档(汇报 §9、缺口分析 §10)方向一致,案例侧补充的理由:

- **A 成立时的故事**(对标 TACK/FEDL 档):"Plum(ICNP'24)证明双向协调该做;期刊版回答**协调应当前瞻(foresighted)且设备状态感知(state-aware)**——反应式无状态协调会撞上容量滞后与设备耗尽两堵墙;我们引入未来网络状态(预测)与设备状态演化(SoC/温度),统一为跨时间的多目标协调框架。"贡献排序:①统一状态感知协调框架(含 D1 耦合机制);②预测的价值与失效边界(实验机理+T1 扰动界);③能耗/热感知机制与 QoE-能耗 Pareto;④联合实现与两平台五对照评估。
  - 标题即增量(§4 规律):如 "PLUM+: Foresighted and Energy-Aware Bidirectional Bandwidth Coordination under Half-Duplex Bottlenecks"(系统名入题,Zhuge 式;副词精确指向两个新轴)。
- **B 时的故事**(对标 Virtual Filter 档):"双向协调不只分带宽,还决定设备活多久、多热——Green-PLUM 把协调目标从 QoE 扩展为 QoE×存活×热稳定,并诚实量化画质代价(-42% 吞吐换存活翻倍)。"Prediction 保留为一节:+17% 的适用口径 + trace-driven 失效机理(呼应 R2-7 的"准确未必最好"),作为"何时值得前瞻"的边界分析——这比硬凑统一更诚实,也仍是合格的第 1+2 型副轴。
- 不推荐:A/B 都不选、把两条线并列平铺("我们做了预测,也做了节能")——正是样本中不存在的"拼盘"反模式,且 cover letter 的差异说明会很难写。
- **组内先例红利**:Zhuge(S-1)就是本团队 Bo Wang/Zili Meng/Mingwei Xu 的 SIGCOMM'22→ToN'25 扩刊,**投稿信怎么写差异说明、审稿几轮、新增了哪些章节,组内有一手经验,应直接请教**;这是本次调研发现的最可执行的一条捷径。

## 9. 下一阶段最重要的工作

(与缺口分析 P0 清单一致,按扩刊案例视角重排序;前两项决定论文骨架,必须最先做)

1. **P0-2 + D1:Pred+Green 联合实验与最小耦合机制**(五对照 Vanilla/Plum/Pred/Green/Pred+Green,两平台)。判据:Pred+Green 相对 Green 在能耗/存活/温度或 QoE 上有 CI 不重叠的增益 → 方案 A;否则 B。**这是 go/no-go,4–6 周内出结论。**
2. **P0-1:统计加固**。Green 3→≥10 seeds,全部结果补 95% CI 与显著性——样本合格线之下的硬伤,A/B 都必须。
3. **P0-3 + T1:预测失效边界机理 + 扰动界推导**(误差注入 ±10/20/30% + trace-driven 不敏感机理解释 + 灵敏度分析推导)。把 Prediction 从第 1 型升格为 1+2 型;对标 FEDL/AlignTrack 的理论增量。**T1 未推导成功前不得写为定理贡献**(沿用 draft 红线)。
4. **P0-4(E1/E2):能耗模型校准**。先做小工作量的 E2(92°C/20W 温度/功率模型修复),再补 E1(≥1 台真机功率计锚点)。Green 的所有主张以此为可信度前提。
5. **P0-7 + 投稿准备**:取得 seq312 全文确认竞争关系;**引用 Pudica 时须同时核对其 NSDI'24 会议版**(本次确认 ton0066 是扩展版,对比口径应以两版核对为准);按 ToN 政策起草 cover letter 差异说明(列 ICNP'24 + 公开链接 + 逐条增量),并向组内 Zhuge ToN 经验对齐。

## 10. 给老师的简洁结论

1. 本轮用 14 组可验证案例(ICNP 6 组为主)回答了"会议→ToN 通常加什么":**新模块/新理论/新场景/部署强化/实验完备化五型,强案例都是"结构性新轴+完备实验",纯加长版不存在成功先例;标题改动即增量声明。**
2. **ToN 官方没有 30% 门槛**,但要求 cover letter 差异说明 + 引用会议版;ICNP Best Paper 另有 fast-track(Plum 不适用,走常规通道,参照 GEMINI 预期多轮修订)。
3. Plum 对号入座:**Prediction = 新模块型(需配失效边界+扰动界升格),Green = 更实质的新问题维度型,统一成立则是最强档的框架升维**;计划体量超过典型案例,**当前证据(无联合实验、3 seeds、无 CI、无新定理、能耗未校准)尚不达样本合格线**。
4. 建议:**4–6 周内用 P0-2 联合实验做 A/B go/no-go**;A 讲"前瞻+状态感知的双向协调",B 讲"Green 主线+预测边界分析"。两案的统计加固、失效边界、能耗校准三件事完全共用,现在就可并行开工。
5. 可执行捷径:组内 Zhuge 就是 SIGCOMM→ToN 扩刊先例,直接请教其差异说明与审稿过程;引用 Pudica(ton0066)时注意它是 NSDI'24 扩展版,两版口径需核对。

---

## 附:案例证据索引(便于复核)

- I-1 GEMINI:期刊版 PDF baiwei0427.github.io/papers/gemini-ton.pdf(脚注原句);DOI 10.1109/TNET.2022.3161580。
- I-2 Virtual Filter:NSF 存档全文 par.nsf.gov/servlets/purl/10359270(脚注原句);ICNP'21 camera-ready icnp21.cs.ucr.edu/papers/icnp21camera-paper3.pdf;DOI 10.1109/TNET.2022.3182694。
- I-3 AlignTrack:DOI 10.1109/TNET.2023.3235041(Semantic Scholar/DBLP 双记录)。
- I-4 Proteus:DOI 10.1109/TNET.2024.3366336;fast-track 政策 icnp23.cs.ucr.edu/cfp.html;会议版 cse.hkust.edu.hk/~kaichen/papers/proteus-icnp23.pdf。
- I-5 GeneWave:作者发表页 tns.thss.tsinghua.edu.cn/~jiliang/publications.html(注意:其挂载的 "ton2018_genewave.pdf" 实为会议版式文件,不可作期刊排版稿证据)。
- I-6 CDN Transit:IEEE 7784432(会议)/8114214(期刊)。
- S-1 Zhuge:DOI 10.1145/3544216.3544225(SIGCOMM'22)/10.1109/TNET.2024.3502822(ToN'25);zilimeng.com/papers.html、bowangthu.github.io 并列记录。
- S-2 Pudica:usenix.org/conference/nsdi24/presentation/wang-shibo;DOI 10.1109/TON.2024.3519902(注意新刊名 TON 前缀)。
- S-3 TACK:DOI 10.1145/3387514.3405850 / 10.1109/TNET.2021.3101011;litonglab.com 项目页并列两版。
- S-4 BOLA:arXiv:1601.06748 v1/v3 脚注原句与 comments 字段;DOI 10.1109/TNET.2020.2996964。
- S-5 Aeolus:期刊版脚注原句 "The earlier idea of Aeolus was presented in [9],[10]";两版全文 baiwei0427.github.io/papers/aeolus-{sigcomm2020,ton}.pdf。
- S-6 FEDL:arXiv:1910.13067 脚注原句;DOI 10.1109/TNET.2020.3035770。
- S-7 AoI:技术报告 sites.northwestern.edu/kadota/files/2023/08/2019ToNTechRep.pdf 脚注原句;DOI 10.1109/TNET.2019.2918736。
- S-8 OLIA:CoNEXT'12 DOI 10.1145/2413176.2413178;ToN DOI 10.1109/TNET.2013.2274462。
- 政策:comsoc.org/publications/journals/ieee-tnet/ieee-transactions-networking-author-guidelines;comsoc.org …/conference-vs-journal-papers(30% 辟谣);journals.ieeeauthorcenter.ieee.org …/submission-and-peer-review-policies;IEEE PSPB Ops Manual §8.1.7.E。
- 排除清单(防误用):SQR、CloakLoRa、HotDASH、SCIONLab 无 ToN 版;**FTrack 会议版是 SenSys'19 非 ICNP**(检索工具曾错报);HPCC 无 ToN 版(后续为 IETF draft);TACK "新增 IACK" 说法未确认不采信。
