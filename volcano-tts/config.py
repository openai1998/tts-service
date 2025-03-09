import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# 确定环境变量文件路径
env_path = Path(__file__).parent / '.env'

# 加载.env文件（如果存在）
# 注意：如果环境变量已经存在，dotenv不会覆盖它们
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"已加载配置文件: {env_path}")
else:
    print(f"警告: 配置文件 {env_path} 不存在，将使用默认值或环境变量")

# API配置
# 从环境变量获取API_KEY，如果不存在则使用默认值
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    print("警告: 未设置API_KEY环境变量，使用默认值")
    API_KEY = 'sk-564565KDA231D'  # 默认值

# 服务配置
# 尝试从环境变量获取PORT，如果不存在或无法转换为整数，则使用默认值
try:
    PORT = int(os.getenv('PORT', '5050'))
except (TypeError, ValueError):
    print("警告: PORT环境变量无效，使用默认值5050")
    PORT = 5050

# 尝试从环境变量获取HOST，如果不存在则使用默认值
HOST = os.getenv('HOST', '0.0.0.0')

# 文本处理配置
try:
    MAX_TEXT_LENGTH = int(os.getenv('MAX_TEXT_LENGTH', '500'))
except (TypeError, ValueError):
    print("警告: MAX_TEXT_LENGTH环境变量无效，使用默认值500")
    MAX_TEXT_LENGTH = 500

try:
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', '5'))
except (TypeError, ValueError):
    print("警告: MAX_WORKERS环境变量无效，使用默认值5")
    MAX_WORKERS = 5

# 日志配置
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', 'logs/volcano-tts.log')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOG_ROTATION = os.getenv('LOG_ROTATION', '1 MB')
LOG_RETENTION = os.getenv('LOG_RETENTION', '30 days')

# 确保日志目录路径一致
LOG_DIR = os.path.dirname(LOG_FILE_PATH)

# 调试配置
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() in ('true', '1', 'yes', 'y', 'on')
DEBUG_DIR = os.getenv('DEBUG_DIR', 'DEBUG')
DEBUG_SAVE_TEXT = os.getenv('DEBUG_SAVE_TEXT', 'true').lower() in ('true', '1', 'yes', 'y', 'on')
DEBUG_SAVE_AUDIO = os.getenv('DEBUG_SAVE_AUDIO', 'true').lower() in ('true', '1', 'yes', 'y', 'on')
try:
    DEBUG_MAX_FILES = int(os.getenv('DEBUG_MAX_FILES', '100'))
except (TypeError, ValueError):
    print("警告: DEBUG_MAX_FILES环境变量无效，使用默认值100")
    DEBUG_MAX_FILES = 100

# 确保调试目录存在
if DEBUG_MODE:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    os.makedirs(os.path.join(DEBUG_DIR, 'text'), exist_ok=True)
    os.makedirs(os.path.join(DEBUG_DIR, 'audio'), exist_ok=True)

# 日志级别映射
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

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

# 性能指标
PERFORMANCE_METRICS = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "avg_response_time": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "stream_requests": 0,
    "parallel_requests": 0,
    "total_audio_size": 0,
    "avg_segment_size": 0
}
