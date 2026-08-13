# Word Format Agent

基于 LangGraph + LangChain 的 Word 文档智能格式化 Agent。用户上传 `.docx` → Agent 解析需求 → 自动改格式 → 校验/修复 → 预览/导出。

## 架构

```
前端/CLI：导入 .docx、填写需求、查看前后预览、下载结果
        ↓
API 层：上传、任务管理、状态查询（FastAPI）
        ↓
Agent 编排层（LangGraph）：解析需求 → 分析文档 → 制定方案 → 执行 → 校验 → 修复 → 交付
        ↓
文档引擎层：python-docx（结构化读写）+ win32com（Word COM 渲染 PDF）
        ↓
校验层：结构校验、格式规则校验、前后 diff、PDF/PNG 渲染
```

## 目录结构

```
WordEditAgent/
├── app/            # FastAPI 入口、API 路由、配置、数据库、后台任务
├── agent/          # LangGraph 工作流、状态、节点、工具、提示词、LLM
├── engine/         # 文档模型、读取、写入、格式化、控制器、Word COM、备份
├── verify/         # 结构校验、规则校验、diff 报告、渲染
├── rules/          # 默认/论文/SOP/合同规则 + 中文单位换算
├── scripts/        # 生成示例 docx
├── tests/          # 单元 / 集成 / 端到端测试
├── uploads/        # 上传目录（运行时）
├── outputs/        # 输出目录（运行时）
├── templates/      # 模板目录
├── docker-compose.yml
├── requirements.txt
├── .env            # 本地环境变量（已 gitignore）
└── .env.example    # 环境变量样例
```

## 环境要求

- Python 3.12+
- Docker + Docker Compose（用于 PostgreSQL）
- Windows + Microsoft Word（用于 PDF/PNG 预览渲染，可选）

## 快速开始

### 1. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. 配置 .env

复制 `.env.example` 为 `.env`，并按需修改：

```ini
# DeepSeek API（OpenAI 兼容接口）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# PostgreSQL（与 docker-compose.yml 保持一致）
DATABASE_URL=postgresql+psycopg2://wordagent:wordagent@localhost:5432/wordedit

# 项目内目录（相对项目根目录）
UPLOAD_DIR=uploads
OUTPUT_DIR=outputs
TEMPLATE_DIR=templates
```

> 所有上传、输出、模板、数据库数据均保存在当前项目目录内，不占用其他路径。

### 3. 启动 PostgreSQL（Docker）

```powershell
docker compose up -d
```

镜像为 `postgres:17-alpine`，数据持久化在 `./data/postgres`。

### 4. 启动 API 服务

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动后访问：

- API 文档（Swagger）：http://127.0.0.1:8000/docs
- 服务信息：http://127.0.0.1:8000/

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

内置格式规则模板（`rules/*.json`），会根据需求关键词自动匹配：

- `default.json` — 通用文档
- `thesis.json` — 学位论文（含「论文/学位/摘要/参考文献」等关键词）
- `contract.json` — 合同（含「合同/甲方/乙方/协议」）
- `sop.json` — 标准作业程序（含「SOP/流程/操作规范」）

中文排版单位已内置换算：三号=16pt、小三=15pt、四号=14pt、小四=12pt、五号=10.5pt、小五=9pt；「2字符」缩进写入 `w:firstLineChars="200"`。

## 运行测试

```powershell
# 单元 / 集成测试（无需网络）
.venv\Scripts\python.exe -m pytest tests/test_rules.py tests/test_engine.py tests/test_verify.py tests/test_agent_plan.py -q

# 端到端测试（需要 DeepSeek 网络，可选 Word COM）
.venv\Scripts\python.exe -m pytest tests/test_e2e.py -q -s
```

## 生成示例文档

```powershell
.venv\Scripts\python.exe -m scripts.generate_sample
```

会在 `uploads/sample.docx` 生成一份中文示例文档，可用于上传测试。

## 说明

- PDF/PNG 预览依赖 Windows 上的 Microsoft Word（通过 Word COM），在独立子进程中执行以隔离崩溃；未安装 Word 时仍可正常格式化并下载 docx，仅预览不可用。
- 任务状态、进度、格式化规则、修改报告等元数据存储在 PostgreSQL；原始文件与结果文件分别保存在 `uploads/` 与 `outputs/`。
