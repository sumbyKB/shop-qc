# TikTok Shop 商品评论抓取 - 完整打法（已验证）

> 项目: shop-qc | 验证日期: 2026-10-09 | 状态: ✅ 两个商品全量抓取成功，流程可复用

## 一、成果

| 商品 | 商品ID | 平台评论数 | 实际抓到 | 评分 | 差评率 | 报告 |
|---|---|---|---|---|---|---|
| 女式单肩包（PU皮） | 1729483763488494309 | 2235 | 2225 (99.6%) | 4.6★ | 6.2% | report/TikTok评论分析报告_单肩包1729483763488494309.xlsx |
| 6支装哑光口红套装 | 1732394770018636376 | 1060 | 1060 (100%) | 3.7★ | 25.6% | report/TikTok评论分析报告_口红套装1732394770018636376.xlsx |

每份报告 5 个工作表 + 7 张原生图表：总览(KPI+星级饼图/柱图)、月度趋势(量+均分)、SKU分析、差评分析(高频词+明细)、评论明细(全量带筛选)。

## 二、标准流程（四步）

### 1. 网络层 — 必须美国出口 IP
- TikTok 直连不通（超时），走本机 Clash Verge 混合端口 `127.0.0.1:7897`
- 美国站 PDP 用非美国 IP 会被地理重定向到泰国站商城首页
- 切节点：skill 打包版 `clash_pipe.py` 走 **HTTP external-controller**（环境变量 `CLASH_API`，默认 `http://127.0.0.1:9090`；`CLASH_SECRET` 可选 Bearer 认证；子命令 `list` / `switch <组> <节点>`；控制器请求绕过流量代理）。`scripts/` 老版本是命名管道 `\\.\pipe\verge-mihomo`（`http_over_pipe`，secret=`set-your-secret`），仅作 legacy 备用
- 选「🇺🇸 美国-家宽」住宅节点，风控最宽松；GLOBAL 组切换，用完可切回（用户可要求不切）

### 2. 浏览器层 — 真实 Edge + CDP 附加
- ❌ Playwright 直接 launch（headless/headed 都试过）→ 必弹 Security Check 滑块
- ❌ 自动过滑块不可靠，让用户手动拖一次即可
- ✅ 独立启动真实 Edge：
  ```
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9333 --user-data-dir=D:\code\codeMy\shop-qc\.browser-profile-cdp --proxy-server=http://127.0.0.1:7897
  ```
- Playwright `connect_over_cdp("http://127.0.0.1:9333")` 附加操作
- 首次通过滑块后 cookie 存在 `.browser-profile-cdp`，之后不再弹验证

### 3. 数据层 — 明文评论 API 重放（核心突破）
- TikTok 前端翻页靠加密参数 `X-Tts-Oec-Bsid`（每页一个），但**实际可不带**
- 直接在页面上下文重放：
  ```
  POST https://shop.tiktok.com/api/shop/pdp_desktop/get_product_reviews
  Content-Type: application/json
  {"product_id":"<id>","page_start":1,"page_size":50,"sort_rule":1,
   "review_filter":{"filter_type":1,"filter_value":6},"component_name":"pdp_left_reviews"}
  ```
- `page_size` 官方前端只用 3，实测可到 **50**（2235 条 = 45 个请求）
- `filter_value`: 6=全部，1-5=对应星级（分区抓取用）
- 响应：`data.product_reviews[]`（review_rating 1-5星、review_text、review_images[]、is_verified_purchase、is_incentivized_review、sku_specification、review_country、review_time 毫秒时间戳）、`has_more`、`review_ratings`（总分+星级分布）

### 4. 报告层 — 参数化生成 Excel
```
python scripts/harvest_reviews.py <商品ID> [page_size]   # 抓取 → probe/us_cdp/reviews_<商品ID>.json
python scripts/build_excel.py <reviews_json> <输出xlsx>   # 报告 → report/
```

## 三、踩坑记录（重要）

| 坑 | 解法 |
|---|---|
| 连续 20 个快速请求后临时限流（v1 卡在 999 条） | 失败退避 5/10/20/40s；v2 改按星级分区抓取+合并去重，每区数据量小 |
| **会话级限流 `{"code":100000}`**（2026-10-09 登山裤踩坑）：在错误标签页上抓另一个商品 → 几十次错误请求触发限流 → 之后连页面自己的评论请求都返回 100000，评论区只剩 SSR 内嵌 3 条，看似"另一种页面模板"，实为限流假象 | **实测约 40-60 分钟自动解封**（换 IP/清 cookie/新浏览器配置都无效，纯等时间）；脚本已加快速熔断（连续两次 100000 即终止+诊断）+ 低频探测自动恢复（每 10 分钟单请求，解封即自动跑完整流程）；对之前成功的商品重放可验证是否解封 |
| 在错误标签页上抓新商品（按"pdp"子串选 tab） | 按**商品ID精确匹配**标签页，不匹配就 goto |
| 深分页安全网 | filter_value=6 全量抓完后再跑 1-5 星各一轮，用 API 返回的各星总数交叉校验 |
| PDP 页面 body 不滚动，滚动容器是 `.overflow-y-scroll` div | 需操作该容器的 scrollTop |
| DOM 元素按滚动虚拟渲染 | 找分页控件前必须先滚到位 |
| GBK 控制台打印中文/emoji 报 UnicodeEncodeError | `PYTHONIOENCODING=utf-8` 或写文件 |
| Playwright 截图卡死在"waiting for fonts" | 用 CDP `Page.captureScreenshot` |
| 页面 Navigation 瞬间调 page.title() 抛异常 | try/except 包裹轮询 |
| SSR HTML 里非 ASCII 是 `\uXXXX` 转义 | 按字段名（review_id 等）定位，别按中文文本搜 |

## 四、脚本清单（scripts/）

| 文件 | 用途 |
|---|---|
| `harvest_reviews.py` | v2 抓取器：星级分区+耐心退避+按商品存档 |
| `build_excel.py` | 参数化 Excel 报告生成（KPI/图表/差评分析/明细） |
| `clash_pipe.py` | Clash 切节点（list/switch；skill 版走 HTTP external-controller，scripts 老版走命名管道） |
| `cdp_capture.py` | 启动真实 Edge（9333 端口）+ 附加 |
| `api_replay_test.py` | API 重放连通性测试 |

## 五、以后怎么用

给我任意 TikTok Shop 美国站商品链接 → 提取商品ID → 确认 Edge(9333) 开着且网络是美国出口 → 跑 harvest → 出 Excel 报告。全程约 2-3 分钟（2000 条级）。
