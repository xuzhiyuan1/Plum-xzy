# Trace-Driven 带宽预测:断因果循环 + 探究预测为何不见效(夜间自动探索报告)

> 本文件记录一整夜的自动探索。**所有改动都在 `--sharedbw`/`--diagbw`/`--predfilter` 开关后,默认全关 = 原版行为一字不变。**
> 结论一句话:**死循环已断、观测已能做干净(两个真成果);但预测仍不提升吞吐,原因比"模型不好"更深——见 §5。关键图:`td_final.png`。**

---

## 1. 目标
1) 摒弃因果循环;2) 在 trace-driven 下证明"加带宽预测 → 吞吐↑、QoE↑";3) n∈{3,4,6}×多seed 聚合出图。

## 2. 因果循环问题(用户点破)
`total_bw`(=C)经 `BandwidthTrace()` 进系统时,被**按上下行分配比例切成两条 P2P 链路限速**;比例来自求解器(观测→预测→比例)。于是 `比例→管子→观测→预测→比例` 死循环,系统看不到没被比例动过的真实带宽。

## 3. 尝试全记录(含失败)
| # | 改法 | 结果 |
|---|---|---|
| 1 | 观测换"服务端收到的 UL 速率" | ❌ 被压制流少发就测不到;被比例污染 |
| 2 | sharedbw v1 `ul_bw=C−dl_used,dl_bw=C−ul_used`(互耦) | ❌ 振荡(用量≈限速,分不清"不想要"vs"被卡住") |
| 3 | CSMA 真共享介质 | ❌ 排除:CsmaNetDevice 启动缓存信道速率、无 setter,不能每16ms改速率 |
| 4 | **sharedbw v2 `ul_bw=C; dl_bw=max(floor,C−ul_used)`**(单向不振荡) | ✅ **total_used≈C (tot/C=0.97~1.09)** |
| 5 | 观测换"实际送达总吞吐"喂服务端取代 pacing | ✅ 量级对了(Client0 从18546→4214≈真实) |
| 6 | 健壮性:clamp 预测/容量≥0 + ns-3 忽略 SIGPIPE | ✅ 修好负预测→负容量→solver断连→SIGPIPE 崩溃 |
| 7 | 对比 mlpred=0 vs 1(Transformer) | ➖ **平手**(±1~4% 噪声,无提升) |
| 8 | 去 EWMA 喂原始带噪观测让预测去噪 | ➖ 仍平手 |
| 9 | **预测精度诊断**(pred vs persistence) | ❗ **Transformer 比 persistence 差 11.5%** |
| 10 | 离线对比 persistence/EWMA/median/Transformer | ❗ **简单滤波比 persistence 准 ~19%;Transformer 最差** |
| 11 | 用中位数滤波代替 Transformer 当预测器,重跑吞吐 | ➖ **仍平手**(seed1/2略低,seed3平) |

## 4. 两个真成果
- **断循环**:`BandwidthTrace` 里 `ul_bw=C; dl_bw=max(floor,C−上行实际送达)`。上行不与下行互耦→稳定;下行补剩余→**总送达吞吐守恒≈C**;分配交给发送端(Plum已有)→ **不再用求解器比例切管子,死循环断开**。实测 tot/C=0.97~1.09。
- **干净观测**:两条链路 PhyTxEnd 计数之和 → 发布 `g_observed_cap_kbps`,服务端拿它当容量观测取代虚高 pacing。喂给预测器的信号量级正确、随真实带宽起伏(不再是又高又平的 pacing)。

## 5. 核心结论:为什么预测还是不提升吞吐(比"模型差"更深)
两层原因(见 `td_final.png`):

**(A) 当前 Transformer 确实没做好** —— 对真实噪声 trace,它的 1-step 预测比 persistence(直接用当前值)还差 11.5%;而简单 EWMA/中位数滤波比 persistence 准 ~19%。**你"滤波提取hidden→预测更准"的思路是对的,但现有 Transformer 是四者里最差的**(很可能因为它在合成分段平稳数据上训练,与真实噪声 trace 域差大)。

**(B) 更根本:干净观测下,吞吐被容量本身卡死,预测无处加价。** 这是关键:
- **model-based 能 +17%,是因为那里的 BBR 观测滞后/低估**,reactive 没吃满容量;预测抢回了 reactive 漏掉的那部分容量 → 吞吐涨。**预测的价值 = 补偿观测的滞后/低估。**
- 我把观测做干净后(送达≈C),reactive **已经吃满 C**,吞吐就是 C;"漏掉的容量"没了,**预测再准也无可抢**。
- 且"送达吞吐"观测是**自限的**(发多少看多少、不主动往上探),reactive 与滤波都卡在同一水平——所以连中位数滤波都没能拉高吞吐。

**含义**:把观测做"干净"这件事,反而抹掉了预测原本要填的那个 gap。要在 trace-driven 复现 model-based 的收益,**需要一个"会主动探测但会滞后"的容量观测**(像 BBR 那样探测,但不被比例污染),让 reactive 因滞后而低估、预测因前瞻而抢回——这正是 model-based 的机制。纯"送达吞吐"观测不具备这个性质。

## 6. 建议的下一步(给你决策)
1. **换观测为"探测型且带滞后"**:在断了循环的 sharedbw 模型上,保留一个会主动探测带宽的估计(如让 BBR 在共享链路上正常探测,或用 delivered+headroom 主动探测),使 reactive 会低估、预测能前瞻抢回。这是最可能复现 +17% 的路。
2. **重训 Transformer**:至少要打得过简单中位数滤波(现在反而最差)。用真实 trace 的观测信号微调;或先验证"滤波型预测"在探测型观测下能否提升吞吐,再上 Transformer。
3. **换 QoE 敏感的指标/场景**:若吞吐天然被容量卡住,考虑用能体现"及时性/稳定性"收益的指标(卡顿、RTT、码率波动)。

## 7. 复现(默认关,不影响原版)
```bash
# 起 solver -n N,再:
cd emulation/ns-allinone-3.37/ns-3.37
NS_GLOBAL_VALUE="RngRun=$SEED" ./ns3 run "scratch/test_half_duplex --mode=sfu --logLevel=0 \
  --simTime=120 --policy=2 --nClient=$N --varyBw=1 --traceMode=1 --seed=$SEED --dataset=0 \
  --serverBtl=1000 --mlpred=0|1 --sharedbw=1 [--predfilter=1] [--diagbw=1]"
```
- `--sharedbw=1` 共享模型(断循环+干净观测);`--diagbw=1` 打 [SharedDiag] 三线诊断;`--predfilter=1` 用中位数滤波代替 Transformer。
- 数据:`sweep.csv`(reactive vs Transformer)、`sw3.csv`(reactive vs medianpred)、`acc_pred.txt`(精度原始日志)。

## 8. 改动文件(均默认关/log-only)
- `emulation/scratch/test_half_duplex.cc`:`--sharedbw/--diagbw/--predfilter`、PhyTxEnd 计数、发布 `g_observed_cap_kbps`、忽略 SIGPIPE。
- `emulation/videoconf/model/vca_server.cc`:用 `g_observed_cap_kbps` 当观测、clamp、中位数滤波选项、三线日志。
- `emulation/videoconf/model/vca_client.cc`:clamp 预测。
- `test_wifi_channel.cc`/`test_half_duplex_w_share_ap.cc`:补全局符号定义(链接)。

## 9. 图
- `td_final.png` —— 主图:左=四种预测器精度(简单滤波<persistence<Transformer);右=三种条件吞吐全平手。
- `td_finding.png` —— 精度 vs 吞吐 双联图(早期版)。
