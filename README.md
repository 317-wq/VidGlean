# VidGlean

本地 AI 视频总结工具：粘贴一个 B 站链接，得到一份结构清晰的 Markdown 知识文档。

第一版范围：Windows 10 / 11，仅 Bilibili，仅视频链接导入，不生成时间戳。

## 已实现

- B 站链接导入（视频页链接、`b23.tv` 短链、BV 号），解析标题、封面、UP 主、时长、类型
- 字幕获取（优先中文 CC 字幕，凭证失效与无字幕分开提示）
- AI 总结：三档深度、类型化结构、模板驱动、长字幕分段提炼、额外要求
- Markdown 文档：磁盘文件为真源，阅读页渲染、源码编辑与自动保存、版本回退
- 任务引擎：阶段化执行、失败续跑、暂停/继续/取消、并发限制、指数退避重试、崩溃标记
- 文档管理：分类、标签（AI 自动生成）、星标、全文搜索（中文二元分词）
- 文档专属 AI 对话（流式）、AI 辅助修改（diff 预览后确认）
- 模板：内置 3 套 + 自定义上传/校验/默认模板
- 模型配置：OpenAI 兼容接口、多模型、连通性测试
- 数据：SQLite + 本地目录、备份/加密备份/恢复、临时文件清理
- 日志：轮转、脱敏、按时间导出、过期清理
- 主题：浅色 / 深色 / 柔和蓝粉紫

## 文档

- [产品需求](docs/PRD.md)（V1.1）
- [技术架构](docs/ARCHITECTURE.md)
- [Windows 打包](docs/BUILD.md)

## 快速开始

需要 [uv](https://docs.astral.sh/uv/) 和 Python 3.12。

```bash
uv sync                               # 安装依赖，创建 .venv
uv run vidglean                       # 启动桌面窗口（Windows 需安装 desktop extra）
uv run vidglean --serve --port 8765   # 以 HTTP 服务方式启动，浏览器访问
```

首次启动后进入「设置」：添加一个 OpenAI 兼容模型（Base URL、模型名、API Key），并在「B 站」页填入 SESSDATA。

以 `--serve` 启动时如果端口被占用，会自动往后找一个可用端口，并打印实际访问地址。

`.env` 只用于开发期方便，正式运行时 API Key 与 SESSDATA 保存在系统凭据管理器（Windows Credential Manager）。

## 开发

```bash
uv run ruff check .     # 静态检查
uv run ruff format .    # 格式化
uv run pytest           # 测试
```

## 目录

```
docs/            产品、架构与打包文档
packaging/       PyInstaller / Inno Setup 打包脚本
src/vidglean/    应用代码
  api/           FastAPI 路由
  pipeline/      任务引擎与阶段
  platforms/     平台适配（当前仅 Bilibili）
  ai/            模型客户端与提示词
  store/         SQLite、仓储与检索
  web/           前端静态资源（含 KaTeX）
main.py          开发期冒烟脚本
```

## 已知限制

- 桌面窗口与系统通知依赖 Windows 环境；Linux 开发机只验证了 HTTP 服务与前端静态页。
- 自动更新只实现「检查更新」，下载与替换目录的流程见 `docs/BUILD.md`，尚未接入界面。
- 费用统计只累计 Token，未内置各厂商价格表，费用字段按 0 记录。
- 代码未签名，安装包首次运行会有 SmartScreen 提示。
