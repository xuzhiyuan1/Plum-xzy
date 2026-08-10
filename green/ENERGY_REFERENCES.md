# Green-PLUM 能耗参数的文献来源（2020 年以后的工作）

> 能耗建模基于 **2020+ 的测量/建模文献**，整机功耗校准到 IMC'21 的硬件实测锚点。
> 不做真机实测；数值为文献支持的代表值，配敏感性分析（fig_D）兜底。

## 能耗模型（每客户端，瞬时功率 W）
$$E_i(u,d) = P_{base} + \underbrace{(1.3u + d)\cdot e_{bit}(u+d)}_{\text{WiFi网络}} + \underbrace{P_{enc}\!\left(\tfrac{u}{u_{ref}}\right)^{t}}_{\text{硬件编码}} + \underbrace{P_{dec}\tfrac{d}{d_{ref}}}_{\text{硬件解码}}$$
其中 $e_{bit}(Th) = a/Th + b$ (nJ/bit)。

**校准**：典型工作点 (u=2, d=6 Mbps) 整机 3.74 W ≈ IMC'21 实测 ~4 W ✔

## 参数与 2020+ 来源

| 参数 | 取值 | 依据（2020+） |
|---|---|---|
| 整机锚点 `Pref` | 4.0 W | **MacMillan et al., "Can You See Me Now? A Measurement Study of Zoom, Webex, and Meet", IMC 2021** (arXiv:2109.13113)：Monsoon 功率计实测，**1 小时视频会议耗 2600mAh(≈10Wh) 电池的 40% ≈ 4W**；三大 app 相差 <10%。 |
| `Pbase` | 2.0 W | 同上 IMC'21：**audio-only(关屏关摄) 省 ~50% 电** → 屏幕/摄像头/系统等"分配省不掉"的基础功耗 ≈ 整机一半。 |
| `e_bit = a/Th+b` | a=305.3, b=13.1 nJ/bit | WiFi 每比特能耗-吞吐模型（2022 年工作复用于 Nexus 实测拟合）；另见 **"Towards an energy-efficient Wi-Fi: an experimental study on recent standards power consumption" (2025)** 对 Wi-Fi 5/6 新标准的功耗实验。 |
| `tx_asym` | 1.3 | 多项测量一致：发送每比特能耗高于接收（TCP 收发效率比 ≈ 6:4.63）。 |
| `Penc0` | 0.8 W @2Mbps | 现代手机为**硬件编码**：**Herglotz/Kränzler 组, "Modeling the HEVC Encoding Energy", 2022** (arXiv:2207.02676) 等编码能耗建模；硬编远低于 2010 年代软件编码。 |
| `t_enc` | 1.2 | 同上系列：编码能耗随码率/复杂度超线性。 |
| `Pdec0` | 0.5 W @6Mbps | **Benmoussa et al., "HEVC hardware vs software decoding", J. Systems Architecture 2021**：硬解显著低于软解；**IEEE 2021 "Power Consumption of Video-Decoders on Various Android Devices"**：285 台设备×6 种标准(AV1/HEVC/VP9/H.264...)解码功耗数据集。 |
| 电池容量 | 手机 12 Wh(≈3200mAh)/笔记本 45 Wh | 现代手机 3000–4200mAh；IMC'21 实验机 2600mAh 同量级。 |
| 场景现实性 | 低电 30% 手机撑不完 1h 会议 | 由 IMC'21 "1h 耗 40%"直接推出：30%×12Wh=3.6Wh < 3.74Wh ✔ |
| `λ=k(1-SoC)^m` | k=1.5, m=2 | 设计式（有界，替代 k/batt 避免低电爆炸）；充电设备 λ=0。 |

## 完整文献列表
1. K. MacMillan, T. Mangla, J. Saxon, N. Feamster. *Measuring the Performance and Network Utilization of Popular Video Conferencing Applications* / "Can You See Me Now?" IMC 2021. arXiv:2109.13113.
2. C. Herglotz, M. Kränzler, et al. *Modeling the HEVC Encoding Energy Using the Encoder Processing Time.* 2022. arXiv:2207.02676（及同组 HEVC 解码能耗建模 arXiv:2203.00466）.
3. Y. Benmoussa, et al. *HEVC hardware vs software decoding: An objective energy consumption analysis and comparison.* Journal of Systems Architecture, 2021.
4. *Power Consumption of Video-Decoders on Various Android Devices.* IEEE, 2021（285 设备/147 机型解码功耗数据集）.
5. *Towards an energy-efficient Wi-Fi: An experimental study on recent standards power consumption.* 2025.
6. L. Wattenbach et al. *Do you have the energy for this meeting?* MOBILESoft 2022（Meet/Zoom Android 能耗）.
7. *Evaluation of in-service smartphone battery drainage profile for video calling feature in major apps.* Scientific Reports, 2023（8 app 视频通话硬件放电实测）.

## 相比旧版(2009-2012文献)的关键修正
- **加入 P_base(≈2W, 占一半)**：屏幕/摄像头/系统的电"分配省不掉"→ 可省空间从"大半"修正为 **~28%**，结论更收敛更可信。
- 编解码从"软件编码 2-3W"修正为"**硬件编解码** 0.5-0.8W"（现代手机现实）。
- 网络从固定 Ptx/Prx 修正为 **每比特能耗-吞吐模型**（低吞吐时每比特更贵）。
