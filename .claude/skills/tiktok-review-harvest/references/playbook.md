# 方法论：为什么这套流程能绕开风控（已验证两个商品 100% 全量）

## 三层障碍与解法

### 1. 网络层：IP 决定生死
- TikTok 直连不通（TLS 握手被重置），必须走代理
- **区域一致性**：`/us/` 商品页用非美国 IP 访问 → 服务端直接弹 Security Check 或重定向到当地商城首页。URL 区域 ↔ 出口 IP 国家必须一致
- 数据中心 IP（机房 VPN）风控评分差；**住宅 IP（家宽）最宽松**。Clash 订阅里带「家宽/ISP」字样的节点优先

### 2. 浏览器层：自动化指纹检测
- Playwright 启动的 Chromium（无论 headless/headed）→ 必弹滑块。TikTok 检测 `navigator.webdriver` + CDP 自动化标志 + 浏览器指纹一致性
- 解法：**独立启动真实 Edge**（`--remote-debugging-port`），Playwright 只做 CDP 附加（`connect_over_cdp`）。真实 Edge 的指纹是真用户指纹
- 滑块兜底：真遇到滑块让人拖一次，cookie 持久化后不再触发

### 3. 数据层：不要和前端加密硬碰硬
- 前端翻页用加密参数 `X-Tts-Oec-Bsid`（每页不同），逆向 JS 生成逻辑成本极高
- **关键发现**：评论接口本身是明文 POST，加密参数可以不带，`page_size` 官方用 3 但服务端接受 50
- 在页面上下文用 `page.evaluate(fetch)` 发请求：自动带 cookie、同源无 CORS、指纹真实

## API 规格（实测）

```
POST https://shop.tiktok.com/api/shop/pdp_desktop/get_product_reviews
Content-Type: application/json

{
  "product_id": "1729483763488494309",   // 商品ID（从 /pdp/<slug>/<id>/ URL 提取）
  "page_start": 1,                        // 1 基页码
  "page_size": 50,                        // 官方 3，实测上限 ≥50
  "sort_rule": 1,                         // 1=推荐排序
  "review_filter": {"filter_type": 1, "filter_value": 6},
                                          // filter_value: 6=全部, 1~5=对应星级
  "component_name": "pdp_left_reviews"    // 桌面端 PDP 固定值
}
```

响应 `data`：
- `product_reviews[]`: review_id, review_rating(1-5), review_text, review_images[], display_image_url, reviewer_name, reviewer_avatar_url, review_time(毫秒), is_verified_purchase, is_incentivized_review, sku_specification, review_country, product_name
- `has_more`, `total_reviews`
- `review_ratings`: {review_count, overall_score, rating_result: {"5": n, ...}}

## 防限流策略（v2，必开）
1. 请求间隔 1.5s
2. 失败退避 5/10/20/40s 重试
3. **星级分区抓取**：全量(6)抓完后按 5→1 各再抓一轮合并去重——单区数据量小不易触顶，且可用 API 返回的各星总数交叉校验完整性
4. 终止条件：`has_more=false` 或连续两页无新数据
5. **code=100000 快速熔断**：连续两次 100000 → 判定会话/IP 被限流，立即终止（10-30 分钟后重试），不做无谓退避。此错误码无 message，是风控/限流的通用签名
6. **SSR 兜底合并**：PDP HTML 内嵌少量评论（~3 条），每次抓取自动解析合并，限流期也保底有数据

## 完整性校验
- `harvested_count` vs `total_reviews_claimed`（≥99% 即正常，缺口多为跨页去重的重复ID）
- 每星抓取数 vs `star_filter_totals`
