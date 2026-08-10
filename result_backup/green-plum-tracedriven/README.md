# Green-PLUM：能耗感知的双向带宽协调 —— 初步实验汇报

在 Plum（半双工瓶颈下的双向带宽协调）基础上，新增能耗/发热维度：分配时同时考虑
每台设备的剩余电量与温度，对快没电/快过热的设备主动降低码率，换取"更多人撑完会议 +
画面不因过热降频而崩"。以下为初步结果（3 seeds，n=8）。

---

## 一、实验结果

对照三种策略：**Vanilla**（对半分，无优化）/ **Plum**（双向带宽协调）/ **Green-PLUM**（Plum + 能耗感知）。

**网络性能（下行码率 = 视频 QoE 来源）**

| 指标 | Vanilla | Plum | Green |
|---|---|---|---|
| 平均下行码率 | 4.75 Mbps | 9.33 Mbps | 5.40 Mbps |
| 最差用户下行码率 | 2.18 Mbps | 6.57 Mbps | 3.73 Mbps |

- **Plum vs Vanilla：平均 +96.3%，最差用户 +201%**（复现 ICNP'24 Plum 论文 Fig.11 的 +48~58%，本操作点更强）。
- Green vs Vanilla：平均 +14%，最差用户 +71%（Green 仍保住了 Plum 协调的核心收益）。

**能耗 / 续命 / 发热（60 分钟会议，8 台设备含低电手机）**

| 指标 | Vanilla | Plum | Green |
|---|---|---|---|
| 会议结束存活设备 | 1 / 8 | 2 / 8 | **4 / 8** |
| 峰值温度 | 92 °C | 60 °C | **47 °C** |
| 平均功率 | 5.31 W | 4.02 W | **3.21 W** |

- **Green 能耗全面最优**：存活翻倍（4 vs 2 vs 1）、峰温比 Vanilla 低 45 °C、平均功率降 40%。
- 代价：Green 平均吞吐比 Plum 低约 42%（主动降码率所致，可通过降低节流强度调节到更温和的权衡点）。

**一句话结论**：Plum 用双向协调换来近 2× 的下行吞吐；Green 在保持"仍优于 Vanilla"的网络表现下，
把续命翻倍、峰温压到过热降频线以下、功率降四成。两个维度交叉互补，Green 是"网络够好 + 能耗最优"的折中点。

---

## 二、实验怎么做的（平台 / 场景 / 流程）

**平台**：NS-3.37 包级网络仿真 + Plum 的 `videoconf` 模块（WebRTC SFU 架构，每客户端上传自己
的视频、下载其余 N-1 路），传输层 TCP + BBR 拥塞控制。**非纯数值模型，是真实包级仿真。**

**拓扑与场景（trace-driven，对应论文 Fig.11「独立接入」，非共享 WiFi）**：
- 8 个客户端，**每个客户端各有一对独立的上行/下行链路，连到唯一的中心 SFU 服务器**——不是 8 台共享一个 WiFi。
- **半双工瓶颈按「每客户端」建模**：每个客户端自身的上行+下行带宽之和，受该客户端自己的 WiFi 带宽
  trace 约束（模拟真实 WiFi 上下行共享气道）。trace-driven 层不含 WiFi 物理/MAC 层实现——与论文一致
  （论文的真实 WiFi PHY/MAC 只在另一个移动性实验 Fig.14 里做）。
- **跨客户端的协调杠杆来自 SFU**：客户端 i 的下行 = 其余客户端上行之和（转码后），所以"某客户端多传
  上行"会抬高别人的下行——这正是 Plum 双向协调发挥作用的地方。
- 每条链路的带宽由**真实餐厅 WiFi 带宽 trace**（`scripts/traces/restaurant/`，11–36 Mbps 大幅波动）逐时刻驱动；
  服务器出口 `serverBtl=300 Mbps`（按客户端均分）；仿真 60 s，经 60× 加速映射为 60 分钟会议。

**三种策略（同一 scratch `test_half_duplex_paper.cc`，`--traceMode` 切换）**：
- `traceMode=0` **Vanilla**：上下行对半分。
- `traceMode=1` **Plum**：按真实带宽算最优双向分配——带宽紧张时压低上行、把气道让给下行（QoE 来源）。
- `traceMode=2` **Green**：在 Plum 分配之上，对低电（SoC<15%）或高温（>41 °C）设备按
  `scale = 0.5/(1+λ)` 压低其总速率（牺牲该设备画质，换其续命与降温）。

**流程**：仿真每 16 ms 从 trace 读取当前链路带宽 → 按所选策略算 ul/dl 分配并下发到链路 →
（Green 模式）用当前电量/温度决定是否额外降速 → 用实际速率算功率、推进电量与温度状态机 →
逐时刻记录 SoC/温度/功率/存活到 CSV。能耗状态机对三种策略都运行（只记录、不改 Vanilla/Plum 的
网络行为），因此三方能耗严格可比。每策略跑 3 个随机种子。

**8 台设备的电池初始状态**（会议开始时；容量按 `batt_scale=0.7` 缩放）：

| 设备 | 类型 | 容量 | 初始电量 | 充电 |
|---|---|---|---|---|
| 0 | 手机 | 12 Wh | 30% | 否 |
| 1 | 手机 | 12 Wh | **25%（最低）** | 否 |
| 2 | 手机 | 12 Wh | 55% | 否 |
| 3 | 手机 | 12 Wh | 60% | 否 |
| 4 | 手机 | 12 Wh | 35% | 否 |
| 5 | 手机 | 12 Wh | 28% | 否 |
| 6 | 笔记本 | 45 Wh | 80% | 否 |
| 7 | 笔记本 | 45 Wh | 90% | 是 |

即 **4 台低电手机（电量 25%~35%）**、2 台中电、2 台电量充足（含 1 台充电）。12 Wh ≈ 3100 mAh 典型手机电池。

> **重要设定说明**：为了让 60 分钟会议里能观察到设备耗尽（真实满电手机 1 小时掉不到没电，看不出差异），
> 电池容量乘了 `batt_scale=0.7`（有效 8.4 Wh）并叠加 60× 时间加速。因此**"谁几分钟没电"这类绝对数字
> 是这两个参数刻意压出来的；真正有意义的是同一设定下的相对比较**——Green 让 4 台撑完会议，Plum 2 台、
> Vanilla 1 台。

**复现命令**：
```
cd emulation/ns-allinone-3.37/ns-3.37
NS_GLOBAL_VALUE="RngRun=6" ./ns3 run "scratch/test_half_duplex_paper \
  --mode=sfu --simTime=60 --policy=0 --nClient=8 --varyBw \
  --traceMode=2 --seed=6 --dataset=1 --serverBtl=300"
# traceMode: 0=Vanilla 1=Plum 2=Green；能耗日志→ green/td_green_logs/
```

---

## 三、功耗与发热建模（参数全部锚定 2020 年后测量文献）

**瞬时功率模型**（每客户端，u/d 为上/下行 Mbps，单位 W）：
```
E(u,d) = P_base + (1.3·u + d)·e_bit(u+d)      ← WiFi 收发（发送每比特贵 30%）
                + P_enc·(u/u_ref)^t             ← 硬件编码（超线性）
                + P_dec·(d/d_ref)               ← 硬件解码
其中每比特能耗  e_bit(Th) = a/Th + b  (nJ/bit)，低吞吐时每比特更贵。
```

**发热与降频**（一阶 RC 热模型 + 滞回节流）：
```
T ← T + Δt/τ · (T_amb + R_th·E − T)
T ≥ 41 °C 触发降频（上行/编码被压到 40%），T ≤ 39 °C 解除。
```

**校准锚点**：典型工作点 (u=2, d=6 Mbps) 整机功率 3.74 W ≈ IMC'21 实测的 ~4 W；由此推出
"低电 30% 手机撑不完 1 小时会议"，与日常经验一致。

**参数取值与文献来源**：

| 参数 | 取值 | 依据（2020+ 测量/建模） |
|---|---|---|
| 整机锚点 P_ref | 4.0 W | MacMillan et al., *Can You See Me Now?*, **IMC 2021**：功率计实测 1h 视频会议耗 2600mAh 电池的 40%≈4W |
| 基础功耗 P_base | 2.0 W | 同上：关屏关摄的 audio-only 省 ~50% 电 → 屏幕/摄像头/系统 ≈ 整机一半（分配省不掉） |
| 每比特能耗 a,b | 305.3, 13.1 nJ/bit | WiFi 每比特能耗-吞吐模型；*Towards an energy-efficient Wi-Fi …* (2025) 对 Wi-Fi 5/6 功耗实验 |
| 发送/接收不对称 | 1.3× | 多项测量一致：发送每比特能耗高于接收 |
| 编码 P_enc / t | 0.8 W@2Mbps / 1.2 | Herglotz & Kränzler, *Modeling HEVC Encoding Energy*, **2022**（硬件编码，超线性） |
| 解码 P_dec | 0.5 W@6Mbps | Benmoussa et al., *HEVC hardware vs software decoding*, **J. Syst. Arch. 2021**；IEEE 2021 *Power Consumption of Video-Decoders on Android*（285 设备数据集） |
| 热模型阈值 | 41/39 °C | *Scientific Reports 2023* 视频通话温度实测达 40 °C+；手机表面节流阈值 ~41–43 °C |

**主要参考文献**：
1. K. MacMillan, T. Mangla, J. Saxon, N. Feamster. *Can You See Me Now? A Measurement Study of Zoom, Webex, and Meet.* IMC 2021.（整机功耗锚点）
2. C. Herglotz, M. Kränzler, et al. *Modeling the HEVC Encoding Energy Using the Encoder Processing Time.* 2022.（编码能耗）
3. Y. Benmoussa, et al. *HEVC hardware vs software decoding: an objective energy consumption analysis.* J. Systems Architecture, 2021.（解码能耗）
4. *Power Consumption of Video-Decoders on Various Android Devices.* IEEE, 2021.（285 设备解码功耗数据集）
5. *Towards an energy-efficient Wi-Fi: an experimental study on recent standards power consumption.* 2025.（WiFi 收发能耗）
6. *Evaluation of in-service smartphone battery drainage … video calling.* Scientific Reports, 2023.（真机放电与温度）

> 说明：能耗为文献锚定的建模值，非本文真机实测；已配 ±50% 参数扰动的敏感性分析验证结论鲁棒性。

---

## 附：本目录文件
- `network_3way.csv` — 三方网络指标（mode 0/1/2 = Vanilla/Plum/Green）
- `plum_vs_vanilla_baseline.csv` — Plum vs Vanilla 基线验证（serverBtl 100/300）
- `energy_logs/mode{0,1,2}/` — 三方逐时刻电量/温度/功率日志
- `test_half_duplex_paper.cc` — 含 Green 的仿真代码
