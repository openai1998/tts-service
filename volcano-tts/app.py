from fastapi import FastAPI, HTTPException, Response, Header, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import requests
import base64
import json
import re
import io
import asyncio
import concurrent.futures
import time
from typing import List, Generator, Dict, Any
from functools import lru_cache
import warnings
import urllib3
import uuid

# 导入配置和日志模块
import config
from logger import get_logger, setup_logging, request_logger, error_logger, logger
from text_filter import filter_text, text_filter

# 禁用不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 获取日志记录器
logger = get_logger()
request_logger = get_logger('request')
error_logger = get_logger('error')

app = FastAPI(title="Volcano TTS API")

# 创建持久会话
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=10,
    pool_maxsize=10,
    max_retries=3
)
session.mount('https://', adapter)

class TTSRequest(BaseModel):
    model: str = "tts-1"  # OpenAI 格式
    input: str           # 要转换的文本
    voice: str          # 声音选择
    response_format: str = "mp3"  # 输出格式
    stream: bool = False  # 是否使用流式响应

# 验证API密钥的依赖函数
async def verify_api_key(authorization: str = Header(None)):
    """验证 API 密钥"""
    if not authorization:
        request_logger.warning("No API key provided")
        raise HTTPException(
            status_code=401,
            detail="API key is required"
        )

    provided_key = authorization.replace("Bearer ", "")
    if provided_key != config.API_KEY:
        request_logger.warning(f"Invalid API key provided: {provided_key}")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return True

# 文本分段函数
def split_text(text: str, max_length: int = config.MAX_TEXT_LENGTH) -> List[str]:
    """
    将长文本分割成适合TTS处理的短段落

    参数:
        text: 要分割的文本
        max_length: 每段最大长度

    返回:
        分割后的文本段落列表
    """
    # 如果文本长度小于最大长度，直接返回
    if len(text) <= max_length:
        return [text]

    # 分段结果
    segments = []

    # 按标点符号分割
    # 优先级：句号/问号/感叹号 > 逗号/分号/冒号 > 其他
    patterns = [
        r'[.!?。！？]', # 句末标点
        r'[,;:，；：]', # 句中标点
        r'[ \n\t]'     # 空格和换行
    ]

    # 当前处理的文本
    remaining_text = text

    while len(remaining_text) > max_length:
        # 在最大长度范围内寻找合适的分割点
        segment = remaining_text[:max_length]
        split_pos = -1

        # 按优先级尝试不同的分割模式
        for pattern in patterns:
            # 从后向前查找最后一个匹配的标点
            matches = list(re.finditer(pattern, segment))
            if matches:
                # 找到最后一个匹配的位置
                split_pos = matches[-1].end()
                break

        # 如果没有找到合适的分割点，强制在最大长度处分割
        if split_pos == -1:
            split_pos = max_length

        # 添加分段并更新剩余文本
        segments.append(remaining_text[:split_pos].strip())
        remaining_text = remaining_text[split_pos:].strip()

    # 添加最后一段
    if remaining_text:
        segments.append(remaining_text)

    return segments

# 使用LRU缓存来缓存TTS结果，提高性能
@lru_cache(maxsize=200)  # 增加缓存容量
def get_segment_audio_cached(text: str, speaker: str, lang: str) -> bytes:
    """获取单个文本段落的音频数据（带缓存）"""
    config.PERFORMANCE_METRICS["cache_hits"] += 1
    return get_segment_audio(text, speaker, lang)

# 获取单个文本段落的音频数据
def get_segment_audio(text: str, speaker: str, lang: str) -> bytes:
    """获取单个文本段落的音频数据"""
    config.PERFORMANCE_METRICS["cache_misses"] += 1
    start_time = time.time()

    # 构建火山引擎请求头
    headers = {
        "authority": "translate.volcengine.com",
        "origin": "chrome-extension://klgfhbdadaspgppeadghjjemk",
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "none",
        "cookie": "hasUserBehavior=1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
    }

    # 使用已知可行的请求格式
    payload = {
        "text": text,
        "speaker": speaker,
        "language": lang
    }

    try:
        logger.info(f"处理文本段落: text_length={len(text)}, speaker={speaker}, lang={lang}")
        logger.debug(f"请求负载: {json.dumps(payload, ensure_ascii=False)}")

        # 使用持久会话发送请求
        response = session.post(
            "https://translate.volcengine.com/crx/tts/v1/",
            headers=headers,
            json=payload,
            verify=False,
            timeout=10
        )

        if response.status_code != 200:
            error_msg = f"HTTP请求错误:\n状态码: {response.status_code}\n响应内容: {response.text}\n请求内容: {json.dumps(payload, ensure_ascii=False)}"
            error_logger.error(error_msg)
            raise Exception(error_msg)

        # 解析响应
        result = response.json()
        logger.debug(f"响应状态: {response.status_code}, 内容类型: {response.headers.get('content-type')}")

        # 检查是否有音频数据
        if not result.get("audio") or not result["audio"].get("data"):
            error_msg = f"未获取到音频数据，完整响应: {json.dumps(result, ensure_ascii=False)}"
            error_logger.error(error_msg)
            raise Exception(error_msg)

        # 获取Base64编码的音频数据并解码
        audio_data = base64.b64decode(result["audio"]["data"])

        # 更新性能指标
        process_time = time.time() - start_time
        config.PERFORMANCE_METRICS["avg_response_time"] = (
            (config.PERFORMANCE_METRICS["avg_response_time"] * config.PERFORMANCE_METRICS["total_requests"] + process_time) /
            (config.PERFORMANCE_METRICS["total_requests"] + 1) if config.PERFORMANCE_METRICS["total_requests"] > 0 else process_time
        )

        logger.info(f"成功生成音频段落, 大小: {len(audio_data)} 字节, 耗时: {process_time:.2f}秒")
        return audio_data

    except Exception as e:
        error_logger.error(f"生成音频时出错: {str(e)}", exc_info=True)
        raise

# 并行处理多个文本段落
async def process_segments_parallel(segments: List[str], speaker: str, lang: str) -> List[bytes]:
    """并行处理多个文本段落"""
    # 根据CPU核心数和段落数量动态调整工作线程数
    optimal_workers = min(len(segments), config.MAX_WORKERS)

    with concurrent.futures.ThreadPoolExecutor(max_workers=optimal_workers) as executor:
        loop = asyncio.get_event_loop()
        # 创建任务列表
        tasks = []
        for segment in segments:
            # 检查缓存
            try:
                # 尝试从缓存获取
                if get_segment_audio_cached.cache_info().currsize > 0:
                    audio_data = get_segment_audio_cached(segment, speaker, lang)
                    tasks.append(loop.create_task(asyncio.sleep(0, result=audio_data)))
                    continue
            except Exception:
                pass

            # 如果缓存未命中，创建新的处理任务
            task = loop.run_in_executor(
                executor,
                get_segment_audio_cached,
                segment,
                speaker,
                lang
            )
            tasks.append(task)

        # 等待所有任务完成
        return await asyncio.gather(*tasks)

# 流式生成音频数据
def generate_audio_stream(text_segments: List[str], speaker: str, lang: str) -> Generator[bytes, None, None]:
    """流式生成音频数据"""
    for segment in text_segments:
        try:
            # 尝试从缓存获取
            audio_data = get_segment_audio_cached(segment, speaker, lang)
            # 分块发送音频数据
            chunk_size = 32768  # 32KB chunks
            for i in range(0, len(audio_data), chunk_size):
                yield audio_data[i:i + chunk_size]
        except Exception as e:
            error_logger.error(f"生成段落音频时出错: {str(e)}", exc_info=True)
            # 继续处理下一段，而不是中断整个流

# 预热服务
def warm_up_service():
    """预热服务，提前加载模型和建立连接"""
    common_phrases = ["你好", "谢谢", "欢迎使用"]
    for phrase in common_phrases:
        try:
            get_segment_audio_cached(phrase, "zh_male_xiaoming", "zh")
            logger.info(f"服务预热完成，使用短语: {phrase}")
        except Exception as e:
            error_logger.error(f"服务预热过程中出错: {str(e)}", exc_info=True)

@app.on_event("startup")
async def startup_event():
    """服务启动时执行的操作"""
    # 预热服务
    warm_up_service()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录请求并收集性能指标"""
    # 记录请求开始时间
    start_time = time.time()

    # 更新请求计数
    config.PERFORMANCE_METRICS["total_requests"] += 1

    # 记录请求信息
    request_id = str(time.time())
    client_host = request.client.host if request.client else "unknown"
    request_logger.info(f"请求开始 [{request_id}] - {request.method} {request.url.path} - 客户端: {client_host}")

    # 处理请求
    try:
        response = await call_next(request)

        # 计算响应时间
        process_time = time.time() - start_time

        # 记录响应信息
        request_logger.info(
            f"请求完成 [{request_id}] - {request.method} {request.url.path} - "
            f"状态码: {response.status_code} - 耗时: {process_time:.4f}秒"
        )

        # 更新统计信息
        if response.status_code < 400:
            config.PERFORMANCE_METRICS["successful_requests"] += 1
        else:
            config.PERFORMANCE_METRICS["failed_requests"] += 1

        return response
    except Exception as e:
        # 记录异常
        process_time = time.time() - start_time
        error_logger.error(
            f"请求异常 [{request_id}] - {request.method} {request.url.path} - "
            f"错误: {str(e)} - 耗时: {process_time:.4f}秒",
            exc_info=True
        )
        config.PERFORMANCE_METRICS["failed_requests"] += 1
        raise

@app.post("/v1/audio/speech")
async def create_speech(request: TTSRequest, _: bool = Depends(verify_api_key)):
    try:
        # 记录请求开始时间
        start_time = time.time()

        # 记录请求
        logger.info(f"收到TTS请求: voice={request.voice}, text_length={len(request.input)}, stream={request.stream}")

        # 应用文本过滤（如果启用）
        original_text = request.input
        filtered_text, filtered_items = text_filter.filter_text(original_text)

        # 如果有内容被过滤，记录日志
        if filtered_items:
            logger.info(f"已过滤 {len(filtered_items)} 处内容，原文本长度: {len(original_text)}，过滤后长度: {len(filtered_text)}")
            for item in filtered_items:
                logger.debug(f"过滤规则 '{item['rule_name']}' 匹配内容: {item['content'][:50]}...")

        # 使用过滤后的文本
        request.input = filtered_text

        # 确定语言和说话人
        lang = "zh"  # 默认中文
        speaker = request.voice

        # 如果传入的是语音名称而不是ID，尝试查找对应的ID
        voice_id_found = False
        for lang_code, voice_dict in config.VOICE_CONFIG.items():
            # 通过名称查找ID
            for voice_id, voice_name in voice_dict.items():
                if voice_name == speaker:
                    speaker = voice_id
                    lang = config.LANGUAGE_MAP.get(lang_code, "zh")
                    voice_id_found = True
                    break
            # 通过ID查找
            if not voice_id_found and speaker in voice_dict:
                lang = config.LANGUAGE_MAP.get(lang_code, "zh")
                voice_id_found = True
                break
            if voice_id_found:
                break

        # 如果没找到指定的声音，使用默认话者
        if not voice_id_found:
            logger.warning(f"未找到声音 {speaker}，使用默认声音")
            lang = "zh"
            speaker = config.DEFAULT_SPEAKERS["zh_cn"]

        # 分割长文本
        text_segments = split_text(request.input)
        logger.info(f"文本已分割为 {len(text_segments)} 个段落")

        # 更新性能指标
        if request.stream:
            config.PERFORMANCE_METRICS["stream_requests"] += 1
        if len(text_segments) > 1:
            config.PERFORMANCE_METRICS["parallel_requests"] += 1

        # 流式响应
        if request.stream:
            return StreamingResponse(
                generate_audio_stream(text_segments, speaker, lang),
                media_type="audio/mpeg",
                headers={"Content-Disposition": "attachment; filename=speech.mp3"}
            )

        # 非流式响应 - 并行处理所有段落
        if len(text_segments) > 1:
            # 使用并行处理加速
            audio_segments = await process_segments_parallel(text_segments, speaker, lang)
            all_audio_data = bytearray()
            for audio_data in audio_segments:
                if audio_data:
                    all_audio_data.extend(audio_data)
        else:
            # 单段处理
            all_audio_data = get_segment_audio_cached(text_segments[0], speaker, lang)

        # 更新性能指标
        process_time = time.time() - start_time
        config.PERFORMANCE_METRICS["total_audio_size"] += len(all_audio_data)
        config.PERFORMANCE_METRICS["avg_segment_size"] = (
            config.PERFORMANCE_METRICS["total_audio_size"] / config.PERFORMANCE_METRICS["successful_requests"]
            if config.PERFORMANCE_METRICS["successful_requests"] > 0 else 0
        )

        logger.info(f"成功生成完整音频, 大小: {len(all_audio_data)} 字节, 耗时: {process_time:.2f}秒")

        # 返回合并后的MP3音频数据
        return Response(
            content=bytes(all_audio_data),
            media_type="audio/mp3",
            headers={
                "X-Process-Time": str(process_time),
                "X-Segments-Count": str(len(text_segments)),
                "X-Cache-Info": str(get_segment_audio_cached.cache_info())
            }
        )

    except Exception as e:
        error_logger.exception("create_speech 方法出错:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/voices")
@app.get("/v1/audio/voices")  # 添加别名路径
async def list_voices():  # 移除API密钥验证
    """列出所有可用的声音，格式完全兼容OpenAI"""
    voices = []
    for lang_code, voice_dict in config.VOICE_CONFIG.items():
        for voice_id, voice_name in voice_dict.items():
            # 构建完全兼容OpenAI格式的语音对象
            voice = {
                "id": voice_id,
                "name": voice_name,
                "model": "tts-1",  # 添加固定的模型标识
                "voice_id": voice_id,  # 保持兼容性
                "preview_url": None,
                "language": lang_code,
                "language_code": config.LANGUAGE_MAP.get(lang_code, "zh"),
                "description": voice_name,  # 简化描述，只显示中文名称
                "is_default": voice_id == config.DEFAULT_SPEAKERS.get(lang_code)
            }
            voices.append(voice)

    # 返回完全兼容OpenAI格式的响应
    return {
        "object": "list",
        "data": voices
    }

@app.get("/stats")
async def get_stats(_: bool = Depends(verify_api_key)):
    """获取服务统计信息"""
    cache_info = get_segment_audio_cached.cache_info()
    stats = {
        "performance": config.PERFORMANCE_METRICS,
        "cache": {
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "maxsize": cache_info.maxsize,
            "currsize": cache_info.currsize,
            "hit_rate": cache_info.hits / (cache_info.hits + cache_info.misses) if (cache_info.hits + cache_info.misses) > 0 else 0
        },
        "config": {
            "max_workers": config.MAX_WORKERS,
            "max_text_length": config.MAX_TEXT_LENGTH
        }
    }
    return stats

@app.get("/")
async def root():
    """API 文档"""
    return {
        "message": "火山引擎 TTS API 服务",
        "version": "1.2.0",
        "docs_url": "/docs",
        "voices_url": "/v1/voices",
        "stats_url": "/stats",
        "supported_languages": list(config.LANGUAGE_MAP.keys()),
        "auth_required": True,
        "default_api_key": config.API_KEY,
        "features": {
            "long_text": f"支持长文本（自动分段，每段最大{config.MAX_TEXT_LENGTH}字符）",
            "streaming": "支持流式音频响应",
            "caching": "使用LRU缓存提高重复请求性能",
            "parallel": f"并行处理长文本（最大{config.MAX_WORKERS}线程）"
        }
    }

if __name__ == "__main__":
    logger.info(f"启动 Volcano TTS 服务，监听 {config.HOST}:{config.PORT}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
