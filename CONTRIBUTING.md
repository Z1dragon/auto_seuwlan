# Contributing

感谢你改进 `auto-seuwlan`。提交前请注意：

1. 不要提交 `.env`、真实账号、密码、完整 Portal URL、真实 `UserIP` 或日志。
2. 修改认证参数时，请说明对应的 Portal 链接形态和脱敏后的响应摘要。
3. 保持脚本无第三方依赖，除非确实有必要。
4. Windows 计划任务相关改动请同时更新 `install_task.ps1`、`uninstall_task.ps1` 和 README。

本地检查：

```powershell
python -m py_compile .\auto_seuwlan.py
python -m unittest discover -s tests
python .\auto_seuwlan.py --doctor
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_task.ps1 -DryRun
```

提交 issue 时请尽量提供：

- 操作系统和 Python 版本。
- `python .\auto_seuwlan.py --doctor` 的输出，先确认没有敏感信息。
- 脱敏后的 Portal 链接形态。
- `logs\auto_seuwlan.log` 中与问题相关的几行，先删除账号、IP、AP 名称等信息。
