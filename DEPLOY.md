# VoiceLife (AILife) Northflank 部署指南

## 前置要求

1. [Northflank](https://northflank.com) 账号
2. GitHub 账号（已创建 `jjbb013/VoiceLife` 仓库）
3. Kimi API Key（[申请地址](https://platform.moonshot.cn)）
4. HuggingFace Token（[申请地址](https://huggingface.co/settings/tokens)）

---

## 部署方式一：使用 Northflank Template（推荐）

本项目包含 `northfrank.json` Template 文件，可一键部署所有基础设施。

### 步骤 1：创建 Template

1. 登录 [Northflank 控制台](https://app.northflank.com)
2. 进入你的 **Team** 页面
3. 点击 **Templates** → **Create new template**
4. 输入模板名称：`voice-life`
5. 选择 **Code editor**（代码编辑器模式）
6. 将 `northfrank.json` 文件的全部内容粘贴到编辑器中
7. 点击 **Create template**

### 步骤 2：配置 Secret Overrides

Template 中定义了两个需要安全存储的参数，必须在运行前配置：

1. 在 Template 页面点击 **Settings**
2. 找到 **Argument overrides** 部分
3. 添加以下密钥：

| 参数 | 值 | 说明 |
|------|-----|------|
| `KIMI_API_KEY` | `sk-xxxxxxxx` | 你的 Kimi API 密钥 |
| `HF_TOKEN` | `hf_xxxxxxxx` | 你的 HuggingFace Token |

4. 点击 **Save changes**

### 步骤 3：运行 Template

1. 在 Template 页面点击 **Run template**
2. 可以修改参数（如项目名称、区域等），或使用默认值
3. 点击 **Run**

Template 将按顺序执行：
1. 创建 Project（`voice-life`）
2. 创建 PostgreSQL addon（`ailife-postgres`，自动安装 pgvector）
3. 等待数据库就绪
4. 创建 Combined Service（`ailife-api`），从 GitHub 构建
5. 等待服务就绪
6. 创建 Secret Group，将数据库连接信息注入服务
7. 重启服务以应用新配置

### 步骤 4：验证部署

等待所有步骤完成后：

```bash
# 检查健康端点
curl https://<你的服务域名>/health

# 预期返回
{"status":"ok","database":"connected"}
```

---

## 部署方式二：手动创建（备用）

如果不使用 Template，也可以手动创建各个资源。

### 1. 创建项目

1. Northflank 控制台 → **Projects** → **Create new project**
2. 名称：`voice-life`
3. 区域：`europe-west`
4. 创建

### 2. 创建 PostgreSQL Addon

1. 进入项目 → **Addons** → **Create new addon**
2. 类型：**PostgreSQL**
3. 版本：`15`
4. 名称：`ailife-postgres`
5. 计费：`nf-compute-50`
6. 存储：`10240 MB`
7. 启用 **TLS**
8. 创建

### 3. 创建 Secret Group

1. 项目 → **Secrets** → **Create Secret Group**
2. 名称：`ailife-secrets`
3. 添加环境变量：
   - `KIMI_API_KEY` = 你的 Kimi API 密钥
   - `HF_TOKEN` = 你的 HuggingFace Token
   - `WHISPER_MODEL` = `large-v3`
   - `KIMI_MODEL` = `moonshot-v1-128k`
   - `CORS_ORIGINS` = `*`
4. 在 **Linked Addons** 中关联 `ailife-postgres`
5. 创建

### 4. 创建 Combined Service

1. 项目 → **Services** → **Create new service** → **Combined service**
2. 名称：`ailife-api`
3. 构建：
   - **Repository**: `jjbb013/VoiceLife`
   - **Branch**: `main`
   - **Build type**: `Dockerfile`
   - **Dockerfile path**: `/Dockerfile`
4. 端口：
   - 内部端口：`8000`
   - 协议：`HTTP`
   - 公开：是
5. 环境变量：从 Secret Group `ailife-secrets` 导入
6. 健康检查：
   - 路径：`/health`
   - 端口：`8000`
   - 初始延迟：`15s`
   - 周期：`30s`
7. 资源：
   - CPU：`1-2`
   - 内存：`2-4 GB`
   - 临时存储：`2 GB`
8. 创建

### 5. 配置前端 API URL

服务部署成功后，获取分配的域名，在前端配置：

```env
EXPO_PUBLIC_API_URL=https://<你的服务域名>
```

---

## 环境变量说明

| 变量 | 来源 | 说明 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL addon 自动注入 | 数据库连接字符串 |
| `PORT` | Northflank 自动分配 | 服务端口（默认 8000） |
| `KIMI_API_KEY` | **手动配置**（Secret） | Kimi API 密钥 |
| `HF_TOKEN` | **手动配置**（Secret） | HuggingFace Token |
| `WHISPER_MODEL` | Template 参数 | Whisper 模型选择 |
| `KIMI_MODEL` | Template 参数 | Kimi 模型选择 |
| `CORS_ORIGINS` | Template 参数 | CORS 白名单 |

---

## Northflank Template 架构

```
northfrank.json (Template)
│
├─ Project: voice-life
│
├─ Workflow (sequential)
│   │
│   ├─ Addon: ailife-postgres (PostgreSQL 15 + pgvector)
│   │
│   ├─ Workflow (sequential)
│   │   ├─ Condition: 等待数据库就绪
│   │   ├─ CombinedService: ailife-api
│   │   │   ├─ Build: Dockerfile (GitHub jjbb013/VoiceLife)
│   │   │   ├─ Port: 8000 HTTP (公开)
│   │   │   ├─ HealthCheck: /health
│   │   │   └─ RuntimeEnv: DATABASE_URL, KIMI_API_KEY, HF_TOKEN, ...
│   │   │
│   │   ├─ Condition: 等待服务就绪
│   │   │
│   │   ├─ SecretGroup: ailife-secrets
│   │   │   ├─ addonDependencies: ailife-postgres → DATABASE_URL
│   │   │   └─ restrictions: 仅限 ailife-api 服务
│   │   │
│   │   └─ Action: 重启 ailife-api 服务
```

**Addon → Service 关联原理：**
1. PostgreSQL addon 创建后输出连接信息（host, port, database, username, password, connectionString）
2. SecretGroup 通过 `addonDependencies` 链接 addon，将连接密钥映射为环境变量
3. SecretGroup 的 `restrictions` 限制只有 `ailife-api` 服务可以访问这些密钥
4. 服务重启后，环境变量生效，应用通过 `DATABASE_URL` 连接到数据库

---

## 常见问题

### pgvector 扩展未启用？

Alembic 迁移会在应用启动时自动执行：
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

如果失败，可以在 Northflank 控制台进入 addon → **Query** 标签，手动执行：
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### 模型下载失败？

确保 `HF_TOKEN` 已正确配置，且该 Token 有权访问：
- `pyannote/speaker-diarization-3.1`
- `speechbrain/ecapa-tdnn`

### 内存不足？

Whisper large-v3 模型需要较多内存，建议：
- 在 Template 参数中将 `WHISPER_MODEL` 改为 `medium`（2GB 内存可运行）
- 或在 Northflank 控制台升级服务资源计划

---

## 资源参考

- [Northflank Template 文档](https://northflank.com/docs/v1/application/infrastructure-as-code/write-a-template)
- [Northflank Template Nodes](https://northflank.com/docs/v1/application/infrastructure-as-code/template-nodes)
- [Northflank API 文档](https://northflank.com/docs/v1/api)
- [VoiceLife GitHub 仓库](https://github.com/jjbb013/VoiceLife)
