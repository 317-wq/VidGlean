# 在 Windows 上建立到 Linux 的 SSH 端口转发：
# 把 Windows 的 127.0.0.1:8765 转发到 Linux 的 127.0.0.1:8765。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\forward.ps1
#       powershell -File scripts\forward.ps1 -User ljt -HostName 192.168.107.128 -Port 8765
param(
    [string]$User = "ljt",
    [string]$HostName = "192.168.107.128",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

Write-Host "正在建立转发：127.0.0.1:$Port  ->  ${HostName}:127.0.0.1:$Port"
Write-Host "保持这个窗口开着；按 Ctrl+C 断开。"

ssh -N `
    -o ExitOnForwardFailure=yes `
    -o BatchMode=yes `
    -o StrictHostKeyChecking=no `
    -o ServerAliveInterval=30 `
    -o ServerAliveCountMax=3 `
    -L "127.0.0.1:${Port}:127.0.0.1:${Port}" `
    "$User@$HostName"
