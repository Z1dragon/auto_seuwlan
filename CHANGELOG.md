# Changelog

## 0.2.0

- 增加 `--doctor` 诊断命令。
- 默认绕过系统代理，改善 VPN/代理场景下的 Portal 探测。
- 增加日志文件支持。
- 优先使用断网时实时探测到的 Portal URL，减少静态链接过期问题。
- 增加 Windows 计划任务安装、卸载和 dry-run 支持。
- 增加基础单元测试和公开发布文档。

## 0.1.0

- 支持 SEU-WLAN ePortal 登录 URL 类型识别。
- 支持单次认证和 daemon 模式。
