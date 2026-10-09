# 首次运行与环境配置

用户从 GitHub 安装 skill 后，直接在宿主中调用。
本文件供执行 agent 检查首次运行环境或处理非标准配置，
不要求用户额外下载文件或运行安装器。

## 首次运行准备（由 agent 执行）

1. 定位当前已安装的 skill 根目录。
2. 找到 Python 3.10+，Windows 可检查 python 或 py -3，macOS/Linux 可检查 python3。
3. 优先使用本 skill 的 .venv；若不存在，创建隔离环境：

       <系统Python> -m venv "<skill>/.venv"

4. 使用隔离 Python 安装依赖：

       <隔离Python> -m pip install -r "<skill>/requirements.txt"

   Windows 的隔离 Python 为 <skill>/.venv/Scripts/python.exe；
   macOS/Linux 为 <skill>/.venv/bin/python。
   若 skill 安装目录只读，在用户工作目录创建 .tiktok-review-harvest-venv，
   后续继续使用这个环境。依赖安装失败时根据错误提示处理，
   不修改系统 Python 的库，不把失败当作已经准备好。
5. 在用户的可写工作目录运行目标商品预检，再执行 all。

已存在的环境先检查依赖是否可导入，正常时不重复安装。
缺少 Python 或浏览器时告诉用户需补齐的软件；
不要因 Python 库缺失而让用户自己执行整套安装流程。

requirements.txt 固定 Playwright 1.63.0 与 openpyxl 3.1.5。
使用机器已安装的 Edge/Chrome，不需要 playwright install。
Python 包安装需要可用的包索引网络，也可沿用组织配置的 pip 镜像。

## 环境变量

| 变量 | 用途 |
|---|---|
| TT_PROXY | http://host:port 或 direct；默认探测常见本地 HTTP/mixed 端口 |
| TT_BROWSER_PATH | 浏览器可执行文件的实际路径 |
| TT_EDGE_PATH | 旧浏览器路径配置，保留兼容 |
| TT_CDP_PORT | 默认 9333，冲突时指定其他空闲端口 |
| TT_PROFILE_DIR | 独立浏览器配置目录，不得指向日常浏览器 profile |
| CLASH_API | 可选 mihomo HTTP 控制器地址，默认 http://127.0.0.1:9090 |
| CLASH_SECRET | 可选控制器密钥，从目标机器环境获取 |

用户告知非标准代理或浏览器路径时，由 agent 在当前运行环境中设置。
不默认写入用户全局配置，也不把控制器密钥写进 skill。

代理须为 HTTP/mixed 端口；不支持 SOCKS-only 或需要账号密码的代理。
能直接访问站点且出口国家正确时使用 direct。
切换后关闭本 skill 的浏览器再运行，已有浏览器不会自动更新代理。
IP 查询使用 api.country.is/ipwho.is；既有 CDP 会话检查浏览器实际出口。
仅在用户手动确认浏览器出口正确、且 IP 查询不可用时使用 --skip-ip-check。

## 可选 Clash/mihomo 控制器

抓取不依赖控制器，用户可在代理软件中手动切节点。
辅助脚本 clash_pipe.py 保留旧文件名，现使用 HTTP external-controller，
不再绑定 verge-mihomo 命名管道。

    <隔离Python> "<skill>/scripts/clash_pipe.py" list
    <隔离Python> "<skill>/scripts/clash_pipe.py" switch "<分组名>" "<节点名>"

switch 仅在用户明确授权后运行，记录原节点以便恢复。
它不会修改代理模式，执行后会核对所选节点。
只有命名管道的配置可直接使用手动切节点方式。

## 运行位置与数据

脚本以安装 skill 的绝对路径调用，产物写到用户工作目录。
浏览器独立会话默认保存在当前用户的数据目录；不得复制给其他用户。
出现验证码时请用户手动完成，不保证会话长期免验证。
Windows 为主要支持平台；macOS/Linux 需要图形桌面与浏览器运行依赖。
