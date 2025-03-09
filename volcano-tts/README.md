# 火山引擎 TTS API 服务

这是一个基于火山引擎的文本转语音(TTS)服务，提供了与OpenAI TTS API兼容的接口。

## 功能特点

- 支持多种语言和声音
- 支持长文本自动分段处理
- 支持流式响应
- 使用LRU缓存提高性能
- 并行处理长文本
- 完整的日志系统
- 兼容OpenAI TTS API格式

## 项目结构

```
volcano-tts/
├── .env                # 环境变量配置文件
├── .env.example        # 环境变量示例文件
├── app.py              # 主应用程序
├── config.py           # 配置加载模块
├── logger.py           # 日志系统模块
├── Dockerfile          # Docker构建文件
└── requirements.txt    # 依赖包列表
```

## 配置说明

服务配置可以通过以下两种方式设置：

1. **环境变量**：直接在系统中设置环境变量
2. **.env文件**：在项目根目录创建 `.env` 文件

> 注意：如果同时存在环境变量和 `.env` 文件中的配置，环境变量将优先生效。

### 配置项

```
# API配置
API_KEY=your_api_key_here

# 服务配置
PORT=5050
HOST=0.0.0.0

# 文本处理配置
MAX_TEXT_LENGTH=500
MAX_WORKERS=5

# 日志配置
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/volcano-tts.log
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
LOG_ROTATION=1 MB
LOG_RETENTION=30 days
```

### 配置项说明

| 配置项 | 说明 | 默认值 | 可选值/范围 |
|--------|------|--------|------------|
| **API配置** |
| API_KEY | API密钥，用于验证请求的合法性 | sk-564565KDA231D | 任意字符串 |
| **服务配置** |
| PORT | 服务监听端口 | 5050 | 1-65535 |
| HOST | 服务监听地址 | 0.0.0.0 | 0.0.0.0, 127.0.0.1等 |
| **文本处理配置** |
| MAX_TEXT_LENGTH | 文本分段最大长度（字符数） | 500 | 100-2000 |
| MAX_WORKERS | 并行处理的最大工作线程数 | 5 | 1-20 |
| **日志配置** |
| LOG_LEVEL | 日志记录级别 | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| LOG_FILE_PATH | 主日志文件路径 | logs/volcano-tts.log | 任意有效路径 |
| LOG_FORMAT | 日志格式 | %(asctime)s - %(name)s - %(levelname)s - %(message)s | 符合Python logging格式的字符串 |
| LOG_ROTATION | 日志轮转大小 | 1 MB | 数字+单位(KB或MB) |
| LOG_RETENTION | 日志保留时间 | 30 days | 数字+单位(days) |

#### 参数详细说明

##### API_KEY
- **说明**：用于验证API请求的密钥
- **建议**：使用复杂的随机字符串增加安全性
- **示例**：`sk-abcdef123456`

##### PORT
- **说明**：服务监听的TCP端口
- **建议**：使用1024以上的端口，避免与系统服务冲突
- **示例**：`5050`, `8080`

##### HOST
- **说明**：服务监听的网络接口
- **选项**：
  - `0.0.0.0`: 监听所有网络接口，允许外部访问
  - `127.0.0.1`: 只监听本地接口，只允许本机访问
  - 特定IP: 只监听指定IP的接口

##### MAX_TEXT_LENGTH
- **说明**：文本分段的最大长度（字符数）
- **影响**：较大的值可能导致请求超时，较小的值会增加请求次数
- **建议**：根据实际需求调整，一般不超过500字符

##### MAX_WORKERS
- **说明**：并行处理文本段落的最大工作线程数
- **影响**：较大的值可以提高处理速度，但会增加系统负载
- **建议**：设置为CPU核心数的1-2倍

##### LOG_LEVEL
- **说明**：日志记录的级别，决定记录哪些级别的日志
- **选项**：
  - `DEBUG`: 记录所有日志，包括调试信息（最详细）
  - `INFO`: 记录信息、警告、错误和严重错误
  - `WARNING`: 只记录警告、错误和严重错误
  - `ERROR`: 只记录错误和严重错误
  - `CRITICAL`: 只记录严重错误（最简略）

##### LOG_FILE_PATH
- **说明**：主日志文件的保存路径
- **注意**：
  - 相对路径基于应用根目录
  - 错误日志和请求日志会自动保存在同一目录下
  - 目录必须存在或可创建

##### LOG_FORMAT
- **说明**：日志记录的格式
- **常用变量**：
  - `%(asctime)s`: 时间戳
  - `%(name)s`: 日志记录器名称
  - `%(levelname)s`: 日志级别
  - `%(message)s`: 日志消息
  - `%(filename)s`: 文件名
  - `%(lineno)d`: 行号

##### LOG_ROTATION
- **说明**：日志文件达到指定大小时进行轮转
- **格式**：数字+单位(KB或MB)
- **示例**：`1 MB`, `500 KB`

##### LOG_RETENTION
- **说明**：旧日志文件的保留时间
- **格式**：数字+单位(days)
- **示例**：`30 days`, `7 days`

## 部署方法

### 使用Docker

1. 构建Docker镜像：
   ```
   docker build -t volcano-tts .
   ```

2. 运行容器：
   ```
   docker run -d -p 5050:5050 -v ./logs:/app/logs -v ./.env:/app/.env --name volcano-tts volcano-tts
   ```

   或者使用环境变量：
   ```
   docker run -d -p 5050:5050 -v ./logs:/app/logs -e API_KEY=your_api_key -e LOG_LEVEL=DEBUG --name volcano-tts volcano-tts
   ```

### 使用Docker Compose

1. 启动服务：
   ```
   docker-compose up -d
   ```

   也可以在docker-compose.yml中设置环境变量：
   ```yaml
   services:
     volcano-tts:
       build: ./volcano-tts
       ports:
         - "5050:5050"
       volumes:
         - ./volcano-tts/logs:/app/logs
       environment:
         - API_KEY=your_api_key
         - LOG_LEVEL=INFO
         - TZ=Asia/Shanghai
       restart: unless-stopped
   ```

2. 查看日志：
   ```
   docker-compose logs -f
   ```

## API接口

### 文本转语音

```
POST /v1/audio/speech
```

请求体示例：
```json
{
  "model": "tts-1",
  "input": "你好，这是一段测试文本。",
  "voice": "zh_male_xiaoming",
  "response_format": "mp3",
  "stream": false
}
```

### 获取可用声音列表

```
GET /v1/voices
```

### 获取服务统计信息

```
GET /stats
```

## 日志系统

服务使用分层日志系统，包括：
- 应用日志：记录应用程序的一般信息
- 请求日志：记录HTTP请求和响应信息
- 错误日志：记录详细的错误信息和堆栈跟踪

日志文件保存在 `logs` 目录中，并通过Docker卷映射到宿主机。

### 日志文件说明

服务会生成以下日志文件：

| 日志文件 | 说明 | 默认路径 |
|---------|------|---------|
| volcano-tts.log | 主日志文件，记录所有级别的日志 | /app/logs/volcano-tts.log |
| volcano-tts-request.log | 请求日志文件，记录HTTP请求和响应 | /app/logs/volcano-tts-request.log |
| volcano-tts-error.log | 错误日志文件，记录错误和异常 | /app/logs/volcano-tts-error.log |

### 日志级别说明

- **DEBUG**: 记录所有日志，包括调试信息（最详细）
- **INFO**: 记录信息、警告、错误和严重错误
- **WARNING**: 只记录警告、错误和严重错误
- **ERROR**: 只记录错误和严重错误
- **CRITICAL**: 只记录严重错误（最简略）

### 日志查看方法

#### 查看容器内的日志文件

```bash
# 查看主日志文件
docker exec -it <container_name> cat /app/logs/volcano-tts.log

# 查看请求日志文件
docker exec -it <container_name> cat /app/logs/volcano-tts-request.log

# 查看错误日志文件
docker exec -it <container_name> cat /app/logs/volcano-tts-error.log

# 实时查看日志更新
docker exec -it <container_name> tail -f /app/logs/volcano-tts.log
```

#### 查看宿主机上的日志文件

```bash
# 查看主日志文件
cat volcano-tts/logs/volcano-tts.log

# 查看请求日志文件
cat volcano-tts/logs/volcano-tts-request.log

# 查看错误日志文件
cat volcano-tts/logs/volcano-tts-error.log

# 实时查看日志更新
tail -f volcano-tts/logs/volcano-tts.log
```

### 常见问题与故障排除

#### 问题：日志文件未创建

**症状**：
- 容器运行正常，但日志目录中没有日志文件
- 日志信息只输出到控制台，不写入文件

**可能原因**：
1. 日志目录权限问题
2. 日志配置不正确
3. 容器中缺少必要的文件（如 `logger.py` 或 `config.py`）

**解决方案**：
1. 检查容器中的文件结构：
   ```bash
   docker exec -it <container_name> ls -la /app
   ```

2. 确保日志目录存在且有正确的权限：
   ```bash
   docker exec -it <container_name> ls -la /app/logs
   ```

3. 重新构建镜像，确保所有文件都被包含：
   ```bash
   docker-compose build --no-cache
   docker-compose down
   docker-compose up -d
   ```

#### 问题：日志未映射到宿主机

**症状**：
- 容器内有日志文件，但宿主机上看不到

**可能原因**：
1. 卷映射配置不正确
2. 权限问题

**解决方案**：
1. 检查 `docker-compose.yml` 中的卷映射配置：
   ```yaml
   volumes:
     - ./volcano-tts/logs:/app/logs
   ```

2. 确保宿主机上的目录存在：
   ```bash
   mkdir -p volcano-tts/logs
   ```

3. 重启容器：
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### 日志系统最佳实践

1. **定期检查日志**：通过查看日志文件，可以及时发现和解决问题。

2. **监控日志大小**：虽然已配置日志轮转，但仍需定期检查日志大小，避免磁盘空间不足。

3. **调整日志级别**：
   - 开发环境：使用 `DEBUG` 级别获取更详细的信息
   - 生产环境：使用 `INFO` 或 `WARNING` 级别减少日志量

4. **定期清理旧日志**：虽然配置了日志保留时间，但仍建议定期手动清理不再需要的旧日志文件。

5. **备份重要日志**：对于重要的日志信息，建议定期备份到其他存储位置。
