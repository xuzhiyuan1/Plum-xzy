# docs/past_ton/scripts 文献处理脚本

所有脚本在 `school-server` 上以 `zsh -lic "python3 <script>"` 运行（需登录 shell 以加载 PATH）。
缓存目录 `../cache/`，产物在 `../`（catalog_v2.csv / references_v2.bib / download_manifest_v2.csv）。

## 脚本清单

| 脚本 | 作用 |
|---|---|
| `fetch_openalex_newton.py` | 抓取新期刊源 OpenAlex S5407042750（e-ISSN 2998-4157）全量 works 到 `../cache/openalex_newton_all.json`。page-based 分页。 |
| `build_catalog_v2.py` | 以缓存的 Crossref 新 ISSN 数据为主，OpenAlex 增强（摘要/OA），DBLP XML 交叉校验。生成 catalog_v2.csv / references_v2.bib / download_manifest_v2.csv，并回填已下载 PDF 的路径与 SHA-256。区分 formal/EA/uncertain/non-research，不伪造缺失的月或日。 |
| `manual_r1r4_review.py` | 人工复核 auto-classified R1/R2 候选，按 R1/R2/R3/R4 重分级并写 relevance_reason、manually_verified=True。 |
| `download_oa_pdfs.py` | 按 download_manifest 下载 OA PDF，每 50 篇一 chunk，校验 %PDF/file/pdfinfo/SHA-256，断点续传。 |
| `catalog_stats.py` | 计算 catalog_v2 统计（status/volume/year/relevance 分布）。 |

## 数据源优先级（与任务一致）
1. IEEE Xplore（反爬，仅作人工核验，不抓取）
2. Crossref API，新旧 ISSN 分别查询：新 2998-4157（2025+）、旧 1063-6692（历史，仅到 2024-12）
3. DBLP XML（ton33/ton34）
4. OpenAlex（source S5407042750 新 / S62238642 旧）
5. 作者主页 / arXiv / HAL（OA PDF）

## 关键修正（相对 v1）
- 上一轮错误结论"Crossref/OpenAlex 只到 2024"系因用旧 ISSN。新 ISSN 2998-4157 下 Crossref 有 2025/2026 全量数据。
- 期刊 2025 起更名 "IEEE Transactions on Networking"，新 e-ISSN 2998-4157。
- 重要：Crossref 缺少 issue 不能单独证明 Early Access。已有 volume 和真实页码时按正式分页论文处理；`volume=34, pages=1-1` 等冲突记录标为 uncertain，等待 IEEE Xplore 人工核实。
