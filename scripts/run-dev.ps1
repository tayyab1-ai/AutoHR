# Start AutoHR Django dev server (from repo root)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "backend")
& ".\.venv\Scripts\python.exe" manage.py runserver @args
