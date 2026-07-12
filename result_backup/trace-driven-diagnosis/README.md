# Trace-Driven 诊断:为什么带宽预测没效果

## 这张图是什么 (`diag_three_lines.png`)

跑了**一次** trace-driven 仿真,把每个 client 的三条曲线画出来:

- **绿线 = 真实带宽**(trace 里的真实值,代码里叫 oracle;**只用来对照,绝不参与任何决策**)
- **蓝线 = 系统自测带宽**(BBR,即 client/server 实际用来做带宽分配的量)
- **红线 = 预测带宽**(Transformer 的输出)

横轴 = 第几个测量周期(服务端每个周期打印一次这三个数;日志没带时间戳,所以用周期序号当横轴)。单位 Mbps。

## 怎么测出来的(可复现)

1. 跑仿真(瓶颈压在 WiFi、开详细日志、跑够时间攒预测点):
   ```bash
   # 先起 solver 和推理服务(见 result_backup 上层说明),再:
   cd emulation/ns-allinone-3.37/ns-3.37
   NS_GLOBAL_VALUE="RngRun=1" ./ns3 run "scratch/test_half_duplex --mode=sfu \
     --logLevel=1 --simTime=300 --policy=2 --nClient=3 --varyBw=1 \
     --traceMode=1 --seed=1 --dataset=0 --serverBtl=1000 --mlpred=1" > diag_full.log 2>&1
   ```
2. 抽出服务端三线日志:
   ```bash
   grep "VcaServer.*Transformer" diag_full.log > diag_pred.txt
   ```
   (日志行形如:`[VcaServer] Client 0 | BBR: 18546.5 | Transformer: 16742.7 | oracle: 12165 | Final: 17825`)
3. 画图 + 算统计:
   ```bash
   python3 plot_diag.py   # 读 diag_pred.txt,生成 diag_three_lines.png 并打印下表
   ```

## 定量结果 (单位 Mbps)

| client | 自测(BBR)均值 | 自测 CoV(波动率) | 真实均值 | 真实 CoV | corr(自测, 真实) |
|---|---|---|---|---|---|
| 0 | 18.71 | **0.02** | 9.64 | 0.53 | **−0.02** |
| 1 | 23.02 | 0.10 | 9.64 | 0.53 | 0.42 |
| 2 | 25.29 | 0.10 | 9.64 | 0.53 | 0.30 |

- CoV = 标准差/均值,越大越"波动"。真实带宽 CoV=0.53(剧烈起伏),自测只有 0.02~0.10(几乎平线)。
- corr(自测, 真实):Client 0 ≈ 0,自测和真实**毫无关系**;Client 1/2 也只有 0.3~0.4(弱相关)。
- 自测均值(19~25)是真实均值(9.6)的约 **2 倍**——严重高估。

## 结论

**问题不在预测器,而在更前一步:系统自测的带宽是错的。**
真实带宽(绿)在 4~24 Mbps 剧烈起伏,而系统自测(蓝)又高约 2 倍、又几乎是平线,基本"看不见"真实的波动。预测器(红)只是忠实地跟着这条平的错线走 —— **垃圾进,垃圾出**。

这也解释了 Model-Based 有效、Trace-Driven 无效:Model-Based 里自测能跟上带宽变化,Trace-Driven 里自测瞎了。

## 下一步

不引入上帝视角的前提下,让系统"测得准一点":用它合法可观测的信号(实际收到的速度、RTT、丢包 —— trace 里有 rtt/lossrate 两列)重建一个能反映真实起伏的观测量,再喂给预测器。先查清为什么同样的 BBR 测法在 trace-driven 里变平、还高 2 倍。
