# TON 2026 LaTeX 文档

这是 Green-PLUM 的 IEEE/ACM Transactions on Networking 投稿文档骨架。

## 文件

- `main.tex`：IEEEtran 双栏论文主文件。
- `references.bib`：BibTeX 参考文献库；当前条目只是可编译占位，请在正式写作时核对作者信息。
- `latexmkrc`：自动多轮编译和 BibTeX 配置。
- `main.pdf`：通过编译测试后生成的 PDF。

## 编译

```bash
ssh school-server
cd /home/xuzy/Plum-for-award/Plum/docs/ton26
latexmk -pdf main.tex
```

清理编译中间文件：

```bash
latexmk -C
```

LaTeX 环境安装在 `~/.TinyTeX`，常用命令的软链接位于 `~/.local/bin`，不需要 sudo。

## 写作提醒

- `main.tex` 中的标题、作者、摘要和章节内容目前都是起草占位。
- 独立能耗模型、model-based Wi-Fi 和 trace-driven 包级实验必须分别描述，不能混用结果。
- 正式投稿前应再次核对当年 TON/IEEE Author Center 的格式、匿名政策和补充材料要求。
