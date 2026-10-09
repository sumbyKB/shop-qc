---
name: tiktok-review-harvest
description: >-
  抓取 TikTok Shop 商品公开评论并生成 Excel 样本分析报告。
  用户给出完整 shop.tiktok.com 区域商品链接或商品 ID，要求抓评论、差评分析或评论报告时使用。
  不用于达人邀约、账号分析、店铺管理或其他网站评论。
---

# TikTok Shop 评论抓取与报告

通过本机 Edge/Chrome 的 CDP 会话读取公开评论；验证码由用户手动完成。
平台接口、风控和评论数量会变化，必须按脚本返回的完整性状态描述结果。

## 安装与运行位置

用户通过宿主的 GitHub skill 安装功能安装后直接调用；无需额外运行安装器。
首次调用按 [INSTALL.md](INSTALL.md) 由 agent 准备隔离 Python 环境与依赖。
需要 Python 3.10+、Edge/Chrome、
playwright 和 openpyxl。Windows 为主要支持平台；macOS/Linux 提供浏览器探测，
需要图形桌面，并应在目标机器运行预检。

执行前定位**当前已安装的本 skill 目录**，不要假设项目根目录就是 skill 根目录。
优先用本 skill 下的隔离环境：
Windows 为 .venv/Scripts/python.exe，macOS/Linux 为 .venv/bin/python；
没有隔离环境时由 agent 创建 .venv 并安装 requirements.txt；目录只读时在用户工作目录创建隔离环境。
已有依赖可正常导入时复用，不重复安装。
下文 <python>、<skill> 和 <工作目录> 都需替换为实际路径，带空格的路径要加引号。
在用户指定的可写工作目录执行，所有脚本使用绝对路径：
产物写到工作目录；浏览器 cookie 默认保存在当前用户的数据目录，不写入 skill 安装目录。

## 流程

1. 预检，尽量带上目标链接：

       <python> "<skill>/scripts/tiktok_reviews.py" check "<商品URL>"

   缺 Python 库时由 agent 在隔离环境补齐后重跑预检，不要求用户手工运行安装器。
   缺 Python、浏览器或网络条件时说明具体缺项；预检失败必须先处理，不得当作通过。
   确认 TT_PROXY 为本机 HTTP/mixed 代理端口或 direct。
   浏览器启动前检查配置出口；已有 CDP 会话时检查浏览器实际出口。

2. 出口国家须与 URL 中的站点区域一致。
   自动探测常见本地 HTTP 端口；非标准端口用 TT_PROXY。
   不依赖 Clash，其他代理客户端可手动切换线路。
   可选的 Clash/mihomo 控制器操作见 INSTALL.md：CLASH_API/CLASH_SECRET。
   切换节点会影响用户其他应用，必须获得明确授权；记录原节点便于恢复。
   切换后关闭本 skill 的浏览器，再运行，以应用新代理。

3. 抓取和报告：

       <python> "<skill>/scripts/tiktok_reviews.py" all "<商品URL或ID>" --out "<工作目录>/output"

   仅 ID 默认美国站；其他区域须加 --region th 等参数。
   支持完整 https://shop.tiktok.com/<region>/pdp/.../<id> 链接，不支持短链。
   抓取器启动独立用户配置的真实浏览器，然后通过 CDP 附加；不使用日常浏览器配置。
   若出现 Security Check，告知用户手动完成，最多等 5 分钟；超时停止。
   不自动处理验证码、不绕登录或付费墙。
   不对同一浏览器/商品并行运行多个抓取器。

4. 根据返回码、JSON 的 status 和报表警告描述结果：
   - 0：正常完成；抓取命令已核对平台总数和各星级数量，单独 report 命令仅表示报表生成成功。
   - 2：配置、依赖、输入、浏览器或报告错误。
   - 3：没有评论数据，不生成空报表；可能是真实零评论或抓取失败，需结合 stop_reason 判断。
   - 4：部分数据或完整性未验证；有数据时仍生成带警告的报表。
   - 130：用户中断。

   连续两次 code=100000，或 HTTP 401/403/429 时停止全部星级请求。
   保留部分 JSON，等待后再由用户决定是否重试；不要承诺固定时间自动解封。
   已有 JSON/默认报表保留，新运行加时间后缀。显式 --xlsx 路径可覆盖该文件。

## 输出与配置

JSON 写入 --out，Excel 默认写入 <工作目录>/report：
5 个工作表、7 个原生图表，包含星级、月度趋势、SKU、英文差评词频和评论明细。
图片输出为 URL，不下载或嵌入图片；日期统一 UTC；未完整抓取的数据只能称为样本分析。

可用子命令：check / harvest / report <JSON> [--xlsx <路径>] / all。
TT_BROWSER_PATH（兼容 TT_EDGE_PATH）、TT_CDP_PORT、TT_PROFILE_DIR、TT_PROXY
的配置与安装示例见 [INSTALL.md](INSTALL.md)。

只有用户已手动核实浏览器出口、且 IP 查询服务不可用时才能使用 --skip-ip-check；
仍会验证商品页面的区域与 ID，不能绕过验证码。

遇到问题读 [references/troubleshooting.md](references/troubleshooting.md)，
接口实现和数量核对读 [references/playbook.md](references/playbook.md)。
