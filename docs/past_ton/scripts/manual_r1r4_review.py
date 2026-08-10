#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manual DOI-level review of the PLUM-related candidates.
Automatic keyword matching never grants R1/R2. This script promotes the 17
manually reviewed DOI records to R2 and leaves all other records at R3/R4."""
import csv, os
BASE="/home/xuzy/Plum-for-award/Plum/docs/past_ton"
P=os.path.join(BASE,"ton_2025_2026_catalog_v2.csv")

MAN = {
 "10.1109/ton.2025.3615604":("R2","边缘多路视频推理的双层带宽协调，是目前最接近的带宽协调工作；无全文，尚不能称为直接竞争或确认可作baseline"),
 "10.1109/ton.2025.3577974":("R2","Conflux多链路ABR，与Plum同为应用层码率协调但维度不同(多链路vs双向)"),
 "10.1109/ton.2024.3519902":("R2","Pudica低延迟交互视频单向CC，与Plum双向协调互补"),
 "10.1109/ton.2025.3589553":("R2","INCC主动瓶颈感知CC，方法可借鉴Plum服务器侧协调"),
 "10.1109/ton.2025.3638882":("R2","异构CC下多流QoE公平带宽分配，与Plum公平性目标相关"),
 "10.1109/ton.2025.3646971":("R2","5G RAN×QUIC×ABR跨层分析；OA全文已精读"),
 "10.1109/ton.2025.3650266":("R2","NeuroBA神经符号ABR；OA全文已精读"),
 "10.1109/ton.2026.3651621":("R2","BIFROST关注解耦CDN-CC，与Plum不侵入CC的思路相关"),
 "10.1109/ton.2026.3653773":("R2","多智能体DRL CC追求公平收敛，可借鉴多终端公平方法"),
 "10.1109/ton.2026.3655983":("R2","FAR数据中心速率控制，提供rate-control方法论对照"),
 "10.1109/ton.2026.3661954":("R2","边缘码率再适配说明预测精度不等于QoE提升"),
 "10.1109/ton.2026.3663789":("R2","Compass反馈延迟与控制失效问题和Plum容量检测相关"),
 "10.1109/ton.2026.3671076":("R2","移动设备FL能耗拆分可用于Green-PLUM能耗建模对照"),
 "10.1109/ton.2026.3686751":("R2","商用5G远程驾驶为双向体积流提供应用动机"),
 "10.1109/ton.2026.3687061":("R2","AraLivePro研究学习式直播码率控制"),
 "10.1109/ton.2025.3581531":("R2","QoE-UAV-MEC能耗约束在线优化，可借鉴能耗-性能建模"),
 "10.1109/tnet.2024.3492096":("R2","Libra是面向多样应用偏好的拥塞控制框架，提供方法对照"),
}

rows=list(csv.DictReader(open(P,encoding="utf-8")))
bydoi={r["doi"].lower():r for r in rows}
touched=0
for doi,(lvl,reason) in MAN.items():
    if doi in bydoi:
        bydoi[doi]["relevance_level"]=lvl
        bydoi[doi]["relevance_reason"]=reason
        bydoi[doi]["manually_verified"]="True"
        touched+=1
# write back preserving column order
cols=list(rows[0].keys())
with open(P,"w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
    for r in rows: w.writerow(r)
print("manual DOI review applied: %d/%d records"%(touched,len(MAN)), flush=True)
from collections import Counter
c=Counter(r["relevance_level"] for r in rows)
mv=sum(1 for r in rows if r["manually_verified"]=="True")
print("final relevance: R1=%d R2=%d R3=%d R4=%d | manually_verified=%d"%(c.get("R1",0),c.get("R2",0),c.get("R3",0),c.get("R4",0),mv),flush=True)
# list final R1/R2 with reasons
print("\n=== FINAL R1 ===")
for r in rows:
    if r["relevance_level"]=="R1":
        print(" seq",r["sequence_id"],r["doi"],"|",r["title"][:55])
print("=== FINAL R2 ===")
for r in rows:
    if r["relevance_level"]=="R2":
        print(" seq",r["sequence_id"],r["doi"],"|",r["title"][:55])
