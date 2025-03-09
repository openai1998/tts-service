from fastapi import FastAPI, HTTPException, Response, Header, Depends, Request
from pydantic import BaseModel
import uvicorn
import requests
import base64
import logging
import json
from functools import lru_cache
import time

# 配置日志
logging.basicConfig(level=logging.INFO)  # 将默认日志级别改为INFO，减少不必要的输出
logger = logging.getLogger(__name__)

app = FastAPI(title="Volcano TTS API")

# 添加 API 密钥配置
API_KEY = "sk-36565655"  # 修改为与 OpenWebUI 相同的 API Key

class TTSRequest(BaseModel):
    model: str = "tts-1"  # OpenAI 格式
    input: str           # 要转换的文本
    voice: str          # 声音选择
    response_format: str = "mp3"  # 输出格式

# 语言映射（来自 main.js）
LANGUAGE_MAP = {
    "zh_cn": "zh",
    "zh_tw": "zh",
    "en": "en",
    "ja": "jp",
    "ko": "kr",
    "fr": "fr",
    "es": "es",
    "ru": "ru",
    "de": "de",
    "it": "it",
    "tr": "tr",
    "pt_pt": "pt",
    "pt_br": "pt",
    "vi": "vi",
    "ms": "ms",
    "ar": "ar",
    "hi": "id"
}

# 完整的话者配置（来自 info.json）
VOICE_CONFIG = {
    "zh_cn": {
        "zh_male_rap": "嘻哈歌手",
        "zh_female_sichuan": "四川女声",
        "tts.other.BV021_streaming": "东北男声",
        "tts.other.BV026_streaming": "粤语男声",
        "tts.other.BV025_streaming": "台湾女声",
        "zh_male_xiaoming": "影视配音",
        "zh_male_zhubo": "男主播",
        "zh_female_zhubo": "女主播",
        "zh_female_qingxin": "清新女声",
        "zh_female_story": "少儿故事"
    },
    "en": {
        "en_male_adam": "美式男声",
        "tts.other.BV027_streaming": "美式女声",
        "en_male_bob": "英式男声",
        "tts.other.BV032_TOBI_streaming": "英式女声",
        "tts.other.BV516_streaming": "澳洲男声",
        "en_female_sarah": "澳洲女声"
    },
    "ja": {
        "jp_male_satoshi": "日语男声",
        "jp_female_mai": "日语女声"
    },
    "ko": {
        "kr_male_gye": "韩语男声",
        "tts.other.BV059_streaming": "韩语女声"
    },
    "fr": {
        "fr_male_enzo": "法语男声",
        "tts.other.BV078_streaming": "法语女声"
    },
    "es": {
        "es_male_george": "西语男声",
        "tts.other.BV065_streaming": "西语女声"
    },
    "ru": {
        "tts.other.BV068_streaming": "俄语女声"
    },
    "de": {
        "de_female_sophie": "德语女声"
    },
    "it": {
        "tts.other.BV087_streaming": "意语男声"
    },
    "tr": {
        "tts.other.BV083_streaming": "土耳其男声"
    },
    "pt_pt": {
        "tts.other.BV531_streaming": "葡语男声",
        "pt_female_alice": "葡语女声"
    },
    "pt_br": {
        "tts.other.BV531_streaming": "葡语男声",
        "pt_female_alice": "葡语女声"
    },
    "vi": {
        "tts.other.BV075_streaming": "越南男声",
        "tts.other.BV074_streaming": "越南女声"
    },
    "ms": {
        "tts.other.BV092_streaming": "马来女声"
    },
    "ar": {
        "tts.other.BV570_streaming": "阿语男声"
    },
    "hi": {
        "tts.other.BV160_streaming": "印尼男声",
        "id_female_noor": "印尼女声"
    }
}

# 默认话者（来自 main.js）
DEFAULT_SPEAKERS = {
    "zh_cn": "zh_male_xiaoming",
    "zh_tw": "zh_male_xiaoming",
    "en": "en_male_adam",
    "ja": "jp_male_satoshi",
    "ko": "kr_male_gye",
    "fr": "fr_male_enzo",
    "es": "es_male_george",
    "ru": "tts.other.BV068_streaming",
    "de": "de_female_sophie",
    "it": "tts.other.BV087_streaming",
    "tr": "tts.other.BV083_streaming",
    "pt_pt": "pt_female_alice",
    "pt_br": "pt_female_alice",
    "vi": "tts.other.BV074_streaming",
    "ms": "tts.other.BV092_streaming",
    "ar": "tts.other.BV570_streaming",
    "hi": "id_female_noor"
}

# 验证API密钥的依赖函数
async def verify_api_key(authorization: str = Header(None)):
    if authorization:
        provided_key = authorization.replace("Bearer ", "")
        if provided_key != API_KEY:
            logger.warning(f"Invalid API key provided: {provided_key}")
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )
    return True

# 请求计数和性能监控
REQUEST_STATS = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "avg_response_time": 0
}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # 记录请求开始时间
    start_time = time.time()

    # 更新请求计数
    REQUEST_STATS["total_requests"] += 1

    # 处理请求
    response = await call_next(request)

    # 计算响应时间
    process_time = time.time() - start_time

    # 更新统计信息
    if response.status_code < 400:
        REQUEST_STATS["successful_requests"] += 1
    else:
        REQUEST_STATS["failed_requests"] += 1

    # 更新平均响应时间（简单移动平均）
    REQUEST_STATS["avg_response_time"] = (
        (REQUEST_STATS["avg_response_time"] * (REQUEST_STATS["total_requests"] - 1) + process_time) /
        REQUEST_STATS["total_requests"]
    )

    return response

# 使用LRU缓存来缓存TTS结果，提高性能
@lru_cache(maxsize=100)
def get_tts_audio(text, speaker, language):
    """
    获取TTS音频数据，使用LRU缓存提高性能
    """
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

    # 构建火山引擎请求数据 - 使用已知可行的格式
    payload = {
        "type": "Json",
        "payload": {
            "text": text,
            "speaker": speaker,
            "language": language
        }
    }

    # 发送请求到火山引擎
    response = requests.post(
        "https://translate.volcengine.com/crx/tts/v1/",
        headers=headers,
        json=payload,
        verify=False,
        timeout=10
    )

    # 检查响应状态
    if response.status_code != 200:
        logger.error(f"HTTP请求错误，状态码: {response.status_code}\n{response.text}")
        raise Exception(f"TTS generation failed: {response.text}")

    # 解析响应
    result = response.json()

    # 检查是否有音频数据
    if not result.get("audio") or not result["audio"].get("data"):
        logger.error(f"未获取到音频数据: {result}")
        raise Exception(f"Invalid response format: {result}")

    # 获取Base64编码的音频数据
    base64_data = result["audio"]["data"]

    # 解码Base64数据
    audio_data = base64.b64decode(base64_data)
    logger.info(f"Successfully generated audio, size: {len(audio_data)} bytes")

    return audio_data

@app.post("/v1/audio/speech")
async def create_speech(request: TTSRequest, _: bool = Depends(verify_api_key)):
    try:
        # 记录请求
        logger.info(f"TTS request received: voice={request.voice}, text_length={len(request.input)}")

        # 确定语言
        lang = "zh"  # 默认中文
        speaker = request.voice

        # 从声音确定语言
        for lang_code, voices in VOICE_CONFIG.items():
            if speaker in voices:
                lang = LANGUAGE_MAP.get(lang_code, "zh")
                break

        # 如果没找到指定的声音，使用默认话者
        if not any(speaker in voices for voices in VOICE_CONFIG.values()):
            logger.warning(f"Voice {speaker} not found, using default voice")
            lang = "zh"
            speaker = DEFAULT_SPEAKERS["zh_cn"]

        # 获取TTS音频数据（使用缓存）
        audio_data = get_tts_audio(request.input, speaker, lang)

        # 返回MP3音频数据
        return Response(
            content=audio_data,
            media_type="audio/mp3"
        )

    except Exception as e:
        logger.exception("Error in create_speech:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/voices")
async def list_voices(_: bool = Depends(verify_api_key)):
    """列出所有可用的声音"""
    voices = []
    for lang_code, voice_dict in VOICE_CONFIG.items():
        for voice_id, voice_name in voice_dict.items():
            voices.append({
                "id": voice_id,
                "name": voice_name,
                "language": lang_code,
                "language_code": LANGUAGE_MAP.get(lang_code, "zh"),
                "is_default": voice_id == DEFAULT_SPEAKERS.get(lang_code)
            })
    return {"voices": voices}

@app.get("/stats")
async def get_stats(_: bool = Depends(verify_api_key)):
    """获取API使用统计信息"""
    return {
        "stats": REQUEST_STATS,
        "cache_info": get_tts_audio.cache_info()._asdict()
    }

@app.get("/")
async def root():
    """API 文档"""
    return {
        "message": "火山引擎 TTS API 服务",
        "version": "1.0.0",
        "docs_url": "/docs",
        "voices_url": "/v1/voices",
        "stats_url": "/stats",
        "supported_languages": list(LANGUAGE_MAP.keys()),
        "auth_required": True,
        "default_api_key": API_KEY
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5050)
