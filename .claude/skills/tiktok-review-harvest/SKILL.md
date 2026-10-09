---
name: tiktok-review-harvest
description: 抓取 TikTok Shop 商品全部评论（星级/文字/图片/翻页）并生成带图表的 Excel 分析报告。当用户给出 TikTok Shop 商品链接/PDP 链接并要求抓评论、分析评论、出评论报告、差评分析时使用。Trigger: TikTok 评论、TikTok Shop reviews、商品评论抓取、评论分析报告。
---

# TikTok Shop 评论抓取 + Excel 报告

一套已验证的完整流程：出口 IP 与站点区域一致 → 真实 Edge(CDP 附加) → 明文评论 API 重放 → Excel 报告。
本 skill 根目录下：`scripts/`（可执行脚本）、`references/`（方法论与故障手册）、`requirements.txt`。
**以下所有路径均相对于本 skill 的根目录。**

## 0. 依赖（首次使用前，一次性）

```bash
pip install -r requirements.txt
```

## 使用步骤（按顺序，不要跳）

### 1. 环境预检

```bash
python scripts/tiktok_reviews.py check
```

自动检查：代理端口（探测 7897/7890/10809 等，可用 env `TT_PROXY` 指定）、出口 IP 国家、Edge 路径、Python 依赖、CDP 9333 端口。缺什么按提示补。

### 2. 出口 IP 必须与站点区域一致

美国站(/us/)必须美国出口 IP，否则被重定向/风控。住宅（家宽）节点风控最宽松。
若用户跑 Clash 系代理（端口探测失败时先确认用户用的是哪种代理）：

```bash
python scripts/clash_pipe.py list     # 列出分组/节点（自动找 US 候选）
python scripts/clash_pipe.py switch "GLOBAL" "<节点名>"
```

⚠️ 切的是用户全局代理：**动手前告知用户，完成后询问是否切回**。密钥不同用 env `CLASH_SECRET`。

### 3. 浏览器：真实 Edge + CDP 附加（脚本会自动拉起）

`harvest`/`all` 子命令发现 CDP 9333 不在线时会自动启动真实 Edge（需系统装有 Edge，路径自动探测，可用 env `TT_EDGE_PATH` 指定）。

硬性规则：
- **禁止**用 Playwright 直接 launch 浏览器（必触发滑块），只能 CDP 附加
- **首次出现 Security Check 滑块：让用户手动拖一次**，脚本等待最多 5 分钟；通过后 cookie 存在 `<工作目录>/.browser-profile-cdp`，之后不再弹

### 4. 一键抓取 + 报告

```bash
python scripts/tiktok_reviews.py all "<商品URL或商品ID>" --out ./output
```

子命令：`check` / `harvest <url|id>` / `report <json> [--xlsx 路径]` / `all <url|id>`。
产物：`<out>/reviews_<商品ID>.json` + `report/TikTok评论分析报告_<商品ID>.xlsx`（5 工作表 + 7 原生图表：总览KPI、星级饼图、月度趋势、SKU分析、差评分析、全量明细带筛选）。

## 行为约定（写给执行 agent）

- 接口被限流（`code=100000`）时脚本会自动熔断并提示：**等 10-60 分钟自动解封**，期间不要反复重试加剧封锁；可用 `harvest` 单次探测（见 references/troubleshooting.md 的判别方法）
- 抓取器已内置防限流（星级分区 + 退避重试），不要对同一商品并行开多个抓取
- 只抓公开评论数据，1.5s/请求限速；不绕登录/付费墙
- 深入原理见 `references/playbook.md`，疑难杂症见 `references/troubleshooting.md`
