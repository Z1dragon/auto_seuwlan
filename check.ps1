$ErrorActionPreference = "Stop"

python -m py_compile .\auto_seuwlan.py
python -m unittest discover -s tests
python .\auto_seuwlan.py --doctor
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_task.ps1 -DryRun

Write-Host "All checks passed."
