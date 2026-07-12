#!/usr/bin/env python3
# 读 diag_pred.txt(服务端三线日志),画 diag_three_lines.png 并打印每 client 统计。
import re, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

PAT = re.compile(r'Client (\d+) \| BBR: ([\d.]+) \| Transformer: ([\d.]+) \| oracle: ([\d.]+) \| Final: ([\d.]+)')

data = {}
for ln in open('diag_pred.txt'):
    m = PAT.search(ln)
    if not m:
        continue
    c = int(m.group(1))
    vals = [float(m.group(i)) / 1000. for i in (2, 3, 4, 5)]  # kbps -> Mbps
    data.setdefault(c, []).append(vals)

print("=== per-client stats (Mbps) ===")
print(f"{'cli':>3} {'N':>4} | {'BBR mean':>8} {'BBR CoV':>7} | {'true mean':>9} {'true CoV':>8} | {'corr(pred,BBR)':>14} {'corr(BBR,true)':>14}")
fig, axes = plt.subplots(len(data), 1, figsize=(14, 3.2 * len(data)), squeeze=False)
for idx, c in enumerate(sorted(data)):
    a = np.array(data[c]); bbr, pred, orc = a[:, 0], a[:, 1], a[:, 2]
    cb = np.corrcoef(pred, bbr)[0, 1] if bbr.std() > 0 and pred.std() > 0 else float('nan')
    co = np.corrcoef(bbr, orc)[0, 1] if bbr.std() > 0 and orc.std() > 0 else float('nan')
    print(f"{c:>3} {len(a):>4} | {bbr.mean():8.2f} {bbr.std()/bbr.mean():7.2f} | {orc.mean():9.2f} {orc.std()/orc.mean():8.2f} | {cb:14.3f} {co:14.3f}")
    ax = axes[idx][0]
    ax.plot(orc, label='true (oracle, log-only)', color='green', lw=1.2)
    ax.plot(bbr, label='self-measured (BBR)', color='C0', lw=1.0, alpha=0.8)
    ax.plot(pred, label='Transformer pred', color='red', lw=1.0, alpha=0.8)
    ax.set_title(f'Client {c}  (x=prediction cycle index)'); ax.set_ylabel('Mbps')
    ax.legend(fontsize=8, ncol=3)
plt.tight_layout(); plt.savefig('diag_three_lines.png', dpi=130, bbox_inches='tight')
print("saved diag_three_lines.png")
