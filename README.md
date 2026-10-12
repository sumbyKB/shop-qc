# TikTok Shop 评论分析 Skill

安装这个 skill 后，直接把 TikTok Shop 商品链接发给 Codex 或 Claude Code，
即可抓取公开评论并生成 Excel 分析报告。
也支持印尼站 `shop-id.tokopedia.com/pdp/.../<商品ID>` 链接，自动识别印尼区域。

## 从 GitHub 安装

把下面这段话发给你的 AI 助手，让它使用当前宿主的 skill 安装功能：

> 帮我安装 https://github.com/sumbyKB/shop-qc 中的 tiktok-review-harvest skill，
> skill 路径是 .claude/skills/tiktok-review-harvest。

仓库地址：[sumbyKB/shop-qc](https://github.com/sumbyKB/shop-qc)。
安装目标是上述 skill 子目录。安装后让宿主重新加载技能，必要时重新打开宿主。

## 安装后直接使用

把真实商品链接替换进下面这段话：

> 使用 tiktok-review-harvest 分析这个商品的评论：<完整商品链接>。
> 生成 Excel 报告，分析差评原因，并告诉我抓取是否完整。

Codex 也可通过 $tiktok-review-harvest 显式调用。
首次调用时，AI 会检查运行环境，缺少 Python 库时在隔离环境中安装，
然后检查浏览器和网络，再开始抓取。

电脑需要已有 Python 3.10+、Edge 或 Chrome，以及能访问目标区域的网络。
印尼 Tokopedia 链接需要印尼出口；验证码或限流仍可能阻止评论翻页。
若缺少这些条件，AI 会说明需要补齐什么；出现验证码时需要你在浏览器中手动完成。

## 会得到什么

- 评论原始 JSON。
- Excel 报告：总览、月度趋势、SKU 分析、差评分析、评论明细。
- 明确的完整性说明；部分数据会标注为样本，不冒充全量结果。

更多用法见 [skill 使用说明](.claude/skills/tiktok-review-harvest/README.md)。

## 开发者验证

在项目根目录运行：

    python -X utf8 -m unittest discover -s tests -v

这些测试检查本地行为，目标机器的网络与 TikTok 验证状态仍需首次调用时确认。
