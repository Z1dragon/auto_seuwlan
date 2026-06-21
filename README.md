# auto-seuwlan

根据 `seuwlan.md` 中的链接：

```text
https://w.seu.edu.cn/a79.htm?UserIP=...&wlanacname=...
```

可以推断这不是深澜 `srun`，而是东南大学 `SEU-WLAN` 使用的 `Dr.COM / eportal / Portal` Web 认证。浏览器被劫持到 `a79.htm` 认证页后，脚本会向同一主机的 `:801/eportal/` 发送登录请求。

## 使用

1. 复制配置文件：

```powershell
Copy-Item .env.example .env
```

2. 编辑 `.env`，填入 `SEUWLAN_USERNAME` 和 `SEUWLAN_PASSWORD`。

3. 如果脚本自动抓不到跳转链接，把浏览器弹出的校园网认证 URL 放进 `seuwlan.md`，或者写入 `.env` 的 `SEUWLAN_LOGIN_URL`。

4. 先检测链接类型：

```powershell
python .\auto_seuwlan.py --detect
```

5. 单次重连和认证：

```powershell
python .\auto_seuwlan.py
```

6. 常驻监控，断线后自动重连：

```powershell
python .\auto_seuwlan.py --daemon
```

7. 注册为开机/登录后自动运行的计划任务：

```powershell
.\install_task.ps1
```

## VPN/代理场景

脚本默认会绕过系统代理访问 `msftconnecttest`、`1.1.1.1` 和校园网认证接口。这样做是为了避免 VPN 或代理软件仍在运行时，把 captive portal 探测请求转发到代理里，导致打不开 `http://www.msftconnecttest.com` 或拿不到校园网登录页。

一般保持默认即可：

```text
SEUWLAN_USE_SYSTEM_PROXY=0
```

只有在你明确需要脚本走系统代理时，才改成：

```text
SEUWLAN_USE_SYSTEM_PROXY=1
```

也可以临时用命令行开启：

```powershell
python .\auto_seuwlan.py --use-system-proxy
```

## 配置说明

- `SEUWLAN_USERNAME`: 统一身份认证账号或校园网账号。
- `SEUWLAN_PASSWORD`: 密码。
- `SEUWLAN_WIFI_PROFILE`: Windows 里保存的 Wi-Fi 配置名，默认 `SEU-WLAN`。
- `SEUWLAN_LOGIN_URL`: 可选，校园网认证跳转链接。
- `SEUWLAN_ISP`: 校园网留空；运营商账号可填 `c/cmcc`、`t/telecom`、`u/unicom`。
- `SEUWLAN_INTERVAL`: 常驻模式检查间隔，默认 60 秒。
- `SEUWLAN_USE_SYSTEM_PROXY`: 默认 `0`，表示认证和联网探测均绕过系统代理。

## 注意

如果 `python .\auto_seuwlan.py --detect` 显示 `unknown`，说明当前链接不是已实现的 SEU eportal 类型。把 `seuwlan.md` 里实际跳转链接贴出来后，可以继续补对应认证流程。
