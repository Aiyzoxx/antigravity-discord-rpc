@echo off
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process pythonw -ArgumentList 'antigravity_rpc.py' -WorkingDirectory '%~dp0'"
