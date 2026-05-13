# AILife NorthFrank 部署指南

## 前置要求

1. [NorthFrank](https://northflank.com) 账号
2. GitHub 账号（用于代码仓库）
3. Kimi API Key（[申请地址](https://platform.moonshot.cn)）
4. HuggingFace Token（[申请地址](https://huggingface.co/settings/tokens)）

## 部署步骤

### 1. 创建 PostgreSQL Addons

1. 在 NorthFrank 控制台中创建新项目
2. 进入项目 -> Addons -> Create new addon
3. 选择 **PostgreSQL**，版本 15
4. 设置名称：`ailife-postgres`
5. 启用 TLS
6. 创建

### 2. 连接 Addons 到 Secret Group

1. 进入 Secret Groups -> Create new secret group
2. 命名：`ailife-secrets`
3. 在 Linked Addons 中选择 `ailife-postgres`
4. 选择 `DATABASE_URL` secret
5. 创建

### 3. 部署后端服务

1. 将代码推送到 GitHub 仓库
2. 在 NorthFrank 中创建 Service -> Combined service
3. 配置：
   - 名称：`ailife-api`
   - 仓库：选择你的 GitHub 仓库
   - 分支：`main`
   - Build type：`Dockerfile`
4. 在 Environment 中添加环境变量：
   - `KIMI_API_KEY`：你的 Kimi API 密钥
   - `HF_TOKEN`：你的 HuggingFace Token
   - `WHISPER_MODEL`：large-v3（或根据 VPS 性能选择）
5. 在 Secret Groups 中链接 `ailife-secrets`
6. 创建服务

### 4. 首次部署后初始化数据库

服务启动后会自动执行 Alembic 迁移。可以通过以下方式验证：

```bash
# 查看服务日志，确认迁移成功
curl https://your-service.northflank.app/health
```

### 5. 配置前端

在前端的 `.env` 文件中设置 API URL：

```
EXPO_PUBLIC_API_URL=https://your-service.northflank.app
```

### 6. 构建前端 APK

```bash
cd ailife-app
eas build --platform android --profile preview
```

## 环境变量说明

| 变量 | 来源 | 说明 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL addon 自动注入 | 数据库连接字符串 (asyncpg 格式) |
| `PORT` | NorthFrank 自动分配 | 服务端口 |
| `KIMI_API_KEY` | 手动配置 | Kimi API 密钥 |
| `HF_TOKEN` | 手动配置 | HuggingFace Token |
| `WHISPER_MODEL` | 手动配置（默认 large-v3） | Whisper 模型 |
| `BGE_MODEL` | 手动配置（默认 BAAI/bge-small-zh-v1.5） | BGE 嵌入模型 |
| `CORS_ORIGINS` | 手动配置（默认 *） | CORS 白名单 |

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **数据库**: PostgreSQL 15 + pgvector 扩展
- **数据库迁移**: Alembic（应用启动时自动执行）
- **数据库驱动**: asyncpg（原生异步 PostgreSQL）
- **向量搜索**: pgvector <=> 操作符（原生 SQL）
- **语音识别**: faster-whisper
- **声纹识别**: SpeechBrain ECAPA-TDNN
- **说话人分离**: pyannote.audio
- **语义嵌入**: sentence-transformers (BGE)
- **AI API**: Moonshot Kimi (OpenAI 兼容接口)

## 数据库架构

应用启动时会自动执行 Alembic 迁移，创建以下表：

| 表名 | 说明 | 向量字段 |
|------|------|----------|
| `speakers` | 说话人档案 | `embedding vector(192)` - 声纹向量 |
| `recordings` | 录音会话 | - |
| `utterances` | 语音转写片段 | `embedding vector(768)` - 语义向量 |
| `events` | 提取事件 | - |
| `todos` | 待办事项 | - |
| `flash_memos` | 闪念笔记 | - |
| `bill_notes` | 账单记录 | - |
| `chat_sessions` | 聊天会话 | - |
| `chat_messages` | 聊天消息 | - |
| `weekly_reports` | 周报数据 | - |

### 向量搜索函数

迁移脚本会自动创建以下 PostgreSQL 函数：

- `match_speakers(query_embedding, threshold, count, user_id)` - 声纹匹配
- `match_utterances(query_embedding, threshold, count, user_id)` - 语义搜索
- `get_user_weekly_stats(user_id, week_start, week_end)` - 周报统计
- `get_speaker_timeline(speaker_id, limit)` - 说话人时间线
- `search_speaker_utterances(embedding, threshold, count, speaker_id)` - 按说话人搜索
- `get_recent_events(user_id, days)` - 近期事件

## 注意事项

- NorthFrank 免费额度有限，Whisper large-v3 模型需要较多内存，建议选择 nf-compute-100 或更高配置
- pyannote 模型首次下载需要 HuggingFace Token，下载后会被缓存
- 音频文件存储在容器内 `/app/data`，如需持久化请配置 Volume
- 数据库连接使用 asyncpg 驱动，通过 DATABASE_URL 环境变量连接
- pgvector 扩展在应用启动时自动启用
- Alembic 迁移在应用启动时自动执行到最新版本
