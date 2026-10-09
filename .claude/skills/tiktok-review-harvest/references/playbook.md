# 实现说明与完整性校验

这是当前脚本的接口记录，不是 TikTok 对接口稳定性的保证。过去商品的成功结果
不能推断到其他机器、站点或未来页面；遇到接口变化必须停止并检查响应。

## 网络与浏览器

出口区域应与商品 URL 区域一致。可使用本地 HTTP/mixed 代理或直连，
不要求特定代理软件。预检和抓取检查出口国家；已有 CDP 会话时检查实际浏览器路由。

启动独立配置的 Edge/Chrome，通过 Playwright connect_over_cdp 附加，
不使用 Playwright 自带浏览器，也不接管用户的日常 profile。
CDP 仅适用于 Chromium 系浏览器，属于兼容性较低的连接方式，
浏览器版本变化仍可能影响功能。[Playwright 官方说明](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp)

验证码由用户手动完成，五分钟超时停止；保留 cookie 不代表以后不会再验证。

## 当前评论接口

同源 POST /api/shop/pdp_desktop/get_product_reviews：

    {
      "product_id": "<商品ID>",
      "page_start": 1,
      "page_size": 50,
      "sort_rule": 1,
      "review_filter": {"filter_type": 1, "filter_value": 6},
      "component_name": "pdp_left_reviews"
    }

filter_value=6 为全部，1..5 为对应星级；参数来自原有商品实测，平台可能修改。
返回 data 包含 product_reviews、has_more、total_reviews、review_ratings。
评论以 review_id 去重；不会因重复页直接宣称抓取完整。

## 请求与终止

- 全部评论后再按 5..1 星补抓，正常请求之间至少间隔 1.5 秒。
- 单请求失败等待 5/10/20 秒，最多四次尝试。
- 连续两次 code=100000，或 HTTP 401/403/429：停止全部星级请求。
- has_more=true 但空页，或连续两页没有新增评论：停止并标记部分数据。
- 响应结构变化：停止，保留已抓到的数据。
- 从已验证商品 PDP 的 HTML 中合并 SSR 内嵌评论；可能没有此数据。
- 站点重定向、商品 ID 不符或验证超时：不调用评论接口。

100000 的具体原因不应只凭错误码判断，更不能推断为全球故障；
查看页面状态、HTTP 状态和响应，等待后再决定是否重试。
不承诺固定解封时间。

## 结果契约

JSON 的 status：
- complete：未中途失败；总数、五个星级分区数与去重后的数据逐项相等。
- partial：中途停止，或数量低于平台声明。
- unknown：总数不可用、分区缺失或数量不一致，无法确认完整。

这是针对抓取时平台声明数量的核对，评论动态变化时可能得到 unknown。
报表只按已抓到的样本统计，明显显示 partial/unknown 警告。
旧 JSON 无 status 时按 unknown 处理。未抓到数据返回码 3，不生成空报表。

## 可选代理控制器

clash_pipe.py 保留旧文件名，但现在调用可配置的 mihomo HTTP 控制器。
GET /proxies 列节点，PUT /proxies/<编码分组名> 切节点，然后读取 now 确认。
CLASH_API 与 CLASH_SECRET 由目标机器配置；无控制器时可手动切换代理。
[官方控制器接口](https://wiki.metacubex.one/api/)

## 本地验证

在项目根目录运行：

    python -X utf8 -m unittest discover -s tests -v

测试使用模拟网页、临时目录和本地 HTTP 控制器，不访问 TikTok 或切换真实代理。
GitHub 安装后的首次调用由 agent 按 INSTALL.md 准备依赖并完成目标商品预检。
