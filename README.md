# auto-seuwlan

`auto-seuwlan` 是一个面向东南大学 `SEU-WLAN` 的自动重连和自动认证脚本。它适合放在个人电脑上常驻运行：发现断网后，先尝试重新连接 Wi-Fi，再通过校园网 Portal 接口完成认证。

当前重点支持 `w.seu.edu.cn/a79.htm?UserIP=...&wlanacname=...` 这一类 `Dr.COM / ePortal / Portal` 认证链接。脚本会默认绕过系统代理，避免 VPN 或代理软件影响校园网登录页探测。

## 功能

- 自动判断是否已联网。
- 自动连接 Windows Wi-Fi 配置 `SEU-WLAN`。
- 自动从浏览器跳转链接或配置文件识别 `SEU ePortal` 类型。
- 断网后循环重试，适合计划任务常驻。
- 默认绕过系统代理，兼容 VPN/代理仍开启的场景。
- 支持日志文件、诊断命令、dry-run 和 Windows 登录自启动。
- 不依赖第三方 Python 包。

## 环境

- Windows 10/11。
- Python 3.9 或更高版本。
- 已在 Windows 里保存过 `SEU-WLAN` Wi-Fi 配置。

macOS/Linux 可以运行认证请求，但脚本里的 Wi-Fi 自动重连只通过 Windows `netsh` 实现。

## 快速开始

1. 复制配置模板：

```powershell
Copy-Item .env.example .env
```

2. 编辑 `.env`，至少填写：

```text
SEUWLAN_USERNAME=你的校园网账号
SEUWLAN_PASSWORD=你的校园网密码
```

3. 运行诊断：

```powershell
python .\auto_seuwlan.py --doctor
```

4. 检测 Portal 链接类型：

```powershell
python .\auto_seuwlan.py --detect
```

如果输出 `login_url: <none>`，说明当前没有配置静态链接，并且本次探测没有拿到校园网登录页跳转。通常有两种情况：你已经在线，或者还没有连接到 `SEU-WLAN`。断开/重连 `SEU-WLAN` 后再执行一次，或把浏览器跳转后的登录链接写入 `seuwlan.local.md`。

5. 单次重连和认证：

```powershell
python .\auto_seuwlan.py
```

6. 常驻监控：

```powershell
python .\auto_seuwlan.py --daemon
```

## Portal 链接

脚本优先使用断网时实时探测到的 Portal 跳转链接。通常不需要手动配置。

如果自动探测不到，可以在浏览器打开任意 HTTP 页面，复制跳转后的校园网登录链接，并放入以下任一位置：

- `.env` 的 `SEUWLAN_LOGIN_URL`
- `seuwlan.local.md` 的任意一行，推荐使用，已被 git 忽略
- `seuwlan.md`，仅适合个人本地使用，不建议提交真实链接

链接形态通常类似：

```text
https://w.seu.edu.cn/a79.htm?UserIP=10.x.x.x&wlanacname=...
```

不要把带有真实 `UserIP`、`wlanacname`、账号或密码的信息提交到公开仓库。

## 配置

常用配置在 `.env.example` 中均有注释。

| 变量 | 说明 |
| --- | --- |
| `SEUWLAN_USERNAME` | 校园网账号 |
| `SEUWLAN_PASSWORD` | 校园网密码 |
| `SEUWLAN_WIFI_PROFILE` | Windows Wi-Fi 配置名，默认 `SEU-WLAN` |
| `SEUWLAN_LOGIN_URL` | 可选，校园网 Portal 跳转链接 |
| `SEUWLAN_MARKDOWN` | 可选，从哪个 Markdown 文件读取 Portal 链接，推荐 `seuwlan.local.md` |
| `SEUWLAN_ISP` | 校园网留空；运营商账号可填 `c/cmcc`、`t/telecom`、`u/unicom` |
| `SEUWLAN_INTERVAL` | daemon 模式检查间隔，默认 60 秒 |
| `SEUWLAN_TIMEOUT` | HTTP 请求超时，默认 5 秒 |
| `SEUWLAN_PORTAL_RETRIES` | Wi-Fi 重连后继续探测 Portal 的次数，默认 5 |
| `SEUWLAN_PORTAL_RETRY_WAIT` | 每次 Portal 探测之间等待秒数，默认 5 |
| `SEUWLAN_FALLBACK_PORTAL_URLS` | 自动跳转拿不到时尝试访问的 SEU Portal 地址 |
| `SEUWLAN_LOCAL_IP` | 可选，Portal URL 不含 `UserIP` 时手动指定本机 IPv4 |
| `SEUWLAN_LOG_FILE` | 可选，日志文件路径 |
| `SEUWLAN_USE_SYSTEM_PROXY` | 默认 `0`，联网探测和认证均绕过系统代理 |

## VPN/代理

校园网 Portal 认证必须直连校园网网关。脚本默认不使用系统代理：

```text
SEUWLAN_USE_SYSTEM_PROXY=0
```

如果你使用的是 Clash、v2rayN、系统代理或浏览器代理，保持默认即可。如果 VPN 使用 TUN/虚拟网卡接管了系统路由，脚本无法强制绕过它，需要在 VPN 客户端里给 `w.seu.edu.cn` 或校园网网关添加直连规则。

## 注册开机/登录自启动

注册当前用户登录后自动运行：

```powershell
.\install_task.ps1
```

注册后立即启动：

```powershell
.\install_task.ps1 -StartNow
```

默认会使用 `pythonw.exe` 注册后台任务，不显示命令行窗口。日志写入：

```text
logs\auto_seuwlan.log
```

如果你需要调试并显示命令行窗口，可以显式使用：

```powershell
.\install_task.ps1 -Console
```

查看将要注册的命令但不实际写入：

```powershell
.\install_task.ps1 -DryRun
```

卸载计划任务：

```powershell
.\uninstall_task.ps1
```

默认日志路径：

```text
logs\auto_seuwlan.log
```

## 常见问题

### `Register-ScheduledTask : 拒绝访问`

新版 `install_task.ps1` 会优先注册当前用户登录任务，并在 PowerShell API 失败时回退到 `schtasks.exe`。如果仍然失败，可以用管理员 PowerShell 再运行一次。

### 挂着 VPN 时打不开 `msftconnecttest`

脚本不依赖浏览器打开 `http://www.msftconnecttest.com`，并且默认绕过系统代理。联网探测会优先访问不依赖 DNS 的 HTTP IP 地址，再尝试 `msftconnecttest`，最后还会尝试 `w.seu.edu.cn/a79.htm` 作为 SEU Portal 兜底。

如果浏览器在挂代理时打不开 `msftconnecttest`，不一定影响脚本自动认证；先看 `logs\auto_seuwlan.log`。如果脚本也失败，通常是 VPN TUN 模式或虚拟网卡接管了路由，需要在代理/VPN 客户端给以下地址设置直连：

```text
w.seu.edu.cn
1.1.1.1
223.5.5.5
www.msftconnecttest.com
```

也可以把浏览器跳出的真实 Portal URL 写入 `.env` 的 `SEUWLAN_LOGIN_URL` 或 `seuwlan.local.md`。

### 开机后出现 `UnicodeDecodeError: gbk codec can't decode`

这是 Windows/Conda 在读取 `netsh` 输出时按 GBK 解码失败导致的。新版脚本已经改为按字节捕获并容错解码，不会再因为本地化输出或异常字节导致 daemon 线程报错。

### 开机后短暂提示 `no portal URL found`

开机初期 Wi-Fi、DNS 和校园网 Portal 可能还没有准备好。脚本会在 Wi-Fi 重连后按 `SEUWLAN_PORTAL_RETRIES` / `SEUWLAN_PORTAL_RETRY_WAIT` 多探测几轮；如果随后已经联网，会直接返回成功。

### 关掉开机启动的命令行窗口后不再自动重连

旧版本计划任务使用 `python.exe`，关闭命令行窗口会结束 daemon。新版 `install_task.ps1` 默认使用 `pythonw.exe` 注册后台任务，不显示窗口，也不会因为关闭窗口而停止。升级后重新运行：

```powershell
.\install_task.ps1
```

然后通过日志查看状态：

```powershell
Get-Content .\logs\auto_seuwlan.log -Wait
```

### `portal_type: unknown`

说明当前链接不是已实现的 SEU ePortal 类型。请提交 issue，并附上脱敏后的链接形态，例如隐藏 `UserIP` 和账号信息。

## 开发

运行基础检查：

```powershell
python -m py_compile .\auto_seuwlan.py
python -m unittest discover -s tests
python .\auto_seuwlan.py --doctor
```

## 安全说明

`.env` 里保存的是明文账号密码，只应该存在于自己的电脑上。仓库已经默认忽略 `.env`、日志和本地链接文件。发布 issue、截图或日志前，请检查是否包含账号、密码、真实 IP 或 AP 名称。
