# TON 2025–2026 文献收集与初稿 — 进度 (v2 校正版)

- 更新：2026-07-27
- 环境：READY（OA-only）。抓取脚本和缓存说明见 `scripts/README.md`。
- 范围：仅公开 OA PDF；不绕过付费墙。

## 关键修正（v1→v2）
- v1 用旧 ISSN 1063-6692，错误结论"Crossref/OpenAlex 只到 2024"。
- 2025 起期刊更名 IEEE Transactions on Networking，新 e-ISSN 2998-4157。
- 用新 ISSN 重采：Crossref 687 记录（664 研究 + 23 非研究）。

## 当前进度
- 已发现：Crossref 新 ISSN 687（OpenAlex 659, DBLP 622 交叉）
- 去重：687 记录 = 646 正式分页研究论文 + 16 EA + 2 状态待核实 + 23 非研究项
- PDF 下载：25/29 OA（chunk_001，复用 v1，未重复下载）
- 相关性：R1=0, 人工确认 R2=17, 自动候选 R3=143, R4=527
- 已精读 R2：17 篇（全文 2，摘要 15）

## 已完成文件
文献: ton_2025_2026_catalog_v2.csv, ton_2025_2026_references_v2.bib, download_manifest_v2.csv
PDF: pdfs/chunk_001/ (25)
脚本: scripts/ (build_catalog_v2.py, manual_r1r4_review.py, fetch_openalex_newton.py, download_oa_pdfs.py, catalog_stats.py, README.md)
分析: TON_2025_2026论文分析与投稿启示_v2.md, TON相关论文精读_v2.md
项目评估: docs/ton26/当前实验进度与证据清单.md, TON投稿准备度与缺口分析.md, 给老师的阶段汇报.md
草稿: docs/ton26/draft.md (v2)

## 阻碍
- IEEE 付费墙：仅 25 篇 OA 全文；最接近 PLUM 的 seq312 无全文，须通过机构访问获取
- IEEE Xplore 反爬未能全量直采；2 条 `volume=34, pages=1-1` 的出版状态暂标 uncertain，须人工核验
