# 多轮对话 AI 导购机评平台

把现有 Python 评测引擎 + demo HTML 形态，升级为可视化评测平台的 MVP 看板版。

## 技术栈
- 前端：Next.js 14 (App Router) + Tailwind + shadcn/ui + Recharts + Fraunces/Manrope
- 后端：FastAPI + SQLAlchemy 2.0 + Pydantic v2 + alembic
- 任务：Celery + Redis
- 存储：Postgres 16
- 容器：docker-compose 单机部署

## 快速开始
```bash
# 1. 准备环境变量（首次）
cp backend/.env.example backend/.env
# 在 backend/.env 中填入 ARK_API_KEY 等 judge 模型密钥

# 2. 启动所有服务
make dev          # 等同 docker compose up --build

# 3. 首次需要建表 + 灌种子数据
make migrate
make seed

# 4. 打开浏览器
open http://localhost:3000
```

## 路线图
- W1（当前）：脚手架 + 单 run 跑通
- W2：看板完整 + Badcase 钻取
- W3：4 类对比 + 人工标注
- W4：体验打磨 + 部署

详细方案见 `~/.claude/plans/ai-chat-bot-vibe-demo-eval-platform-dem-tender-newell.md`。

## 目录结构
```
platform/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── api/                 # 路由
│   │   ├── models/              # SQLAlchemy ORM
│   │   ├── schemas/             # Pydantic
│   │   ├── services/eval_engine # 复用现有评测引擎
│   │   ├── tasks/               # Celery
│   │   └── core/                # config/db/sse
│   ├── alembic/                 # 迁移
│   └── seeds/                   # 种子数据脚本
├── frontend/
│   ├── app/                     # Next.js App Router
│   ├── components/              # UI 组件
│   └── styles/                  # 全局样式 + tokens
├── docker-compose.yml
└── Makefile
```
