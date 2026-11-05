# Windows 打包

第一版只发布 Windows 安装包，流程分三步：Python 依赖 → PyInstaller → Inno Setup。

## 前置条件

- Windows 10 / 11 x64
- Python 3.12 与 [uv](https://docs.astral.sh/uv/)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)（`ISCC.exe` 在 PATH 中）
- 目标机器需要 WebView2 Runtime（Windows 11 自带；Windows 10 可能缺失，安装时引导安装 Evergreen Runtime）

## 构建

在仓库根目录执行：

```powershell
uv sync --extra desktop --extra build
uv run pyinstaller packaging/vidglean.spec --noconfirm
iscc packaging/vidglean.iss
```

产物：

- `dist\VidGlean\VidGlean.exe`：免安装目录版，可直接运行
- `dist\VidGlean-0.1.0-setup.exe`：安装包

`packaging/build.ps1` 把上面三步合在一起。

## 说明

- 使用 `onedir` 而不是 `onefile`：启动快，更新时只需要替换目录。
- 未做代码签名，首次运行会有 SmartScreen 提示，安装说明里需要写明。
- 更新流程：检查更新 → 下载 zip → 校验 sha256 → 备份当前目录 → 解压覆盖 → 重启；失败时从备份目录恢复。更新源地址在设置页配置，返回 JSON：
  ```json
  {"version": "0.1.1", "notes": "更新说明", "url": "https://example.com/vidglean-0.1.1.zip", "sha256": "..."}
  ```
- 安装包在卸载时会询问是否删除用户数据，默认保留。
