# Word Format Agent

基于 LangGraph + LangChain 的 Word 文档智能格式化 Agent。用户上传 `.docx` → Agent 解析需求 → 自动改格式 → 校验/修复 → 预览/导出。

前后端分离：`backend/`（Python FastAPI + LangGraph） + `frontend/`（Next.js）。

## 功能特性

- 自然语言需求解析：口语化格式要求自动转为结构化规则（DeepSeek）
- 完整 Agent 工作流：加载 → 分析 → 需求解析 → 规则 → 规划 → 执行 → 校验 → 修复重试 → 交付
- 中文排版：中文字号换算（三号=16pt 等）、首行缩进 2 字符
- 内置规则模板：论文 / SOP / 合同 / 通用，按关键词自动匹配
- 校验闭环：结构校验 + 规则校验 + 前后 diff + PDF/PNG 视觉渲染
- Web 界面：上传、填需求、进度追踪、预览、下载、撤销上一步
- 可回滚：每步操作记录快照，支持 undo
- PostgreSQL 持久化：任务状态、规则、报告等元数据入库

## 架构

```
前端（Next.js）：上传 .docx、填写需求、查看预览、下载结果
        ↓ HTTP
API 层（FastAPI）：上传、任务管理、状态查询
        ↓
Agent 编排层（LangGraph）：解析需求 → 分析文档 → 制定方案 → 执行 → 校验 → 修复 → 交付
        ↓
文档引擎层：python-docx（结构化读写）+ win32com（Word COM 渲染 PDF）
        ↓
校验层：结构校验、格式规则校验、前后 diff、PDF/PNG 渲染
```

## Agent 工作流

基于 LangGraph 的状态图，节点流转如下：

```text
load_document → analyze_document → parse_requirements → build_rules
  → plan_format → execute_plan → verify_step
       │
       ├── 校验通过 ──────────────→ finish_and_render
       └── 校验失败（未超重试上限）→ fix_and_retry → execute_plan
```

| 节点 | 职责 |
| --- | --- |
| load_document | 读取 docx 为文档模型 |
| analyze_document | 生成结构摘要（标题层级 / 段落 / 样式分布） |
| parse_requirements | 调用 DeepSeek 解析自然语言需求 |
| build_rules | 需求 → 格式规则 JSON |
| plan_format | 规则 → 操作步骤数组 |
| execute_plan | 逐条执行格式工具 |
| verify_step | 规则校验 + 结构校验 |
| fix_and_retry | 失败时修复并重试（最多 N 次） |
| finish_and_render | 保存 docx、渲染 PDF/PNG、生成报告 |

## 工具集

Agent 通过以下工具操作文档（实现位于 `backend/engine/controller.py`）：

| 工具 | 作用 |
| --- | --- |
| read_document | 读取 docx 为文档模型 |
| get_document_overview | 返回标题层级、段落、样式摘要 |
| get_paragraph_detail | 查看某段完整格式 |
| set_heading_style | 把段落设为 Heading 1/2/3 或自定义标题 |
| set_paragraph_format | 对齐、缩进、行距、段前段后 |
| set_run_font | 字体、中文字体、字号、粗斜体、颜色 |
| apply_style | 应用命名样式 |
| modify_style_definition | 全局修改某样式定义 |
| set_section_format | 页边距、纸张、分节 |
| set_header_footer | 页眉、页脚 |
| set_table_font | 表格字体 |
| update_toc | 更新目录（Word COM） |
| save_document | 保存 docx |
| undo_last | 回滚上一步 |

所有工具返回结构化结果：

```json
{"ok": true, "changed": ["p_001"], "message": "已应用 Heading 1：黑体 16pt，居中"}
```

## 校验闭环

- **结构校验**：标题层级是否连续、段落是否遗漏、表格是否完整
- **规则校验**：抽查段落字号、字体、行距、缩进是否符合规则
- **Diff 报告**：修改前后逐段对比，列出新增 / 修改 / 删除
- **视觉校验**：Word COM 导出 PDF → 转 PNG → 确认布局无错乱

## 目录结构

```
WordEditAgent/
├── backend/             # Python 后端
│   ├── app/             # FastAPI 入口、API 路由、配置、数据库、后台任务
│   ├── agent/           # LangGraph 工作流、状态、节点、工具、提示词、LLM
│   ├── engine/          # 文档模型、读取、写入、格式化、控制器、Word COM、备份
│   ├── verify/          # 结构校验、规则校验、diff 报告、渲染
│   ├── rules/           # 默认/论文/SOP/合同规则 + 中文单位换算
│   ├── scripts/         # 生成示例 docx
│   ├── tests/           # 单元 / 集成 / 端到端测试
│   ├── uploads/         # 上传目录（运行时）
│   ├── outputs/         # 输出目录（运行时）
│   ├── templates/       # 模板目录
│   ├── requirements.txt
│   ├── .env             # 环境变量（已 gitignore）
│   └── .env.example
├── frontend/            # 前端（Next.js 16 + React 19 + Tailwind）
│   ├── app/             # 页面与布局
│   ├── lib/             # API 客户端
│   ├── public/
│   └── package.json
├── docker-compose.yml   # PostgreSQL 17-alpine
└── README.md
```

## 环境要求

- Python 3.12+
- Node.js 18+ / pnpm
- Docker + Docker Compose（用于 PostgreSQL）
- Windows + Microsoft Word（用于 PDF/PNG 预览渲染，可选）

## 快速开始

### 1. 启动 PostgreSQL（Docker）

在项目根目录执行：

```powershell
docker compose up -d
```

镜像为 `postgres:17-alpine`，数据持久化在 `./data/postgres`。

### 2. 启动后端

```powershell
cd backend

# 首次：创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> 若 PowerShell 提示「禁止运行脚本」，先执行一次：
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

后端配置位于 `backend/.env`，从 `backend/.env.example` 复制：

```ini
# DeepSeek API（OpenAI 兼容接口）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# PostgreSQL（与 docker-compose.yml 保持一致）
DATABASE_URL=postgresql+psycopg2://wordagent:wordagent@localhost:5432/wordedit
```

后端地址：

- API 文档（Swagger）：http://127.0.0.1:8000/docs
- 服务信息：http://127.0.0.1:8000/

### 3. 启动前端

```powershell
cd frontend

# 首次：安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

浏览器访问 http://localhost:3000（若端口被占用会自动切换，如 3001）。

> 前端通过环境变量 `NEXT_PUBLIC_API_BASE` 指定后端地址，默认 `http://localhost:8000`。如需修改，在 `frontend/.env.local` 中配置。

## API 使用

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/upload` | 上传 `.docx`，返回 `file_id` |
| POST | `/api/tasks` | 创建格式化任务（传 `file_id` + `requirements`） |
| GET | `/api/tasks/{id}` | 查询任务状态与进度 |
| GET | `/api/tasks/{id}/preview?type=png\|pdf` | 获取预览 |
| GET | `/api/tasks/{id}/download` | 下载结果 docx |
| POST | `/api/tasks/{id}/undo` | 撤销上一步 |

示例流程：

```powershell
# 上传
curl.exe -s -X POST http://127.0.0.1:8000/api/upload -F "file=@uploads/sample.docx"

# 创建任务
curl.exe -s -X POST http://127.0.0.1:8000/api/tasks `
  -H "Content-Type: application/json" `
  -d '{"file_id":"<file_id>","requirements":"标题黑体三号居中，正文宋体小四，1.5倍行距，首行缩进2字符，两端对齐"}'

# 查询状态
curl.exe -s http://127.0.0.1:8000/api/tasks/<task_id>

# 下载结果
curl.exe -s -o result.docx http://127.0.0.1:8000/api/tasks/<task_id>/download
```

## 规则模板

内置格式规则模板（`backend/rules/*.json`），会根据需求关键词自动匹配：

- `default.json` — 通用文档
- `thesis.json` — 学位论文（含「论文/学位/摘要/参考文献」等关键词）
- `contract.json` — 合同（含「合同/甲方/乙方/协议」）
- `sop.json` — 标准作业程序（含「SOP/流程/操作规范」）

中文排版单位换算：

| 中文字号 | 磅值(pt) |
| --- | --- |
| 三号 | 16 |
| 小三 | 15 |
| 四号 | 14 |
| 小四 | 12 |
| 五号 | 10.5 |
| 小五 | 9 |

「2字符」缩进写入 `w:firstLineChars="200"`。

口语需求解析为规则 JSON，例如「标题黑体三号，正文宋体小四，1.5 倍行距，首行缩进 2 字符」：

```json
{
  "headings": [
    {"level": 1, "font": "黑体", "size": 16, "bold": true, "alignment": "center"}
  ],
  "body": {
    "font": "宋体", "size": 12,
    "line_spacing": 1.5,
    "first_line_indent": "2字符",
    "alignment": "justify"
  },
  "page": {"size": "A4", "margins": {"top": 2.54, "bottom": 2.54, "left": 3.17, "right": 3.17}}
}
```

## 运行测试

在 `backend/` 目录下执行：

```powershell
# 单元 / 集成测试（无需网络）
pytest tests/test_rules.py tests/test_engine.py tests/test_verify.py tests/test_agent_plan.py -q

# 端到端测试（需要 DeepSeek 网络，可选 Word COM）
pytest tests/test_e2e.py -q -s
```

## 生成示例文档

在 `backend/` 目录下执行：

```powershell
python -m scripts.generate_sample
```

会在 `backend/uploads/sample.docx` 生成一份中文示例文档，可用于上传测试。

## 服务器部署（Linux）

项目不依赖任何绝对路径，可直接在 Linux 服务器部署。前后端分离，可按需单独部署。

### 1. 启动 PostgreSQL

```bash
docker compose up -d
```

### 2. 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env   # 编辑填入 DEEPSEEK_API_KEY 等

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> PDF/PNG 预览依赖 Windows 上的 Microsoft Word（Word COM），Linux 环境无法使用；文档格式化与 docx 下载功能不受影响。

### 3. 启动前端

```bash
cd frontend
pnpm install

# 生产模式（推荐）
NEXT_PUBLIC_API_BASE=http://<服务器地址>:8000 pnpm build
pnpm start -p 3000

# 或开发模式
NEXT_PUBLIC_API_BASE=http://<服务器地址>:8000 pnpm dev
```

前端通过环境变量 `NEXT_PUBLIC_API_BASE` 指定后端地址，默认 `http://localhost:8000`。

## 说明

- PDF/PNG 预览依赖 Windows 上的 Microsoft Word（通过 Word COM），在独立子进程中执行以隔离崩溃；未安装 Word 时仍可正常格式化并下载 docx，仅预览不可用。
- 任务状态、进度、格式化规则、修改报告等元数据存储在 PostgreSQL；原始文件与结果文件分别保存在 `backend/uploads/` 与 `backend/outputs/`。
