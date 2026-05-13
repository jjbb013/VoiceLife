# VoiceLife - AI 随身语音助手

基于声纹识别的随身 AI 语音记忆与智能分析助手。

> **NorthFrank 部署适配版** | 原项目: AILife

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | Expo SDK 50 + React Native | 跨平台移动应用 |
| **后端** | FastAPI + asyncpg | 高性能异步 API |
| **数据库** | PostgreSQL 15 + pgvector | 向量搜索支持 |
| **AI 模型** | Whisper + pyannote + Kimi | 语音识别、说话人分离、LLM 分析 |
| **部署** | NorthFrank (Docker) | 云原生部署 |

## 项目结构

```
VoiceLife/
├── app/                          # 后端 FastAPI 应用
│   ├── main.py                   # 应用入口
│   ├── config.py                 # 配置管理
│   ├── db.py                     # PostgreSQL 连接池 (asyncpg)
│   ├── models.py                 # SQLAlchemy 模型
│   ├── db_migration.py           # Alembic 自动迁移
│   ├── routers/                  # API 路由 (9个模块)
│   │   ├── upload.py             # 音频上传
│   │   ├── speakers.py           # 人物管理
│   │   ├── utterances.py         # 语音片段
│   │   ├── search.py             # 语义检索
│   │   ├── chat.py               # AI 聊天
│   │   ├── flash_memos.py        # 闪念胶囊
│   │   ├── meetings.py           # 会议纪要
│   │   ├── bills.py              # 账单速记
│   │   └── reports.py            # 周报日报
│   └── services/                 # 业务服务层
│       ├── audio_processor.py    # 音频处理流水线
│       ├── whisper_service.py    # Whisper 语音识别
│       ├── diarization_service.py # 说话人分离
│       ├── embedding_service.py  # 声纹嵌入提取
│       ├── llm_service.py        # Kimi LLM 调用
│       ├── vector_service.py     # BGE 语义向量
│       ├── calendar_parser.py    # 日历事件提取
│       ├── bill_extractor.py     # 账单 NER 提取
│       └── report_generator.py   # 报告生成
├── alembic/                      # 数据库迁移
│   └── versions/
│       └── 001_initial_schema.py # 初始表结构
├── frontend/                     # Expo 前端应用
│   ├── src/
│   │   ├── app/                  # 页面路由
│   │   ├── components/           # UI 组件
│   │   ├── hooks/                # 自定义 Hooks
│   │   ├── services/             # API 服务
│   │   └── types/                # TypeScript 类型
│   ├── app.json                  # Expo 配置
│   └── package.json
├── db/                           # 数据库脚本（备用）
├── Dockerfile                    # Docker 构建文件
├── docker-compose.yml            # Docker Compose 配置
├── alembic.ini                   # Alembic 配置
├── northfrank.json               # NorthFrank 部署模板
├── requirements.txt              # Python 依赖
└── DEPLOY.md                     # 部署指南
```

## 快速开始

### 本地开发

```bash
# 1. 克隆仓库
git clone https://github.com/jjbb013/VoiceLife.git
cd VoiceLife

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 DATABASE_URL, KIMI_API_KEY, HF_TOKEN

# 3. 安装依赖
pip install -r requirements.txt

# 4. 执行数据库迁移
alembic upgrade head

# 5. 启动服务
uvicorn app.main:app --reload
```

### NorthFrank 部署

详见 [DEPLOY.md](DEPLOY.md)。

## API 文档

启动服务后访问 `/docs` 查看 Swagger UI 文档。

## 核心功能

- **后台录音 + VAD**: 手机常驻监听，有人声即录
- **主人声纹注册**: 首次使用录制主人声纹
- **说话人分离**: 区分"我"、已知人物、未知人物
- **云端转写 + 摘要**: Whisper 转写 + Kimi 生成对话摘要
- **人物档案**: 未知声纹可人工命名，建立人物卡片
- **闪念胶囊**: 快速语音备忘
- **AI 聊天**: 查询历史、人