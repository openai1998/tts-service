import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import config

# 确保日志目录存在
log_dir = os.path.dirname(config.LOG_FILE_PATH)
os.makedirs(log_dir, exist_ok=True)

# 日志级别映射
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

def setup_logger(name):
    """
    设置并返回一个配置好的日志记录器

    参数:
        name: 日志记录器名称

    返回:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)

    # 设置日志级别
    log_level = LOG_LEVELS.get(config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    # 清除现有的处理器
    if logger.handlers:
        logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(config.LOG_FORMAT)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 解析日志轮转大小
    size_str = config.LOG_ROTATION
    if 'MB' in size_str:
        max_bytes = int(size_str.split('MB')[0].strip()) * 1024 * 1024
    elif 'KB' in size_str:
        max_bytes = int(size_str.split('KB')[0].strip()) * 1024
    else:
        max_bytes = 1024 * 1024  # 默认1MB

    # 文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        config.LOG_FILE_PATH,
        maxBytes=max_bytes,
        backupCount=10  # 保留10个备份文件
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 如果是错误日志记录器，添加专门的错误日志文件
    if name == 'error':
        error_log_path = os.path.join(log_dir, 'volcano-tts-error.log')
        error_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=max_bytes,
            backupCount=10
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        logger.addHandler(error_handler)

    # 如果是请求日志记录器，添加专门的请求日志文件
    if name == 'request':
        request_log_path = os.path.join(log_dir, 'volcano-tts-request.log')
        request_handler = RotatingFileHandler(
            request_log_path,
            maxBytes=max_bytes,
            backupCount=10
        )
        request_handler.setFormatter(formatter)
        logger.addHandler(request_handler)

    return logger

# 创建应用日志记录器
app_logger = setup_logger('volcano_tts')
request_logger = setup_logger('request')
error_logger = setup_logger('error')

def get_logger(name=None):
    """获取指定名称的日志记录器，如果未指定则返回应用日志记录器"""
    if name == 'request':
        return request_logger
    elif name == 'error':
        return error_logger
    elif name:
        return setup_logger(name)
    return app_logger
