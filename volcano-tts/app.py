from fastapi import FastAPI, HTTPException, Response, Header, Depends, Request, File, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
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
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.staticfiles import StaticFiles
import traceback
import datetime

# 导入配置和日志模块
import config
from logger import get_logger
from text_filter import filter_text, text_filter
from debug_utils import save_request_text, save_audio_data, get_debug_info

# 设置日志
logger = get_logger()
request_logger = get_logger('request')
error_logger = get_logger('error')

# 禁用不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="Volcano TTS API")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

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

    # 预处理文本，确保没有特殊字符
    text = text.strip()
    if not text:
        logger.warning("文本为空，返回空音频")
        return b''

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

    # 构建请求负载
    payload = {
        "text": text,
        "speaker": speaker,
        "language": lang
    }

    logger.debug(f"请求负载: {json.dumps(payload)}")

    try:
        # 发送请求
        response = session.post(
            "https://translate.volcengine.com/web/tts/v1/",
            headers=headers,
            json=payload,
            timeout=10,
            verify=False
        )

        # 检查响应状态
        logger.debug(f"响应状态: {response.status_code}, 内容类型: {response.headers.get('content-type', 'unknown')}")
        response.raise_for_status()

        # 解析响应
        result = response.json()
        if "audio" in result:
            try:
                # 检查audio是否为字符串（Base64编码）
                if isinstance(result["audio"], str):
                    # 解码Base64音频数据
                    audio_data = base64.b64decode(result["audio"])
                elif isinstance(result["audio"], dict) and "data" in result["audio"]:
                    # 兼容旧版API格式
                    audio_data = base64.b64decode(result["audio"]["data"])
                else:
                    logger.error(f"未知的音频数据格式: {type(result['audio'])}")
                    return b''

                # 确保音频数据是有效的MP3格式
                if not audio_data.startswith(b'\xFF\xFB') and not audio_data.startswith(b'ID3'):
                    logger.warning("返回的音频数据不是有效的MP3格式，尝试修复")
                    # 添加MP3头
                    audio_data = b'\xFF\xFB\x90\x44\x00' + audio_data

                # 确保音频数据以MP3结尾标记结束
                if not audio_data.endswith(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'):
                    logger.warning("添加MP3结尾标记")
                    audio_data += b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

                # 验证音频数据大小
                if len(audio_data) < 100:
                    logger.warning(f"生成的音频数据过小 ({len(audio_data)} 字节)，可能无效")
                    # 生成一个简单的静音MP3
                    audio_data = b'\xFF\xFB\x90\x44\x00' + b'\x00' * 1000 + b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

                logger.info(f"成功生成音频段落, 大小: {len(audio_data)} 字节, 耗时: {time.time() - start_time:.2f}秒")
                return audio_data
            except Exception as e:
                logger.error(f"处理音频数据失败: {str(e)}")
                return b''
        else:
            logger.error(f"响应中没有音频数据: {result}")
            return b''
    except Exception as e:
        logger.error(f"获取音频数据失败: {str(e)}")
        return b''

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
            # 跳过空段落
            if not segment or segment.isspace():
                logger.warning("跳过空段落")
                tasks.append(loop.create_task(asyncio.sleep(0, result=b'')))
                continue

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
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤掉异常和空结果
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"段落 {i+1} 处理失败: {str(result)}")
                valid_results.append(b'')
            elif not result:
                logger.warning(f"段落 {i+1} 返回空音频")
                valid_results.append(b'')
            else:
                valid_results.append(result)

        return valid_results

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
async def create_speech(request: TTSRequest, raw_request: Request, _: bool = Depends(verify_api_key)):
    try:
        # 生成请求ID
        request_id = str(uuid.uuid4())[:8]

        # 记录请求开始时间
        start_time = time.time()

        # 记录请求
        logger.info(f"收到TTS请求 [{request_id}]: voice={request.voice}, text_length={len(request.input)}, stream={request.stream}")

        # 获取并保存完全原始的请求体
        try:
            raw_body = await raw_request.body()
            raw_body_text = raw_body.decode('utf-8')
            logger.info(f"原始请求体 [{request_id}]: {raw_body_text[:200]}...")

            # 保存原始请求体
            if config.DEBUG_MODE and config.DEBUG_SAVE_TEXT:
                raw_data = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "request_id": request_id,
                    "raw_request_body": raw_body_text,
                    "parsed_request": request.dict()
                }

                # 确保目录存在
                text_dir = os.path.join(config.DEBUG_DIR, 'text')
                os.makedirs(text_dir, exist_ok=True)

                # 生成文件名
                timestamp = int(time.time())
                filename = f"{timestamp}_{request_id}_raw.json"
                filepath = os.path.join(text_dir, filename)

                # 保存到文件
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(raw_data, f, ensure_ascii=False, indent=2)

                logger.info(f"已保存原始请求体到 {filepath}")
        except Exception as e:
            logger.error(f"保存原始请求体失败: {str(e)}")

        # 保存原始请求文本（调试模式）
        save_request_text(request_id, request.dict())

        # 应用文本过滤（如果启用）
        original_text = request.input
        filtered_text, filtered_items = text_filter.filter_text(original_text)

        # 如果有内容被过滤，记录日志
        if filtered_items:
            logger.info(f"已过滤 {len(filtered_items)} 处内容，原文本长度: {len(original_text)}，过滤后长度: {len(filtered_text)}")
            for item in filtered_items:
                logger.debug(f"过滤规则 '{item['rule_name']}' 匹配内容: {item['content'][:50]}...")

        # 额外的文本清理步骤，处理特殊字符和格式
        # 1. 移除所有HTML标签
        cleaned_text = re.sub(r'<[^>]*>', '', filtered_text)

        # 2. 规范化换行符
        cleaned_text = re.sub(r'\r\n', '\n', cleaned_text)
        cleaned_text = re.sub(r'\r', '\n', cleaned_text)

        # 3. 移除连续的换行符
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)

        # 4. 移除特殊Unicode字符
        cleaned_text = re.sub(r'[\u2000-\u206F\u2E00-\u2E7F\\\'!"#$%&()*+,\-.\/:;<=>?@\[\]^_`{|}~]', ' ', cleaned_text)

        # 5. 移除多余的空格
        cleaned_text = re.sub(r' {2,}', ' ', cleaned_text)
        cleaned_text = cleaned_text.strip()

        # 记录清理结果
        if cleaned_text != filtered_text:
            logger.info(f"文本清理: 过滤后长度={len(filtered_text)}, 清理后长度={len(cleaned_text)}")

        # 保存过滤后的文本（调试模式）
        if filtered_text != original_text or cleaned_text != filtered_text:
            save_request_text(request_id, {'original': original_text}, cleaned_text)

        # 检查清理后的文本是否为空或只包含空白字符
        if not cleaned_text or cleaned_text.isspace():
            logger.warning("清理后文本为空，返回空响应")
            # 返回空音频响应 - 完全模拟OpenAI的TTS API响应格式
            return Response(
                content=b'',  # 空字节数组
                media_type="audio/mpeg",
                headers={
                    "Content-Type": "audio/mpeg",
                    "Content-Disposition": "attachment; filename=empty.mp3",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Allow-Methods": "*",
                    "X-Filter-Result": "empty_after_filtering"
                }
            )

        # 使用清理后的文本
        request.input = cleaned_text

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
                headers={
                    "Content-Type": "audio/mpeg",
                    "Content-Disposition": "attachment; filename=speech.mp3",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Allow-Methods": "*"
                }
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

        # 检查是否成功生成音频
        if not all_audio_data:
            logger.warning("未能生成有效音频，返回静音MP3")
            # 生成一个简单的静音MP3
            all_audio_data = b'\xFF\xFB\x90\x44\x00' + b'\x00' * 1000 + b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

        # 更新性能指标
        process_time = time.time() - start_time
        config.PERFORMANCE_METRICS["total_audio_size"] += len(all_audio_data)
        config.PERFORMANCE_METRICS["avg_segment_size"] = (
            config.PERFORMANCE_METRICS["total_audio_size"] / config.PERFORMANCE_METRICS["successful_requests"]
            if config.PERFORMANCE_METRICS["successful_requests"] > 0 else 0
        )

        logger.info(f"成功生成完整音频 [{request_id}], 大小: {len(all_audio_data)} 字节, 耗时: {process_time:.2f}秒")

        # 保存生成的音频数据（调试模式）
        save_audio_data(request_id, bytes(all_audio_data))

        # 返回合并后的MP3音频数据 - 完全模拟OpenAI的TTS API响应格式
        return Response(
            content=bytes(all_audio_data),
            media_type="audio/mpeg",
            headers={
                "Content-Type": "audio/mpeg",
                "Content-Length": str(len(all_audio_data)),
                "Content-Disposition": "attachment; filename=speech.mp3",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*",
                "Cache-Control": "no-cache"
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

# 添加调试信息接口
@app.get("/debug", response_class=HTMLResponse)
async def debug_page():
    """调试页面"""
    if not config.DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Debug mode is disabled")

    debug_info = get_debug_info()

    # 获取文本文件列表
    text_dir = os.path.join(config.DEBUG_DIR, 'text')
    text_files = []
    if os.path.exists(text_dir):
        text_files = [f for f in os.listdir(text_dir) if f.endswith('.json')]
        text_files.sort(key=lambda f: os.path.getmtime(os.path.join(text_dir, f)), reverse=True)

    # 获取音频文件列表
    audio_dir = os.path.join(config.DEBUG_DIR, 'audio')
    audio_files = []
    if os.path.exists(audio_dir):
        audio_files = [f for f in os.listdir(audio_dir) if f.endswith('.mp3')]
        audio_files.sort(key=lambda f: os.path.getmtime(os.path.join(audio_dir, f)), reverse=True)

    # 生成HTML页面
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Volcano TTS 调试页面</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            h1, h2, h3 {{ color: #333; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .card {{ background: #f9f9f9; border-radius: 5px; padding: 15px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .file-list {{ max-height: 400px; overflow-y: auto; }}
            .file-item {{ padding: 8px; border-bottom: 1px solid #eee; }}
            .file-item:hover {{ background: #f0f0f0; }}
            .file-link {{ text-decoration: none; color: #0066cc; }}
            .file-link:hover {{ text-decoration: underline; }}
            .audio-player {{ width: 100%; margin-top: 5px; }}
            .tabs {{ display: flex; margin-bottom: 15px; }}
            .tab {{ padding: 10px 15px; cursor: pointer; border: 1px solid #ddd; border-bottom: none; border-radius: 5px 5px 0 0; margin-right: 5px; }}
            .tab.active {{ background: #f9f9f9; }}
            .tab-content {{ display: none; }}
            .tab-content.active {{ display: block; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Volcano TTS 调试页面</h1>

            <div class="card">
                <h2>调试信息</h2>
                <p>调试模式: {debug_info.get('debug_enabled', False)}</p>
                <p>调试目录: {debug_info.get('debug_dir', '')}</p>
                <p>保存文本: {debug_info.get('save_text', False)}</p>
                <p>保存音频: {debug_info.get('save_audio', False)}</p>
                <p>最大文件数: {debug_info.get('max_files', 0)}</p>
                <p>文本文件数: {debug_info.get('text_files_count', 0)}</p>
                <p>音频文件数: {debug_info.get('audio_files_count', 0)}</p>
            </div>

            <div class="tabs">
                <div class="tab active" onclick="openTab(event, 'text-files')">文本文件</div>
                <div class="tab" onclick="openTab(event, 'audio-files')">音频文件</div>
            </div>

            <div id="text-files" class="tab-content card active">
                <h2>文本文件</h2>
                <div class="file-list">
                    {''.join([f'<div class="file-item"><a class="file-link" href="/debug/text/{file}" target="_blank">{file}</a></div>' for file in text_files])}
                    {f'<div class="file-item">没有文本文件</div>' if not text_files else ''}
                </div>
            </div>

            <div id="audio-files" class="tab-content card">
                <h2>音频文件</h2>
                <div class="file-list">
                    {''.join([f'<div class="file-item"><a class="file-link" href="/debug/audio/{file}" target="_blank">{file}</a><audio class="audio-player" controls src="/debug/audio/{file}"></audio></div>' for file in audio_files])}
                    {f'<div class="file-item">没有音频文件</div>' if not audio_files else ''}
                </div>
            </div>
        </div>

        <script>
            function openTab(evt, tabName) {{
                var i, tabContent, tabLinks;

                // 隐藏所有标签内容
                tabContent = document.getElementsByClassName("tab-content");
                for (i = 0; i < tabContent.length; i++) {{
                    tabContent[i].className = tabContent[i].className.replace(" active", "");
                }}

                // 移除所有标签的活动状态
                tabLinks = document.getElementsByClassName("tab");
                for (i = 0; i < tabLinks.length; i++) {{
                    tabLinks[i].className = tabLinks[i].className.replace(" active", "");
                }}

                // 显示当前标签内容并添加活动状态
                document.getElementById(tabName).className += " active";
                evt.currentTarget.className += " active";
            }}
        </script>
    </body>
    </html>
    """

    return html

@app.get("/debug/info")
async def debug_info():
    """获取调试信息"""
    return get_debug_info()

@app.get("/debug/text/{filename}")
async def get_debug_text(filename: str):
    """获取调试文本文件内容"""
    if not config.DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Debug mode is disabled")

    filepath = os.path.join(config.DEBUG_DIR, 'text', filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = json.load(f)
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

@app.get("/debug/audio/{filename}")
async def get_debug_audio(filename: str):
    """获取调试音频文件内容"""
    if not config.DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Debug mode is disabled")

    filepath = os.path.join(config.DEBUG_DIR, 'audio', filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(filepath, media_type="audio/mpeg")

@app.get("/debug/test")
async def debug_test():
    """测试调试功能是否正常工作"""
    try:
        # 检查调试模式是否启用
        debug_enabled = config.DEBUG_MODE

        # 获取调试目录信息
        debug_dir = config.DEBUG_DIR
        text_dir = os.path.join(debug_dir, 'text')
        audio_dir = os.path.join(debug_dir, 'audio')

        # 确保目录存在
        os.makedirs(text_dir, exist_ok=True)
        os.makedirs(audio_dir, exist_ok=True)

        # 检查目录权限
        text_dir_exists = os.path.exists(text_dir)
        audio_dir_exists = os.path.exists(audio_dir)
        text_dir_writable = os.access(text_dir, os.W_OK) if text_dir_exists else False
        audio_dir_writable = os.access(audio_dir, os.W_OK) if audio_dir_exists else False

        # 尝试写入测试文件
        test_id = f"test_{int(time.time())}"
        test_text_file = os.path.join(text_dir, f"{test_id}.json")
        test_audio_file = os.path.join(audio_dir, f"{test_id}.mp3")

        text_write_success = False
        audio_write_success = False

        if text_dir_writable:
            try:
                with open(test_text_file, 'w', encoding='utf-8') as f:
                    json.dump({"test": "success", "time": time.time()}, f)
                text_write_success = os.path.exists(test_text_file)
                if text_write_success:
                    os.remove(test_text_file)
            except Exception as e:
                logger.error(f"测试文本写入失败: {str(e)}")

        if audio_dir_writable:
            try:
                with open(test_audio_file, 'wb') as f:
                    f.write(b'\xFF\xFB\x90\x44\x00')  # 简单的MP3头
                audio_write_success = os.path.exists(test_audio_file)
                if audio_write_success:
                    os.remove(test_audio_file)
            except Exception as e:
                logger.error(f"测试音频写入失败: {str(e)}")

        # 检查环境变量
        env_vars = {
            "DEBUG_MODE": os.environ.get("DEBUG_MODE", "未设置"),
            "DEBUG_DIR": os.environ.get("DEBUG_DIR", "未设置"),
            "DEBUG_SAVE_TEXT": os.environ.get("DEBUG_SAVE_TEXT", "未设置"),
            "DEBUG_SAVE_AUDIO": os.environ.get("DEBUG_SAVE_AUDIO", "未设置"),
            "DEBUG_MAX_FILES": os.environ.get("DEBUG_MAX_FILES", "未设置")
        }

        # 返回测试结果
        return {
            "status": "success",
            "debug_enabled": debug_enabled,
            "config": {
                "DEBUG_MODE": config.DEBUG_MODE,
                "DEBUG_DIR": config.DEBUG_DIR,
                "DEBUG_SAVE_TEXT": config.DEBUG_SAVE_TEXT,
                "DEBUG_SAVE_AUDIO": config.DEBUG_SAVE_AUDIO,
                "DEBUG_MAX_FILES": config.DEBUG_MAX_FILES
            },
            "environment": env_vars,
            "directories": {
                "text_dir": {
                    "path": text_dir,
                    "exists": text_dir_exists,
                    "writable": text_dir_writable,
                    "write_test": text_write_success
                },
                "audio_dir": {
                    "path": audio_dir,
                    "exists": audio_dir_exists,
                    "writable": audio_dir_writable,
                    "write_test": audio_write_success
                }
            },
            "current_working_dir": os.getcwd(),
            "user": os.getenv("USER", "unknown")
        }
    except Exception as e:
        logger.error(f"调试测试失败: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/debug/write-test")
async def debug_write_test():
    """直接测试文件写入功能"""
    if not config.DEBUG_MODE:
        return {"status": "error", "message": "Debug mode is disabled"}

    results = {}

    # 测试文本文件写入
    text_dir = os.path.join(config.DEBUG_DIR, 'text')
    os.makedirs(text_dir, exist_ok=True)
    test_file = os.path.join(text_dir, "write_test.json")

    try:
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write('{"test": "success"}')
        results["text_write"] = "success"
        os.remove(test_file)
    except Exception as e:
        results["text_write"] = f"failed: {str(e)}"

    # 测试音频文件写入
    audio_dir = os.path.join(config.DEBUG_DIR, 'audio')
    os.makedirs(audio_dir, exist_ok=True)
    test_file = os.path.join(audio_dir, "write_test.mp3")

    try:
        with open(test_file, 'wb') as f:
            f.write(b'\xFF\xFB\x90\x44\x00')
        results["audio_write"] = "success"
        os.remove(test_file)
    except Exception as e:
        results["audio_write"] = f"failed: {str(e)}"

    # 获取目录信息
    results["directories"] = {
        "debug_dir": {
            "path": config.DEBUG_DIR,
            "exists": os.path.exists(config.DEBUG_DIR),
            "writable": os.access(config.DEBUG_DIR, os.W_OK) if os.path.exists(config.DEBUG_DIR) else False,
            "contents": os.listdir(config.DEBUG_DIR) if os.path.exists(config.DEBUG_DIR) else []
        },
        "text_dir": {
            "path": text_dir,
            "exists": os.path.exists(text_dir),
            "writable": os.access(text_dir, os.W_OK) if os.path.exists(text_dir) else False,
            "contents": os.listdir(text_dir) if os.path.exists(text_dir) else []
        },
        "audio_dir": {
            "path": audio_dir,
            "exists": os.path.exists(audio_dir),
            "writable": os.access(audio_dir, os.W_OK) if os.path.exists(audio_dir) else False,
            "contents": os.listdir(audio_dir) if os.path.exists(audio_dir) else []
        }
    }

    # 获取环境变量
    results["config"] = {
        "DEBUG_MODE": config.DEBUG_MODE,
        "DEBUG_DIR": config.DEBUG_DIR,
        "DEBUG_SAVE_TEXT": config.DEBUG_SAVE_TEXT,
        "DEBUG_SAVE_AUDIO": config.DEBUG_SAVE_AUDIO
    }

    return results

if __name__ == "__main__":
    logger.info(f"启动 Volcano TTS 服务，监听 {config.HOST}:{config.PORT}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
