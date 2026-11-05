# VidGlean

把 B 站视频变成结构化 Markdown 知识文档的本地桌面工具。

粘贴一个链接 → 抓字幕 → AI 提炼 → 落成一篇可长期保存、可检索的 `.md`。
数据、模型 Key、凭证全部留在本地，不经过任何中间服务器。

[![Build Windows Installer](https://github.com/317-wq/VidGlean/actions/workflows/build-windows.yml/badge.svg)](https://github.com/317-wq/VidGlean/actions/workflows/build-windows.yml)
[![Release](https://img.shields.io/github/v/release/317-wq/VidGlean?label=release)](https://github.com/317-wq/VidGlean/releases)

## 下载安装（Windows 10 / 11）

到 [Releases](https://github.com/317-wq/VidGlean/releases) 下载最新的 `VidGlean-*-setup.exe`，双击安装。

- 首次运行时 Windows 会拦（未签名）→ 点「更多信息」→「仍要运行」
- 需要 **WebView2 Runtime**：Windows 11 自带；Windows 10 若缺失，窗口会白屏，装一次 Evergreen Runtime 即可
- 数据默认存放在 `%LOCALAPPDATA%\VidGlean`，卸载时会问是否一并删除
- 启动失败先看 `%LOCALAPPDATA%\VidGlean\logs\startup-error.log`

首次进入软件后，在「设置」里做两件事：

1. **模型**：添加一个 OpenAI 兼容服务（Base URL、模型名、API Key），可点「测试」验证连通性
2. **B 站**：填入 SESSDATA（不填通常拿不到字幕）

## 功能

- **导入**：B 站视频页链接、`b23.tv` 短链、BV 号；解析标题、封面、UP 主、时长、类型；重复视频自动识别
- **字幕**：优先中文 CC 字幕；「凭证过期」与「视频没有字幕」分开提示
- **AI 总结**：9 套内容类型模板、三档深度、额外要求、长字幕分段提炼后合并、自动生成标签
- **Markdown 文档**：磁盘 `.md` 是内容真源，阅读页渲染代码块/表格/公式，源码编辑自动保存，可回退上一版
- **任务引擎**：四阶段执行、失败从失败阶段续跑、暂停/继续/取消、视频与 AI 双并发限制、指数退避重试、崩溃标记为中断
- **文档管理**：分类（可重命名/删除）、标签、星标、中文全文搜索（FTS5 + 二元分词）
- **AI 对话**：每篇文档独立上下文，流式输出，可清空
- **AI 辅助修改**：先出 diff 预览，确认后才改正文
- **模板**：内置 9 套 + 自定义上传（变量校验、重名检查、默认模板）
- **数据**：SQLite 索引 + 文件正文，备份/加密备份/恢复，数据目录可迁移，临时文件清理
- **其他**：三套主题、快捷键、启动页、日志轮转与脱敏、Token 用量统计

## 文档

| 文档 | 内容 |
|---|---|
| [docs/PRD.md](docs/PRD.md) | 产品需求（V1.1） |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 技术选型、进程模型、数据模型、接口、与需求的已知差异 |
| [docs/TEMPLATES.md](docs/TEMPLATES.md) | 模板规范与 9 套内置模板全文 |
| [docs/BUILD.md](docs/BUILD.md) | Windows 打包与发版流程 |
| [docs/CHECKLIST.md](docs/CHECKLIST.md) | 开发清单（已完成 / 待验证） |

## 从源码运行

需要 [uv](https://docs.astral.sh/uv/) 和 Python 3.12。

```bash
uv sync                               # 安装依赖
uv run vidglean                       # 桌面窗口（Windows 需先 uv sync --extra desktop）
uv run vidglean --serve --port 8765   # 只起 HTTP 服务，用浏览器访问
```

端口被占用会自动往后找可用端口并打印实际地址。

### 远程开发（Linux 上跑、Windows 上开）

`127.0.0.1` 在两边是不同机器，直接访问必然连不上。三选一：

| 做法 | 命令 | 说明 |
|---|---|---|
| VS Code 端口转发 | 端口面板添加 `8765` | 最省事，跟着 Remote-SSH 走 |
| 独立 SSH 隧道 | `powershell -File scripts\forward.ps1` | 不开 VS Code 时用 |
| 直接对外监听 | `uv run vidglean --serve --host 0.0.0.0` | 会生成访问令牌，用打印出来的局域网地址打开 |

## 开发

```bash
uv run ruff check .     # 静态检查
uv run pytest           # 测试（39 项）
```

## 目录

```
docs/            产品、架构、模板与打包文档
packaging/       PyInstaller / Inno Setup 打包脚本 + 中文语言包
scripts/         Windows 端口转发脚本
src/vidglean/    应用代码
  api/           FastAPI 路由
  pipeline/      任务引擎与阶段
  platforms/     平台适配（当前仅 Bilibili）
  ai/            模型客户端与提示词
  store/         SQLite、仓储与检索
  web/           前端静态资源（含 KaTeX）
main.py          开发期冒烟脚本
```

## 发版

打 tag 推送即可，GitHub Actions 会构建并发布安装包：

```bash
git tag v0.1.1 && git push origin v0.1.1
```

也可以在 Actions 页面手动触发 `Build Windows Installer`，从 Artifacts 下载。

## 已知限制

- 自动更新只做到「检查更新」，下载替换仍需手动（流程见 `docs/BUILD.md`）
- 桌面通知未接入 Windows 通知中心，只有软件内提示
- 费用统计只累计 Token，未内置各厂商价格表，金额记 0
- 代码未签名，安装包会触发 SmartScreen 提示
- 第一版只支持 Bilibili，抖音、本地视频、ASR、时间戳均在后续规划内

## 许可证

[MIT](LICENSE) © 2026 317-wq

内置的 KaTeX（公式渲染）遵循其自身的 MIT 许可，其他第三方依赖见各自的开源许可。

