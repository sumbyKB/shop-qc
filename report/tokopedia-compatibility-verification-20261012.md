# 印尼 Tokopedia 兼容性验证

范围：shop-id.tokopedia.com 商品链接、区域映射、支持域名间页面跳转、目标商品 SSR 数据和报表输出。
保留原有用户修改的 .aios/memory/tiktok-review-scraping-playbook.md 与 .gitignore，未提交或推送。

VERDICT:
retry_budget: 3 remaining: 3

FILES_REVIEWED:
  - .claude/skills/tiktok-review-harvest/scripts/tiktok_reviews.py: product_url、extract_embedded_values、extract_ssr_ratings、fetch_page、collect_reviews (changed)
  - tests/test_portability.py: Tokopedia URL、印尼出口、跨域跳转、SSR 汇总、404 停止用例 (changed)
  - README.md、skill README.md、SKILL.md、references/playbook.md (changed)

CHECKS:
  - PASS: python -X utf8 -m unittest discover -s tests -v — 35/35。
  - PASS: quick_validate.py — Skill is valid!
  - PASS: git diff --check — 无格式错误，只有 Windows 换行提示。
  - PASS: 目标商品公开 raw HTML 读取，标题、商品 ID、review_info 与 review_ratings 可识别。
  - PASS: 实际页面提取 3 条目标商品评论，页面声明总数 24629，评分 4.9。
  - PASS: 对实际 SSR 样本运行 report，返回 0，生成标注部分数据的 Excel。
  - LIMITATION: 实时翻页测试页面出现 Security Check，停止会话；全量接口与后续分页未完成现场验证。
  - LIMITATION: 未更改用户的代理节点，未复制其他浏览器会话，未执行验证码自动处理。

CODE:
  > if parsed.netloc == 'shop-id.tokopedia.com' and parsed.path.startswith('/pdp/'):
  >     actual_region = 'id'
  > if response['status'] in (401, 403, 404, 405, 429):
  >     raise HarvestStopped(f'HTTP {response["status"]}: stopped; check challenge/login or wait before retrying.')

VALIDATION:
  APPROVED — score: 1.0, complete: true, missing: []
  结论仅覆盖链接、区域和公开页面数据兼容，不表示已验证全量翻页。实际抓取需可用的印尼出口及人工完成网站验证。

源页面：https://shop-id.tokopedia.com/pdp/tas-selempang-wanita-mossdoom-kulit-pu-3-warna-pilihan/1729623203878963558
样本 JSON：output/tokopedia-id-sample-20261012/reviews_1729623203878963558_SSR_sample.json
样本 Excel：report/Tokopedia评论样本_1729623203878963558_20261012.xlsx
