# 火山引擎 TTS 服务部署文档

## 1. 项目说明
这是一个基于火山引擎的文本转语音(TTS)服务，可以与 Open WebUI 集成使用。支持多种语言和声音，包括中文方言、英语、日语等。服务采用了智能分段处理长文本，并支持流式音频响应，提高了用户体验。

## 2. 目录结构
```
V:\DockerData\tts-service\
├── docker-compose.yml      # Docker 编排配置文件
└── volcano-tts\           # TTS 服务目录
    ├── Dockerfile         # Docker 构建文件
    ├── requirements.txt   # Python 依赖文件
    └── app.py            # 主服务程序
```

## 3. 支持的语音
### 中文语音
- zh_male_xiaoming: 影视配音
- zh_male_rap: 嘻哈歌手
- zh_female_sichuan: 四川女声
- zh_male_zhubo: 男主播
- zh_female_zhubo: 女主播
- zh_female_qingxin: 清新女声
- tts.other.BV021_streaming: 东北男声
- tts.other.BV026_streaming: 粤语男声

### 其他语言
- 英语：美式/英式/澳洲男女声
- 日语：男声/女声
- 韩语：男声/女声
- 法语、西班牙语、俄语等多种语言

## 4. 部署步骤

### 4.1 安装要求
- Docker Desktop
- 至少 2GB 可用内存
- 网络连接

### 4.2 部署命令
```bash
# 1. 进入项目目录
cd V:\DockerData\tts-service

# 2. 构建并启动服务
docker-compose up -d --build

# 3. 检查服务状态
docker-compose ps
docker-compose logs -f
```

### 4.3 Open WebUI 集成配置

#### 方法一：通过 Web 界面配置
1. 访问 Open WebUI (http://localhost:3000)
2. 登录管理员账户
3. 点击右上角的 "Admin Panel"（管理面板）
4. 在左侧菜单选择 "Settings"（设置）
5. 找到 "Audio" 部分
6. 配置以下参数：
   - Text-to-Speech Engine: 选择 "OpenAI"
   - API Base URL: 输入 `http://localhost:5050/v1`
   - API Key: 输入 `sk-36565655`（或保持为空）
   - TTS Voice: 选择 `zh_male_xiaoming`（或其他声音）
7. 点击 "Save" 保存设置

#### 方法二：直接修改配置文件
1. 找到 Open WebUI 的数据目录：`V:/DockerData/open-webui-data`
2. 编辑配置文件（如果不存在则创建）：
```bash
# 配置文件路径示例
V:/DockerData/open-webui-data/config.json
```

3. 添加或修改以下配置：
```json
{
  "tts": {
    "provider": "openai",
    "openai": {
      "api_base": "http://localhost:5050/v1",
      "api_key": "sk-36565655",
      "voice": "zh_male_xiaoming"
    }
  }
}
```

### 4.4 测试配置
1. 在 Open WebUI 聊天界面中：
   - 点击语音输入按钮进行测试
   - 或发送消息后点击语音播放按钮

2. 可用的中文声音选项：
   ```
   zh_male_xiaoming    - 影视配音（推荐）
   zh_female_sichuan   - 四川女声
   zh_male_zhubo      - 男主播
   zh_female_zhubo    - 女主播
   zh_female_qingxin  - 清新女声
   ```

3. 常见问题：
   - 如果听不到声音，检查浏览器是否允许播放
   - 如果报错，检查 API Base URL 是否正确
   - 确保 TTS 服务容器正常运行

## 5. API 接口

### 5.1 语音合成
```http
POST http://localhost:5050/v1/audio/speech
Content-Type: application/json
Authorization: Bearer sk-36565655

{
    "input": "要转换的文本",
    "voice": "zh_male_xiaoming",
    "model": "tts-1",
    "response_format": "mp3",
    "stream": false
}
```

#### 参数说明
- `input`: 要转换的文本（支持长文本，会自动分段处理）
- `voice`: 声音ID
- `model`: 模型名称（兼容OpenAI格式）
- `response_format`: 输出格式（目前仅支持mp3）
- `stream`: 是否使用流式响应（true/false）

### 5.2 流式语音合成
```http
POST http://localhost:5050/v1/audio/speech
Content-Type: application/json
Authorization: Bearer sk-36565655

{
    "input": "要转换的文本",
    "voice": "zh_male_xiaoming",
    "model": "tts-1",
    "response_format": "mp3",
    "stream": true
}
```

流式响应适用于长文本，可以在生成过程中逐步播放音频，而不必等待整个文本处理完成。

### 5.3 获取可用语音列表
```http
GET http://localhost:5050/v1/voices
Authorization: Bearer sk-36565655
```

### 5.4 API 文档
访问 http://localhost:5050/docs 查看完整的 API 文档

## 6. 维护命令
```bash
# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新服务
docker-compose pull
docker-compose up -d --build
```

## 7. 故障排除
1. 如果服务无法访问：
   - 检查端口 5050 是否被占用
   - 确认容器运行状态
   - 查看容器日志

2. 如果语音合成失败：
   - 确认网络连接正常
   - 检查请求参数是否正确
   - 查看服务日志

3. 如果 Open WebUI 无法使用 TTS：
   - 确认 API Base URL 配置正确
   - 检查选择的语音是否存在
   - 确认服务正常运行

## 8. 高级功能

### 8.1 长文本分片处理

#### 核心原理
长文本分片处理的核心是将超长文本智能地分割成较小的片段，每个片段单独处理后再合并结果。这样可以解决火山引擎API对单次请求文本长度的限制问题。

#### 技术实现
服务使用了智能分段算法，通过以下步骤处理长文本：

1. **文本分段函数**：
   ```python
   def split_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> List[str]:
   ```

   这个函数负责将长文本分割成多个短段落，最大长度由 `MAX_TEXT_LENGTH` 控制（默认500字符）。

2. **分段策略**：
   - 优先在句末标点（句号、问号、感叹号等）处分段
   - 其次在句中标点（逗号、分号、冒号等）处分段
   - 再次在空格、换行等位置分段
   - 如果都找不到合适的分割点，则在最大长度处强制分段

3. **正则表达式匹配**：
   ```python
   patterns = [
       r'[.!?。！？]',  # 句末标点
       r'[,;:，；：]',  # 句中标点
       r'[ \n\t]'      # 空格和换行
   ]
   ```

   按优先级依次尝试不同的分割模式，确保分段在语义上尽量完整。

4. **从后向前查找**：
   在最大长度范围内从后向前查找最后一个匹配的标点，确保分段不会在句子中间断开。

#### 使用场景
- 长篇文章朗读
- 小说章节转语音
- 长对话内容转语音
- 任何超过500字符的文本

### 8.2 流式音频响应

#### 核心原理
流式响应允许服务器在生成音频的同时就开始向客户端发送数据，而不必等待整个文本处理完成。这对长文本特别有用，可以大大提高用户体验。

#### 技术实现
服务使用了以下技术实现流式响应：

1. **生成器函数**：
   ```python
   def generate_audio_stream(text_segments: List[str], speaker: str, lang: str) -> Generator[bytes, None, None]:
   ```

   这个函数是一个生成器，它会逐段处理文本并生成音频数据，每生成一段就立即返回（yield）给调用者。

2. **错误容忍**：
   即使某一段处理失败，也会继续处理后续段落，而不会中断整个流程。这确保了即使部分文本处理失败，用户仍然能听到大部分内容。

3. **FastAPI的StreamingResponse**：
   ```python
   return StreamingResponse(
       generate_audio_stream(text_segments, speaker, lang),
       media_type="audio/mpeg",
       headers={"Content-Disposition": "attachment; filename=speech.mp3"}
   )
   ```

   使用FastAPI的StreamingResponse来实现HTTP流式响应，客户端可以在接收到部分数据后就开始处理。

#### 客户端处理
要使用流式响应，客户端需要能够处理流式数据。常见的处理方式包括：

1. **浏览器中**：
   ```javascript
   fetch('/v1/audio/speech', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       input: longText,
       voice: 'zh_male_xiaoming',
       stream: true
     })
   })
   .then(response => response.blob())
   .then(blob => {
     const url = URL.createObjectURL(blob);
     const audio = new Audio(url);
     audio.play();
   });
   ```

2. **高级处理**：对于更复杂的需求，可以使用Web Audio API逐段处理和播放音频数据。

#### 使用场景
- 实时语音生成
- 长文本朗读
- 需要快速响应的应用
- 提高用户体验的场景

### 8.3 两者的结合使用

当处理长文本时，系统会：

1. 首先调用`split_text`将文本分割成多个段落
2. 如果请求中`stream=true`，则使用`generate_audio_stream`和`StreamingResponse`进行流式处理
3. 如果请求中`stream=false`，则依次处理每个段落并将结果合并后一次性返回

这种组合方式既解决了长文本处理的问题，又提供了更好的用户体验：
- 对于短文本，可以直接一次性处理
- 对于长文本，可以选择流式响应，让用户更快听到结果
- 即使某一段处理失败，也不会影响整体功能

### 8.4 音频响应速度优化

为了进一步提高音频响应速度，可以采用以下优化策略：

#### 1. 缓存机制

实现多级缓存策略，大幅提高重复请求的响应速度：

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_tts_audio(text, speaker, lang):
    # 处理TTS请求并返回音频数据
    ...
```

- **内存缓存**：使用LRU（最近最少使用）缓存存储最近请求的音频结果
- **磁盘缓存**：对于常用短语，可以预先生成并存储在磁盘上
- **分段缓存**：缓存常见的句子片段，即使完整文本不同，也可以重用部分缓存

#### 2. 并行处理

对于长文本，使用并行处理加速音频生成：

```python
import asyncio
import concurrent.futures

async def process_segments_parallel(segments, speaker, lang):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(
                executor,
                get_segment_audio,
                segment,
                speaker,
                lang
            )
            for segment in segments
        ]
        return await asyncio.gather(*futures)
```

- **多线程处理**：同时处理多个文本段落
- **异步IO**：使用异步IO减少等待时间
- **批量请求**：将多个短文本合并为一个批量请求

#### 3. 连接优化

优化与火山引擎API的连接：

```python
# 创建持久会话
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=10,
    pool_maxsize=10,
    max_retries=3
)
session.mount('https://', adapter)

# 使用会话发送请求
response = session.post(url, headers=headers, json=payload)
```

- **连接池**：使用HTTP连接池复用连接
- **持久连接**：保持与API服务器的长连接
- **超时设置**：设置合理的超时时间，避免长时间等待

#### 4. 预热策略

实现服务预热，减少冷启动延迟：

```python
def warm_up_service():
    """预热服务，提前加载模型和建立连接"""
    common_phrases = ["你好", "谢谢", "再见", "欢迎使用"]
    for phrase in common_phrases:
        try:
            get_tts_audio(phrase, "zh_male_xiaoming", "zh")
        except Exception:
            pass
```

- **启动预热**：服务启动时预热常用语音
- **定时预热**：定期刷新缓存和连接
- **智能预热**：根据使用模式预测并预热可能需要的内容

#### 5. 压缩和格式优化

优化音频格式和压缩设置：

```python
def optimize_audio(audio_data, quality=0.9):
    """优化音频数据大小和质量"""
    # 实现音频压缩或转码
    return compressed_audio
```

- **自适应比特率**：根据网络条件调整音频质量
- **音频格式选择**：为不同场景选择合适的音频格式
- **增量传输**：只传输音频数据的变化部分

#### 6. 客户端优化

优化客户端处理逻辑：

```javascript
// 预缓冲策略
const audioContext = new (window.AudioContext || window.webkitAudioContext)();
let audioBuffer = [];
let isPlaying = false;

function handleAudioChunk(chunk) {
  audioBuffer.push(chunk);
  if (audioBuffer.length > 3 && !isPlaying) {
    startPlayback();
  }
}
```

- **预缓冲**：在开始播放前缓冲一定量的音频
- **渐进式播放**：接收到足够数据就开始播放
- **后台预加载**：预测用户可能需要的下一段音频

#### 7. 硬件加速

利用硬件加速提高处理速度：

- **GPU加速**：使用GPU加速音频处理
- **专用服务器**：使用高性能服务器托管服务
- **边缘计算**：将服务部署在离用户更近的位置

#### 8. 监控和自适应优化

实现性能监控和自适应优化：

```python
def adaptive_optimization(metrics):
    """根据性能指标自动调整优化参数"""
    if metrics['response_time'] > 1.0:
        # 增加并行度
        MAX_WORKERS = min(MAX_WORKERS + 1, 10)
    elif metrics['memory_usage'] > 80:
        # 减少缓存大小
        adjust_cache_size(0.8)
```

- **性能指标收集**：收集响应时间、CPU使用率等指标
- **自适应参数**：根据负载自动调整参数
- **A/B测试**：测试不同优化策略的效果

## 9. 性能优化
服务包含以下性能优化措施：

1. **智能分段处理**：自动将长文本分割成适合TTS处理的短段落
2. **流式响应**：支持流式音频输出，提高长文本处理的用户体验
3. **错误处理**：更加健壮的错误处理机制，提高服务稳定性
4. **日志优化**：减少不必要的日志输出，提高服务性能
5. **缓存机制**：使用LRU缓存存储常用请求结果，减少重复处理
6. **并行处理**：并行处理多个文本段落，加速长文本处理
7. **连接优化**：优化与火山引擎API的连接，减少网络延迟

## 10. 注意事项
- 服务依赖网络连接
- 建议定期备份配置文件
- 可以根据需要修改端口映射
- 支持的语音可能会随火山引擎更新而变化
- 默认每段文本最大长度为500字符，可在代码中调整
- 流式响应需要客户端支持处理流式数据
- 对于非常长的文本（如整本书），建议分章节处理
- 并行处理会增加内存和CPU使用，需根据服务器配置调整并行度
- 缓存大小应根据可用内存和使用模式调整

## 11. 更新日志
- v1.2.0: 性能优化版本
  - 添加LRU缓存机制
  - 实现并行处理长文本
  - 优化网络连接
  - 添加服务预热功能
- v1.1.0: 功能增强版本
  - 添加长文本智能分段处理
  - 添加流式音频响应
  - 优化错误处理
  - 减少不必要的日志输出
- v1.0.0: 初始版本
  - 支持多语言 TTS
  - 集成 Open WebUI
  - 提供 REST API
