# Windows 构建脚本：依赖 -> PyInstaller -> Inno Setup
param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/3] 安装依赖"
uv sync --extra desktop --extra build

Write-Host "[2/3] PyInstaller 打包"
uv run pyinstaller packaging/vidglean.spec --noconfirm

Write-Host "[3/3] Inno Setup 生成安装包"
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    Write-Warning "未找到 ISCC.exe，跳过安装包生成。安装 Inno Setup 6 后重新执行。"
} else {
    & $iscc.FullName "packaging/vidglean.iss"
}

Write-Host "完成。产物在 dist/ 目录（版本 $Version）"
