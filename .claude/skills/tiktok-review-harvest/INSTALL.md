# 安装到另一台电脑

需要 Python 3.10+（推荐 3.11/3.12）、Microsoft Edge 或 Google Chrome、
可访问目标站点的网络，以及可手动完成验证码的图形桌面。
Windows 是主要支持平台；macOS/Linux 的浏览器探测代码需要在目标机器预检。
Python、浏览器和代理服务不会随 ZIP 一起安装。

## Windows 快速安装

解压 ZIP，进入里面的 `tiktok-review-harvest` 文件夹，在该目录打开终端。
先运行 `python --version`；没有 python 命令时可以使用 `py -3`。

Codex：

```powershell
python scripts/install.py --host codex --deps
```

Claude Code：

```powershell
python scripts/install.py --host claude --deps
```

安装脚本复制 skill，并在安装目录创建 `.venv`、安装 Python 依赖，
不改系统 Python 的依赖。Codex 使用 `CODEX_HOME/skills`，未配置时使用
当前用户 `.codex/skills`；Claude Code 使用当前用户 `.claude/skills`。
安装失败会返回非零状态，按错误提示补齐 Python/网络后从**解压目录**加 `--update` 重试。
依赖安装需要访问 Python 包索引，可使用组织已经配置的 pip 镜像。
不需要 `playwright install`，因为使用机器已安装的 Edge/Chrome。
requirements.txt 固定本次隔离安装测试的 Playwright 1.63.0、openpyxl 3.1.5；
升级依赖时应重新运行测试，不自动追随新的版本。

已安装旧版时，从新包的解压目录运行：

```powershell
python scripts/install.py --host codex --update --deps
```

更新会覆盖 skill 的分发文件，保留已有隔离环境和其他文件。
安装成功后在宿主中重新加载技能（必要时重新打开宿主），使用
`$tiktok-review-harvest` 或描述抓取评论的需求。宿主是否允许执行脚本取决于其权限配置。

## 验证与使用

先在一个可写的工作目录运行。下面默认安装路径仅适用于未自定义 CODEX_HOME 的 Codex：

```powershell
$skillDir = Join-Path $env:USERPROFILE '.codex\skills\tiktok-review-harvest'
$skillPython = Join-Path $skillDir '.venv\Scripts\python.exe'
& $skillPython "$skillDir\scripts\tiktok_reviews.py" check 'https://shop.tiktok.com/us/pdp/<商品ID>'
& $skillPython "$skillDir\scripts\tiktok_reviews.py" all 'https://shop.tiktok.com/us/pdp/<商品ID>' --out './output'
```

将 `<商品ID>` 换成真实 ID，也可以粘贴完整商品 URL。
Claude Code 把 `.codex` 换成 `.claude`；自定义安装以安装脚本输出的路径为准。
返回码 4 表示仅抓到部分数据或完整性未验证，报表会显示警告，不代表全量成功。

## 机器配置

配置只在当前终端生效，下面的值是示例，请换成目标机器的值：

```powershell
$env:TT_PROXY = 'http://127.0.0.1:7890'
# 能直接访问并且出口国家正确时：
$env:TT_PROXY = 'direct'
# 非标准浏览器安装位置（无需包含引号）：
$env:TT_BROWSER_PATH = 'C:\自定义目录\chrome.exe'
# 默认 9333；冲突时换一个空闲端口：
$env:TT_CDP_PORT = '9334'
```

- 未设置 TT_PROXY 时探测常见本地 HTTP/mixed 端口，无端口时尝试直连；
  SOCKS-only 端口、需要账号密码的代理不支持，请使用代理软件的本地 HTTP/mixed 端口。
- 出口 IP 必须与站点区域一致。预检或抓取会查询 `api.country.is`/`ipwho.is`；
  已有 CDP 时检查浏览器实际出口，不以代理客户端配置代替验证。
- **切换代理后关闭本 skill 的浏览器，再启动抓取**，否则已有浏览器可能仍走旧代理。
- 首次 Security Check 需要手动处理，以后仍可能再次出现，不保证 cookie 永久免验证。
- 浏览器独立配置默认放在当前用户的数据目录，可用 TT_PROFILE_DIR 改到另一个独立目录。
  不要指定日常浏览器的配置目录，不要把 cookie/profile 发给同事。
- 只有手动验证浏览器出口正确、但 IP 查询服务不可用时，才加 `--skip-ip-check`。
- 用纯商品 ID 时默认美国站；其他区域加 `--region th` 等参数。
- JSON 在 `--out`，报表在当前工作目录 `report`；脚本可从任何工作目录调用。

## Clash/mihomo（可选）

抓取器不依赖 Clash。手动在代理软件中切节点即可。
要使用辅助脚本，需启用 mihomo 的 HTTP `external-controller`，然后配置：

```powershell
$env:CLASH_API = 'http://127.0.0.1:9090'
$env:CLASH_SECRET = '<你自己配置的控制器密钥>'
& $skillPython "$skillDir\scripts\clash_pipe.py" list
# 仅在用户授权修改节点后：
& $skillPython "$skillDir\scripts\clash_pipe.py" switch '实际分组名' '实际节点名'
```

脚本名称为兼容原调用保留，已使用 HTTP 控制器，不再绑定 `verge-mihomo` 命名管道。
只有命名管道而未启用 HTTP 控制器的旧配置需要手动切换，或由用户自行开启控制器。
它只切换指定分组的节点，不改变代理模式；执行前记录原节点，恢复时再次 switch。
控制器密钥不写进 skill，也不要放入分发包。

## macOS/Linux 与其他安装目录

同样运行 `python3 scripts/install.py --host codex --deps`；隔离 Python 在
安装目录 `.venv/bin/python`。Linux 需要桌面显示和浏览器运行依赖。
环境变量用 `export TT_PROXY=http://127.0.0.1:7890` 等方式设置。
自定义宿主技能目录：`python scripts/install.py --destination '<技能目录>/tiktok-review-harvest' --deps`。

## 制作分发包

从源码 skill 文件夹运行：

```powershell
python scripts/install.py --package '<输出目录>/tiktok-review-harvest.zip'
```

打包仅包含 SKILL.md、安装说明、requirements.txt、Python 脚本和参考文档，
排除 cookie、浏览器配置、依赖环境、原始评论和报告。输出文件已存在时不会覆盖。

## 兼容性决策

保留现有 CDP 抓取和 openpyxl 报告，使用标准库处理安装、ZIP 和控制器 HTTP；
网络/浏览器探测统一放入 environment.py，避免预检与运行采用不同配置。
不自动安装代理或改全局节点，也不复制旧会话；首次验证由目标机器用户完成。
