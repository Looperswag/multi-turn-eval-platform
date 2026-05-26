# 多轮对话 AI 导购机评平台

把现有 Python 评测引擎 + demo HTML 形态，升级为可视化评测平台。覆盖 W1/W1.5/B/C 四阶段（详见路线图）。

## 技术栈
- 前端：Next.js 14 (App Router) + Tailwind + shadcn/ui + Recharts + Fraunces/Manrope
- 后端：FastAPI + SQLAlchemy 2.0 + Pydantic v2 + alembic
- 任务：Celery + Redis
- 存储：Postgres 16
- 容器：docker-compose 单机部署

## 快速开始（本地 dev）
```bash
# 1. 准备环境变量
cp backend/.env.example backend/.env
# 至少填 ARK_API_KEY 才能跑 judge 调用

# 2. 启动所有服务
make dev              # 等同 docker compose up --build

# 3. 首次：建表 + 灌种子
make migrate          # 跑全部 alembic 0001 → 0009
make seed             # 灌入 100 条 mock query + 6 维 v4 prompt

# 4. 浏览器
open http://localhost:3000
```

## 单机生产部署

### 基础步骤
```bash
# 1. clone 仓库
git clone <repo>
cd platform

# 2. 准备生产 .env
cp backend/.env.example backend/.env
# 必改：
#   ARK_API_KEY=<your ark key>
#   API_KEY=<生成一个随机 32 字节字符串>
#   REQUIRE_API_KEY=true   # 启用全局鉴权（外网部署必开）
#   DATABASE_URL=...       # 若用外部 Postgres
# 可选：
#   ARK_DEFAULT_MODEL / ARK_BASE_URL（如 endpoint 不同）
#   CORS_ORIGINS=["https://yourdomain.com"]

# 3. 构建 + 启动
docker compose build --no-cache    # 关键：必须 build 让 fpdf2 等 pip 依赖进镜像
docker compose up -d

# 4. 初始化 DB
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seeds.seed   # 可选：灌种子或跳过

# 5. 烟测
curl -H "X-API-Key: <your-API_KEY>" http://localhost:8000/api/health
# REQUIRE_API_KEY=true 时业务端点必须带 X-API-Key
curl -H "X-API-Key: <your-API_KEY>" http://localhost:8000/api/datasets
```

### 全局鉴权 (X-API-Key)
| 配置 | 行为 |
|---|---|
| `REQUIRE_API_KEY=false` (默认) | 跳过校验，适合内网/dev |
| `REQUIRE_API_KEY=true` | 所有业务端点强制带 `X-API-Key: $API_KEY`；`/api/health` 永远豁免 |

**注意**：开启后浏览器侧 `<a href>` 直跳的 Excel/MD/PDF 导出会失败（navigation 不带 header）。临时方案：保持 disabled，或在反向代理层（nginx）做 IP 白名单替代 X-API-Key。后续 D 阶段会改为 fetch + Blob 下载。

### 反向代理 / Ingress 建议（D 阶段安全基线）

平台已开启全局 rate-limit（300 req/min/IP）+ 上传 size 限制 50 MB。如使用 nginx 反代：

```nginx
client_max_body_size 50m;        # 与后端 _MAX_UPLOAD_BYTES 对齐
proxy_buffering off;             # SSE 流式响应不缓冲
proxy_read_timeout 3600s;        # SSE 长连接
```

API key 比较已用 `secrets.compare_digest` 防 timing 攻击；xlsx 解析已通过 `defusedxml.defuse_stdlib()` 防 XXE / billion-laughs。

### 备份与灾备（M2.4）

| 指标 | 目标 | 说明 |
|---|---|---|
| **RPO**（数据丢失窗口） | ≤ 24h | 每日 03:00 `pg_dump` 全备 |
| **RTO**（恢复时间） | ≤ 30 min | 单文件 `gunzip \| psql` 流式恢复 |
| 保留期 | 30 天本地 | 超过自动清理；S3 可选异地副本 |
| 兜底 | 自动 pre-restore 快照 | restore 前先 dump 当前 DB 防误操作 |

**每日备份脚本** — `backend/scripts/backup.sh`：

```bash
# 本地备份
./backend/scripts/backup.sh

# 同时推 S3（需 aws cli）
S3_BUCKET=my-bucket ./backend/scripts/backup.sh

# Cron（每日凌晨 3 点）
0 3 * * * cd /opt/platform && ./backend/scripts/backup.sh >> /var/log/platform-backup.log 2>&1
```

**恢复演练（restore drill）** — 建议每季度跑一次：

```bash
# 1. 在 staging 环境跑：
./backend/scripts/restore.sh ./backups/eval_platform-20260526-030000.sql.gz
# 输入 'yes' 确认；脚本会先 dump 当前 DB 作为 pre-restore 快照

# 2. 自检输出（alembic_version / eval_run / eval_case_result 三表行数）
#    任一为 0 应视为恢复异常

# 3. 烟测：跑 5-session run + 看板验证
```

**未在范围内**：WAL 增量备份（POSTGRES + wal-g/barman 部署较重，待 S3 路径成熟后引入）。

### 启动检查清单
- [ ] `.env` 不在 git（已 .gitignore）
- [ ] API_KEY 使用 32 字节随机字符串（避免 dev-key-change-me）
- [ ] Postgres / Redis 数据卷持久化（docker volume）
- [ ] alembic 迁移跑到 head（`alembic current` 应是 `0009`）
- [ ] Worker 容器健康（`docker compose ps` 显示 Up）
- [ ] 测试 ARK 连通性：UI 进 `/judge-config/models/1` 点 "测试连通性"

## 路线图（项目历史）
- **W1** ✅：脚手架（5 容器 + 8 张表 + 5 个 SSR 页 + ARK 联通）
- **W1.5/A** ✅：SSR 修复 / Bot/Judge/Prompt 三页 / PromptRenderer / Dataset 上传向导 / 对比 / 标注 / 可视化导出（9 子模块 × Worker+Reviewer）
- **B** ✅：Badcase 钻取 + 维度详情 6-tab
- **C** ✅：MD/PDF 导出 + 回归集管理 + SSE 优化 + 全局鉴权 + 部署文档（本文件）

## 数据流（4 类对比示意）
```
Dataset (mock_multi_turn) ←→ Bot Version (baseline/v2)
                              ↓
                          Bot Rewrite
                              ↓
EvalRun (dataset × bot × prompt × judge) → Celery Worker
                              ↓
                  EvalCaseResult (6 维 + 完整 raw judge JSON)
                              ↓
                  ┌───────────┼───────────┬─────────────────┐
                  ↓           ↓           ↓                 ↓
              Comparison   Annotation   Badcase Tag    Regression Set
            (prompt/bot/    (人工 vs   (打标 + 加入   (子集回归测试)
            judge/人工)     机评)      回归集)
```

## 目录结构
```
platform/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + 全局 X-API-Key
│   │   ├── api/                 # 9 个 router
│   │   ├── models/              # SQLAlchemy ORM (10 张表)
│   │   ├── schemas/             # Pydantic v2
│   │   ├── services/
│   │   │   ├── eval_engine/     # PromptRenderer + evaluators
│   │   │   ├── scoring.py
│   │   │   ├── exporter.py      # xlsx/md/pdf 三格式导出
│   │   │   ├── comparison.py    # diff_runs + kappa + movements
│   │   │   └── agreement.py     # 4-level (含 NA) Cohen's κ
│   │   ├── tasks/               # Celery (execute_eval_run + retry_failed_cases)
│   │   └── core/                # config / db / sse
│   ├── alembic/                 # 0001 → 0009 migration
│   └── seeds/                   # 种子数据脚本
├── frontend/
│   ├── app/                     # Next.js App Router
│   │   ├── datasets/            # 列表 + 上传 4 步向导
│   │   ├── bot-versions/        # CRUD + rewrite stats
│   │   ├── judge-config/        # prompts (含 clone/activate) + models (含测试连通性)
│   │   ├── eval-runs/           # 任务队列 + 看板 + Badcase 钻取 + 维度详情 + 实时 SSE
│   │   ├── comparisons/         # 4 类对比 (prompt/bot/judge/人工)
│   │   ├── annotations/         # 标注工作台 + 一致率看板
│   │   └── regression-sets/     # 回归集管理
│   ├── components/              # 共享 UI（雷达 / 直方图 / live-progress 等）
│   └── styles/                  # 全局样式 + 设计 token（米色+森林绿）
├── docker-compose.yml
└── Makefile
```

## 故障排查

### `docker compose build` 网络超时
- 重试或切换 docker registry 镜像源（`/etc/docker/daemon.json` 加 `registry-mirrors`）
- 应急：`docker compose exec api pip install -r requirements.txt`（容器内临时装，重启会丢，仅供本地恢复）

### `alembic upgrade head` 报错 GIN-on-JSON
- 0008 已用表达式索引 `(judge_prompt_version_ids::jsonb) jsonb_path_ops` 绕过；若你扩展查询要命中索引，记得 SQL 里也用 `::jsonb` 转换

### PDF 导出中文显示问号
- fpdf2 默认 latin-1，中文 fallback 为 `?`。完整中文请用 MD / XLSX 格式
- D 阶段会切换到 weasyprint + CJK 字体

### Celery 任务卡 running
- 检查 worker 日志：`docker compose logs worker --tail 100`
- 若 prompt_template 有 jinja2 语法错误：A.3 已加 fail-fast → 自动把 run 标 failed
- 重试失败 case：UI 上点 `重试失败` 按钮（C.3 已实现）
