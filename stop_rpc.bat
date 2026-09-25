@echo off
echo Arret du Discord RPC Antigravity...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*antigravity_rpc.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Discord RPC arrete.
