# Windows 打包

产品只发布 Windows 安装包。构建分两步：PyInstaller 生成 `dist\VidGlean\` 目录，Inno Setup 把它打成安装程序。

有两种构建方式：GitHub Actions（不用 Windows 机器）和本地 Windows 构建。

## 方式一：GitHub Actions（推荐）

仓库里有 `.github/workflows/build-windows.yml`，在 `windows-latest` 上跑完整流程。

**触发方式**

1. 打 tag 推送：`git tag v0.1.0 && git push origin v0.1.0`
   → 自动构建，并把安装包附到对应的 GitHub Release 上。
2. 手动触发：Actions 页面选 `Build Windows Installer` → `Run workflow`
   → 构建完成后在 run 页面的 Artifacts 里下载 `VidGlean-windows`。

**它做了什么**

```
uv sync --extra desktop --extra build   # 装 pywebview / pyinstaller
uv run pyinstaller packaging/vidglean.spec --noconfirm
choco install innosetup
ISCC packaging\vidglean.iss
```

产物：`dist/VidGlean/VidGlean.exe`（免安装目录版）与 `dist/VidGlean-0.1.0-setup.exe`（安装包）。

## 方式二：本地 Windows 构建

前置条件：

- Windows 10 / 11 x64
- Python 3.12 与 [uv](https://docs.astral.sh/uv/)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)（`ISCC.exe` 在 PATH 中）

在仓库根目录：

```powershell
uv sync --extra desktop --extra build
uv run pyinstaller packaging/vidglean.spec --noconfirm
iscc packaging\vidglean.iss
```

或者直接跑 `packaging\build.ps1`，它把三步串起来。

## 说明

- `onedir` 而不是 `onefile`：启动快，更新时只替换目录。
- 入口是 `packaging/entry.py`；启动失败会把 traceback 写到
  `%LOCALAPPDATA%\VidGlean\logs\startup-error.log` 并弹窗提示（因为 exe 没有控制台）。
- 冻结后前端资源从 `_MEIPASS/vidglean/web` 读取，`api/server.py` 里已做兼容。
- 目标机器需要 WebView2 Runtime：Windows 11 自带，Windows 10 可能缺失。
- 未做代码签名，首次运行会有 SmartScreen 提示。
- 安装包卸载时会询问是否删除用户数据，默认保留。
- 更新流程（第一版只做到「检查更新」）：下载 zip → 校验 sha256 → 备份当前目录 → 解压覆盖 → 重启，失败从备份恢复。更新源返回 JSON：
  ```json
  {"version": "0.1.1", "notes": "更新说明", "url": "https://example.com/vidglean-0.1.1.zip", "sha256": "..."}
  ```

## 版本号

`packaging/vidglean.iss` 里的 `AppVersion` 与 `pyproject.toml` 的 `version` 需要手动保持一致。
