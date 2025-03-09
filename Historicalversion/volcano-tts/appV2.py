from fastapi import FastAPI, HTTPException, Response, Header, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import requests
import base64
import logging
import json
import re
import io
from typing import List, Generator

# 配置日志
logging.basicConfig(level=logging.INFO)  # 将默认日志级别改为INFO，减少不必要的输出
logger = logging.getLogger(__name__)

app = FastAPI(title="Volcano TTS API")

# 添加 API 密钥配置
API_KEY = "sk-36565655"  # 修改为与 OpenWebUI 相同的 API Key

# 文本分段最大长度（字符数）
MAX_TEXT_LENGTH = 500

class TTSRequest(BaseModel):
    model: str = "tts-1"  # OpenAI 格式
    input: str           # 要转换的文本
    voice: str          # 声音选择
    response_format: str = "mp3"  # 输出格式
    stream: bool = False  # 是否使用流式响应

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

# 文本分段函数
def split_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> List[str]:
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

# 获取单个文本段落的音频数据
def get_segment_audio(text: str, speaker: str, lang: str) -> bytes:
    """获取单个文本段落的音频数据"""
    # 构建火山引擎请求头
    headers = {
        "authority": "translate.volcengine.com",
        "origin": "chrome-extension://klgfhbdadaspgppeadghjjemk",
        "accept": "application/json, text/plain, */*",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "none",
        "cookie": "hasUserBehavior=1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
    }

    # 尝试不同的URL路径和请求体格式
    url_and_payload_formats = [
        # 包装在type/payload中
        {
            "url": "https://translate.volcengine.com/crx/tts/v1/",
            "payload": {
                "type": "Json",
                "payload": {
                    "text": text,
                    "speaker": speaker,
                    "language": lang
                }
            }
        },
        # 原始格式
        {
            "url": "https://translate.volcengine.com/crx/tts/v1/",
            "payload": {
                "text": text,
                "speaker": speaker,
                "language": lang
            }
        }
    ]

    response = None
    last_error = None

    for config in url_and_payload_formats:
        try:
            url = config["url"]
            payload = config["payload"]

            logger.info(f"Processing text segment (length: {len(text)})")
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                verify=False,
                timeout=10
            )

            # 如果请求成功，跳出循环
            if response.status_code == 200:
                break

            last_error = f"HTTP请求错误，状态码: {response.status_code}\n{response.text}"
        except Exception as e:
            logger.exception(f"Error trying {url}: {e}")
            last_error = str(e)

    # 如果所有URL都失败了
    if response is None or response.status_code != 200:
        logger.error(f"All URLs failed. Last error: {last_error}")
        raise Exception(f"TTS generation failed: {last_error}")

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
    logger.info(f"Successfully generated audio segment, size: {len(audio_data)} bytes")

    return audio_data

# 流式生成音频数据
def generate_audio_stream(text_segments: List[str], speaker: str, lang: str) -> Generator[bytes, None, None]:
    """流式生成音频数据"""
    for segment in text_segments:
        try:
            audio_data = get_segment_audio(segment, speaker, lang)
            yield audio_data
        except Exception as e:
            logger.error(f"Error generating audio for segment: {e}")
            # 继续处理下一段，而不是中断整个流

@app.post("/v1/audio/speech")
async def create_speech(request: TTSRequest, _: bool = Depends(verify_api_key)):
    try:
        # 记录请求
        logger.info(f"TTS request received: voice={request.voice}, text_length={len(request.input)}, stream={request.stream}")

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

        # 分割长文本
        text_segments = split_text(request.input)
        logger.info(f"Text split into {len(text_segments)} segments")

        # 流式响应
        if request.stream:
            return StreamingResponse(
                generate_audio_stream(text_segments, speaker, lang),
                media_type="audio/mpeg",
                headers={"Content-Disposition": "attachment; filename=speech.mp3"}
            )

        # 非流式响应 - 合并所有音频段
        all_audio_data = bytearray()
        for segment in text_segments:
            try:
                audio_data = get_segment_audio(segment, speaker, lang)
                all_audio_data.extend(audio_data)
            except Exception as e:
                logger.error(f"Error processing segment: {e}")
                raise HTTPException(status_code=500, detail=f"Error processing text segment: {str(e)}")

        logger.info(f"Successfully generated complete audio, total size: {len(all_audio_data)} bytes")

        # 返回合并后的MP3音频数据
        return Response(
            content=bytes(all_audio_data),
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

@app.get("/")
async def root():
    """API 文档"""
    return {
        "message": "火山引擎 TTS API 服务",
        "version": "1.1.0",
        "docs_url": "/docs",
        "voices_url": "/v1/voices",
        "supported_languages": list(LANGUAGE_MAP.keys()),
        "auth_required": True,
        "default_api_key": API_KEY,
        "features": {
            "long_text": f"支持长文本（自动分段，每段最大{MAX_TEXT_LENGTH}字符）",
            "streaming": "支持流式音频响应"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5050)
