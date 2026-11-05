# VidGlean 技术架构

**状态：** 第一版已确定，实现过程中可局部调整
**对应需求：** `docs/PRD.md` V1.1
**适用范围：** Windows 10 / 11，仅 Bilibili，仅视频链接导入

---

## 1. 设计原则

1. **只用一种语言**：全部 Python + 原生前端。不引入 Node、不引入前端构建链。
2. **只用一个进程**：窗口、HTTP 服务、任务执行都在同一个进程内。
3. **文件是数据，数据库是索引**：正文存 `.md`，SQLite 只存元数据和索引。
4. **阶段之间用磁盘产物对接**：不靠内存对象传递状态，断点续跑天然成立。
5. **标准库优先**：能在 `sqlite3`、`logging`、`asyncio` 里解决的不引第三方。

对应 PRD 的原则：文档优先、本地优先、渐进开发。

## 2. 技术栈

| 层 | 选型 | 为什么 | 不选什么 |
|---|---|---|---|
| 语言 / 环境 | Python 3.12 + uv | 项目已有 Python 依赖 | |
| 桌面壳 | pywebview（WebView2） | 单进程、无 Node、无 IPC 设计 | Electron（多一条 node + 打包 + IPC 工具链） |
| 后端 | FastAPI + uvicorn | 原生 async，SSE 简单 | Flask（异步任务要另绕一层） |
| 前端 | 原生 HTML / CSS / ES Module | 零构建，改完刷新即生效 | React + Vite（多一条构建链） |
| Markdown 渲染 | python-markdown + Pygments（后端渲染）+ KaTeX（前端公式） | 渲染与高亮只有一处实现，前端零 JS 依赖 | 前端 marked + highlight.js（多两个 JS 依赖，公式仍要两边处理） |
| 编辑器 | textarea + 自动保存 | PRD 6.2 只要求源码编辑 | CodeMirror（体积与集成成本） |
| 数据库 | SQLite（`sqlite3`，WAL） | 单机、单用户、零运维 | ORM（SQL 直接写更短） |
| 全文检索 | FTS5 + 二元分词（bigram） | 中文可搜，零依赖 | jieba（多一个依赖和词典体积） |
| AI | `openai.AsyncOpenAI` | 兼容任意 OpenAI 协议服务 | 各家 SDK 分别对接 |
| B 站 | `bilibili-api-python` | 已验证可用（`main.py`） | 自己签名 |
| 凭证 | `keyring`（Windows 凭据管理器） | PRD 17.2 | 明文配置 |
| 日志 | `logging` + `RotatingFileHandler` | 标准库 | 日志框架 |
| 测试 / 检查 | pytest + ruff | 够用 | mypy（第一版不加类型门禁） |
| 打包 | PyInstaller `onedir` + Inno Setup | 启动快，更新只换目录 | onefile（每次启动解压） |

依赖清单以 `pyproject.toml` 为准。`pywebview` 放在 `desktop` extra 里，Linux 开发机不安装。

## 3. 进程与线程模型

```
vidglean.exe
├─ 主线程        pywebview 事件循环（WebView2 窗口）
├─ 后台线程      uvicorn → FastAPI（127.0.0.1，随机端口）
│                 └─ asyncio 事件循环
│                     ├─ HTTP / SSE 请求处理
│                     └─ 任务 worker（视频任务并发 2，AI 调用并发 2）
└─ 后台线程      定时器：重试调度 tick、日志清理
```

**单实例**：启动时先抢占固定端口 `47821`。抢占失败说明已有实例在运行，直接退出（第一版不做「唤起已有窗口」，避免引入 IPC）。

**服务端口**：真正的 HTTP 服务用随机空闲端口，前端 URL 在创建窗口时注入，避免端口冲突。

**访问控制**：服务只监听 `127.0.0.1`；启动时生成一次性 token，通过窗口 URL 的 query 传给前端，前端存内存，所有 `/api/*` 请求带 `X-VG-Token` 头。这样本机其它网页即使猜到端口也调不动。

**关闭**：窗口关闭 → 置 uvicorn 退出标志 → 最多等 10 秒让 worker 把当前阶段结果落盘 → 进程退出。超过 10 秒强制退出，未完成的阶段保留为「中断」。

## 4. 目录结构

### 代码

```
VidGlean/
├─ pyproject.toml
├─ main.py                     # 开发期冒烟脚本，保持可运行
├─ docs/
│  ├─ PRD.md
│  └─ ARCHITECTURE.md
├─ src/vidglean/
│  ├─ __init__.py              # __version__ + main() 入口
│  ├─ app.py                   # 组装：单实例、端口、token、uvicorn 线程、窗口
│  ├─ config.py                # 数据目录、默认设置、settings 读写
│  ├─ api/                     # FastAPI 路由，按资源拆文件
│  ├─ core/                    # dataclass 领域模型、错误类型、事件
│  ├─ platforms/bilibili.py    # 链接识别、元信息、字幕
│  ├─ pipeline/                # 阶段定义、状态机、worker、重试
│  ├─ ai/                      # client / prompt / 分块 / 输出解析
│  ├─ store/                   # db、migrations、repo、search
│  ├─ security/                # keyring、日志脱敏
│  └─ web/                     # 静态资源：html / css / js / vendor
└─ tests/
```

### 运行时数据目录

默认 `%LOCALAPPDATA%\VidGlean`，可在设置中修改（PRD 13.2）。

```
VidGlean/
├─ vidglean.db
├─ documents/<doc_id>.md        # 正文真源，文件名用 ID，标题存 DB
├─ subtitles/<platform>-<video_id>.json
├─ tasks/<task_id>/01_meta.json
├─ tasks/<task_id>/02_subtitle.json
├─ tasks/<task_id>/03_summary.md
├─ logs/vidglean.log
└─ tmp/
```

## 5. 核心链路

```
输入链接
  → 解析（平台适配器）        → tasks/<id>/01_meta.json
  → 字幕获取                  → tasks/<id>/02_subtitle.json
  → AI 分析 + 成文            → tasks/<id>/03_summary.md
  → 落盘为文档                → documents/<doc_id>.md
  → 更新索引                  → documents + documents_fts
```

每一步先写产物文件，成功后再改数据库状态。因此：任一阶段失败，前面产物都在；重试从失败阶段开始；进程崩溃后产物不丢。

`main.py` 的行为可以视为这条链路的单文件版本，迁移时保持它的输出语义（Markdown 正文 + 文首视频元信息）。

## 6. 任务引擎

### 6.1 状态

任务状态：`pending` / `running` / `paused` / `succeeded` / `failed` / `canceled` / `interrupted`

阶段：`link_parse` / `subtitle` / `ai_analyze` / `render_md`

阶段状态：`pending` / `running` / `succeeded` / `failed` / `skipped`

### 6.2 规则

- **幂等**：阶段启动前检查产物是否存在且有效，存在则标记 `skipped` 直接跳过。
- **重试**：只重跑 `failed` 阶段及其下游，上游不动（PRD 4.3）。
- **并发**：`asyncio.Semaphore(2)` 控制视频任务，`Semaphore(2)` 控制 AI 请求；队列 FIFO；数值可配（PRD 4.5）。
- **退避**：第 n 次重试等待 `min(2**n, 30)` 秒并加 0~1 秒抖动；默认最多 3 次，可配 1~10（PRD 16.5 / 16.6）。
- **不重试的错误**：链接非法、平台不支持、视频不存在、无字幕、凭证失效、API Key 无效、余额不足、模型不存在。
- **暂停**：在当前阶段边界停下，不打断进行中的 HTTP 请求；恢复时从该阶段开始。
- **取消**：停止后续阶段，保留已产出的文件和字幕，不删除文档（PRD 4.4）。
- **崩溃**：启动时把 `running` 任务统一改成 `interrupted`，不自动恢复，首页提示用户手动重试（PRD 4.7）。
- **调度**：进程内一个调度循环，每 500ms 扫一次 `pending` 和到期的 `failed`，不引入队列中间件。

## 7. 数据模型（SQLite）

关键表（字段为实现草案，细节可在建表时微调）：

```sql
documents(id TEXT PRIMARY KEY, platform TEXT, video_id TEXT, title TEXT, author TEXT,
          cover_url TEXT, duration INTEGER, source_url TEXT, content_type TEXT,
          summary_depth TEXT, template_id TEXT, starred INTEGER DEFAULT 0,
          file_path TEXT, file_mtime REAL, status TEXT,
          created_at TEXT, updated_at TEXT)

categories(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, created_at TEXT)
document_categories(document_id TEXT, category_id TEXT, PRIMARY KEY(document_id, category_id))

tags(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL)
document_tags(document_id TEXT, tag_id TEXT, PRIMARY KEY(document_id, tag_id))

notes(document_id TEXT PRIMARY KEY, content TEXT, updated_at TEXT)

messages(id TEXT PRIMARY KEY, document_id TEXT, role TEXT, content TEXT, created_at TEXT)

tasks(id TEXT PRIMARY KEY, document_id TEXT, source_url TEXT, video_id TEXT,
      status TEXT, current_stage TEXT, retry_count INTEGER DEFAULT 0,
      next_retry_at TEXT, created_at TEXT, updated_at TEXT)

task_stages(task_id TEXT, stage TEXT, status TEXT, error_code TEXT,
            error_message TEXT, started_at TEXT, finished_at TEXT,
            PRIMARY KEY(task_id, stage))

models(id TEXT PRIMARY KEY, name TEXT, base_url TEXT, model TEXT,
       temperature REAL, max_tokens INTEGER, timeout INTEGER, is_current INTEGER)

templates(id TEXT PRIMARY KEY, name TEXT UNIQUE, kind TEXT, description TEXT,
          path TEXT, created_at TEXT)

usage(id TEXT PRIMARY KEY, document_id TEXT, task_id TEXT, kind TEXT, model_id TEXT,
      prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
      estimated_cost REAL, created_at TEXT)

settings(key TEXT PRIMARY KEY, value TEXT)

documents_fts USING fts5(doc_id UNINDEXED, title, body, tags, tokenize='unicode61')
```

约定：

- 正文不重复入库；`documents.file_path` 指向 `.md`，`file_mtime` 用于检测外部修改。
- 搜索表存二元分词（bigram）后的文本，查询也走同一切词器。
- 迁移用 `migrations.py` 里的有序列表 + `PRAGMA user_version`，不引迁移框架。

## 8. HTTP 接口

统一响应：`{"ok": true, "data": ...}` 或 `{"ok": false, "error": {"code": "...", "message": "..."}}`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 启动自检，供 Splash 使用 |
| POST | `/api/import/preview` | 批量链接预览（标题、封面、时长、重复标记） |
| POST | `/api/import` | 确认导入，创建任务 |
| GET | `/api/tasks` | 任务列表（分页、筛选） |
| GET | `/api/tasks/{id}` | 任务详情 + 各阶段状态 |
| POST | `/api/tasks/{id}/retry` | 从失败阶段重试 |
| POST | `/api/tasks/{id}/pause` `/resume` `/cancel` | 任务控制 |
| GET | `/api/events` | SSE：任务进度、文档变更 |
| GET | `/api/documents` | 列表/搜索（`q`、`type`、`platform`、`starred`、分页） |
| GET | `/api/documents/{id}` | 元信息 + 正文 |
| PUT | `/api/documents/{id}/content` | 保存正文（先写文件再更新索引） |
| PATCH | `/api/documents/{id}` | 标题、星标、标签、分类 |
| DELETE | `/api/documents/{id}` | 删除（文件进回收站） |
| POST | `/api/documents/{id}/regenerate` | 重新生成总结 |
| POST | `/api/documents/{id}/assist` | AI 修改，返回 diff 预览 |
| POST | `/api/documents/{id}/assist/apply` | 确认应用 |
| GET/POST | `/api/documents/{id}/messages` | 文档对话历史 / 发送（SSE 流式） |
| CRUD | `/api/categories` `/api/tags` `/api/templates` | 分类、标签、模板 |
| CRUD | `/api/models` + `POST /api/models/{id}/test` | 模型配置与连通性测试 |
| GET/PUT | `/api/settings` | 设置读写 |
| POST | `/api/backup` `/api/restore` | 备份与恢复 |
| GET | `/api/logs/export` | 导出日志（脱敏） |

SSE 事件格式：`event: task`、`data: {"task_id": "...", "status": "...", "stage": "...", "progress": 0.6}`。

## 9. 前端

- 页面：文档中心（首页）、阅读页、任务页、设置页。hash 路由 `#/home`、`#/starred`、`#/doc/<id>`、`#/tasks`、`#/settings`。
- 状态：没有状态库，页面渲染时把 `state` 对象传进视图函数，事件（SSE）触发重新渲染。
- 主题：`<html data-theme="light|dark|soft">` + CSS 变量，三套主题只换变量。
- 阅读页：正文 HTML 由后端渲染（含代码高亮），前端只做 KaTeX 公式渲染和外链处理。
- 编辑页：textarea 全屏，`Ctrl+S` 立即保存，平时 1.2 秒防抖自动保存（不产生版本），保存中/已保存用状态条提示。
- 列表：默认卡片，`localStorage` 记住卡片/列表切换；分页 50 条。
- 搜索：输入框 300ms 防抖，直接请求 `/api/documents?q=`，命中片段由后端返回。

第三方库以固定版本放在 `src/vidglean/web/vendor/`，不走 CDN（离线可用）。

## 10. 搜索

- 写入时：标题 + 正文 + 标签 → 二元分词（CJK 取相邻两字，ASCII 按单词）→ 空格拼接存 `documents_fts.body`。
- 查询时：同样切词后用 FTS5 `MATCH`（词之间 AND），`bm25()` 排序；单字查询退化为 `LIKE`。
- 片段：按命中的词在原文里定位，取前后各 60 字，返回给前端。
- 正文来自文件：命中后按 `doc_id` 读文件，不用 DB 副本。

## 11. 凭证与日志

- keyring service 固定为 `vidglean`。
  - `model:<model_id>` → AI API Key
  - `bilibili:sessdata` → B 站凭证
- 日志：`logs/vidglean.log`，单文件 5MB 轮转，保留 30 天（PRD 16.4），导出时按时间范围过滤。
- 脱敏：日志 Filter 统一替换 `SESSDATA=`、`sk-...`、`Authorization:` 三类内容；错误详情在入库前也走同一过滤器。

## 12. 打包、安装、更新

- PyInstaller `onedir`，`web/` 作为 data 一起打包；入口是 `packaging/entry.py`（调用 `vidglean.app.cli`）。
- Inno Setup 生成单文件安装包：安装目录可选、桌面快捷方式、开始菜单、卸载时询问保留或删除用户数据（PRD 17.4）。
- 更新：检查更新 → 下载 zip → sha256 校验 → 备份当前目录 → 解压覆盖 → 重启；失败时从备份恢复（PRD 18.5）。不做增量更新。
- 代码签名第一版不做，接受 SmartScreen 警告，安装说明里写明。

## 13. 第一版明确不做

Electron / Tauri、ORM、Celery / Redis、WebSocket（SSE 够用）、前端打包器、ASR、抖音、本地视频、时间戳、云同步、多语言、账号体系。

## 14. 里程碑与实现状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| M0 | 入口 + 单实例 + 窗口 + `/api/health` + 静态页 | 代码完成，桌面窗口待 Windows 验证 |
| M1 | B 站链路：解析 → 字幕 → AI → 落盘 | 已在真实视频上跑通 |
| M2 | 任务引擎：状态机、重试、并发、SSE | 完成，单测覆盖状态机 |
| M3 | 文档管理：列表、分类、标签、星标、搜索 | 完成，中文搜索单测通过 |
| M4 | AI 对话、辅助修改、模板、模型配置、设置、日志 | 完成，对话流式已验证 |
| M5 | 打包、安装包、更新、备份恢复 | 备份恢复完成；打包脚本就绪，待 Windows 构建验证 |

## 15. 已知风险

1. **WebView2 运行时**：Windows 11 自带；Windows 10 可能缺，安装包需检测并引导安装 Evergreen Runtime。
2. **B 站接口**：`bilibili-api` 依赖平台接口，接口或风控变化会导致解析失败，需要清晰的错误提示与重试边界。
3. **SESSDATA 过期**：需要单独的错误码与提示，不能和「无字幕」混在一起。
4. **Inno Setup 无内置回滚**：更新回滚要自己实现目录备份与恢复。
5. **FTS5 二元分词**：对中英混排、代码片段的召回率需要实测，必要时对代码块加权重或跳过索引。

## 16. 与需求的已知差异

1. 桌面通知（PRD 15.6）目前只有软件内提示，未接 Windows 通知中心。
2. 自动更新（PRD 18.4）只实现检查更新与更新源配置，下载替换与回滚按 `docs/BUILD.md` 的手工流程执行。
3. 费用统计（PRD 12）只累计 Token，没有内置价格表，金额按 0 记录。
4. 关闭软件时（PRD 4.6）不弹「继续等待 / 保存退出」对话框，直接退出；未完成的任务下次启动标记为「已中断」，由用户决定是否重试。
5. AI 修改（PRD 5.9）只对整篇文档做修改，未做「指定章节」的局部修改。
