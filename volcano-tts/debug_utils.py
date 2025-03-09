"""
调试工具模块

提供保存请求文本和生成音频的功能，用于调试和问题排查。
"""

import os
import json
import time
import logging
import datetime
import glob
from typing import Dict, Any, List, Optional, Union

import config

# 获取日志记录器
logger = logging.getLogger('debug_utils')

def save_request_text(request_id: str, request_data: Dict[str, Any], filtered_text: Optional[str] = None) -> None:
    """
    保存请求文本数据到文件

    参数:
        request_id: 请求ID
        request_data: 请求数据字典
        filtered_text: 过滤后的文本（如果有）
    """
    if not config.DEBUG_MODE or not config.DEBUG_SAVE_TEXT:
        logger.debug(f"调试模式未启用或未配置保存文本: DEBUG_MODE={config.DEBUG_MODE}, DEBUG_SAVE_TEXT={config.DEBUG_SAVE_TEXT}")
        return

    try:
        # 确保目录存在
        text_dir = os.path.join(config.DEBUG_DIR, 'text')
        try:
            os.makedirs(text_dir, exist_ok=True)
            logger.debug(f"确保目录存在: {text_dir}")
        except Exception as dir_error:
            logger.error(f"创建目录失败: {text_dir}, 错误: {str(dir_error)}")
            # 尝试在当前目录创建
            text_dir = os.path.join(os.getcwd(), 'DEBUG', 'text')
            os.makedirs(text_dir, exist_ok=True)
            logger.info(f"已在当前目录创建: {text_dir}")

        # 检查目录权限
        if not os.access(text_dir, os.W_OK):
            logger.error(f"没有写入权限: {text_dir}")
            # 尝试修复权限
            try:
                os.chmod(text_dir, 0o777)
                logger.info(f"已尝试修复目录权限: {text_dir}")
            except Exception as perm_error:
                logger.error(f"修复权限失败: {str(perm_error)}")
                return

        # 创建保存数据
        save_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'request_id': request_id,
            'original_request': request_data,
            'filtered_text': filtered_text
        }

        # 生成文件名
        timestamp = int(time.time())
        filename = f"{timestamp}_{request_id}.json"
        filepath = os.path.join(text_dir, filename)

        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        logger.info(f"已保存请求文本到 {filepath}")

        # 清理旧文件
        cleanup_old_files('text')
    except Exception as e:
        logger.error(f"保存请求文本失败: {str(e)}", exc_info=True)

def save_audio_data(request_id: str, audio_data: bytes, is_filtered: bool = False) -> None:
    """
    保存音频数据到文件

    参数:
        request_id: 请求ID
        audio_data: 音频数据
        is_filtered: 是否经过过滤
    """
    if not config.DEBUG_MODE or not config.DEBUG_SAVE_AUDIO or not audio_data:
        logger.debug(f"调试模式未启用或未配置保存音频: DEBUG_MODE={config.DEBUG_MODE}, DEBUG_SAVE_AUDIO={config.DEBUG_SAVE_AUDIO}")
        return

    try:
        # 确保目录存在
        audio_dir = os.path.join(config.DEBUG_DIR, 'audio')
        try:
            os.makedirs(audio_dir, exist_ok=True)
            logger.debug(f"确保目录存在: {audio_dir}")
        except Exception as dir_error:
            logger.error(f"创建目录失败: {audio_dir}, 错误: {str(dir_error)}")
            # 尝试在当前目录创建
            audio_dir = os.path.join(os.getcwd(), 'DEBUG', 'audio')
            os.makedirs(audio_dir, exist_ok=True)
            logger.info(f"已在当前目录创建: {audio_dir}")

        # 检查目录权限
        if not os.access(audio_dir, os.W_OK):
            logger.error(f"没有写入权限: {audio_dir}")
            # 尝试修复权限
            try:
                os.chmod(audio_dir, 0o777)
                logger.info(f"已尝试修复目录权限: {audio_dir}")
            except Exception as perm_error:
                logger.error(f"修复权限失败: {str(perm_error)}")
                return

        # 生成文件名
        timestamp = int(time.time())
        filtered_tag = "_filtered" if is_filtered else ""
        filename = f"{timestamp}_{request_id}{filtered_tag}.mp3"
        filepath = os.path.join(audio_dir, filename)

        # 保存到文件
        with open(filepath, 'wb') as f:
            f.write(audio_data)

        logger.info(f"已保存音频数据到 {filepath}, 大小: {len(audio_data)} 字节")

        # 清理旧文件
        cleanup_old_files('audio')
    except Exception as e:
        logger.error(f"保存音频数据失败: {str(e)}", exc_info=True)

def cleanup_old_files(file_type: str) -> None:
    """
    清理旧文件，保持文件数量在限制范围内

    参数:
        file_type: 文件类型 ('text' 或 'audio')
    """
    try:
        # 获取目录路径
        dir_path = os.path.join(config.DEBUG_DIR, file_type)

        # 获取所有文件
        pattern = '*.json' if file_type == 'text' else '*.mp3'
        files = glob.glob(os.path.join(dir_path, pattern))

        # 按修改时间排序
        files.sort(key=os.path.getmtime)

        # 如果文件数量超过限制，删除最旧的文件
        if len(files) > config.DEBUG_MAX_FILES:
            files_to_delete = files[:len(files) - config.DEBUG_MAX_FILES]
            for file_path in files_to_delete:
                os.remove(file_path)
                logger.debug(f"已删除旧文件: {file_path}")
    except Exception as e:
        logger.error(f"清理旧文件失败: {str(e)}")

def get_debug_info() -> Dict[str, Any]:
    """
    获取调试信息

    返回:
        包含调试信息的字典
    """
    if not config.DEBUG_MODE:
        return {'debug_enabled': False}

    try:
        # 获取文本文件数量
        text_dir = os.path.join(config.DEBUG_DIR, 'text')
        text_files = glob.glob(os.path.join(text_dir, '*.json'))

        # 获取音频文件数量
        audio_dir = os.path.join(config.DEBUG_DIR, 'audio')
        audio_files = glob.glob(os.path.join(audio_dir, '*.mp3'))

        # 获取最新文件
        latest_text = max(text_files, key=os.path.getmtime) if text_files else None
        latest_audio = max(audio_files, key=os.path.getmtime) if audio_files else None

        return {
            'debug_enabled': True,
            'debug_dir': config.DEBUG_DIR,
            'save_text': config.DEBUG_SAVE_TEXT,
            'save_audio': config.DEBUG_SAVE_AUDIO,
            'max_files': config.DEBUG_MAX_FILES,
            'text_files_count': len(text_files),
            'audio_files_count': len(audio_files),
            'latest_text': os.path.basename(latest_text) if latest_text else None,
            'latest_audio': os.path.basename(latest_audio) if latest_audio else None
        }
    except Exception as e:
        logger.error(f"获取调试信息失败: {str(e)}")
        return {
            'debug_enabled': True,
            'error': str(e)
        }
