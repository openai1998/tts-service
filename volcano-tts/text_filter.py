"""
文本过滤模块 - 用于过滤不需要转换为TTS的特定内容

此模块提供了一个可配置的文本过滤系统，用于识别和过滤掉不需要进行TTS转换的文本内容。
主要用于处理如OpenWebUI等系统返回的引用资料、思考过程等内容。

用户可以通过.env文件配置过滤规则和是否启用过滤功能。
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Pattern, Tuple, Optional, Union
import logging

# 获取日志记录器
logger = logging.getLogger('text_filter')

class TextFilter:
    """文本过滤器类，用于过滤不需要TTS的文本内容"""

    def __init__(self):
        # 从环境变量加载配置
        self.enabled = self._parse_bool_env('TEXT_FILTER_ENABLED', False)

        # 加载过滤规则
        self.rules = []
        self._load_rules()

        # 记录初始化状态
        if self.enabled:
            logger.info(f"文本过滤器已启用，已加载 {len(self.rules)} 条规则")
        else:
            logger.info("文本过滤器已禁用")

    def _parse_bool_env(self, env_name: str, default: bool) -> bool:
        """解析布尔类型的环境变量"""
        value = os.getenv(env_name, str(default)).lower()
        return value in ('true', '1', 'yes', 'y', 'on')

    def _load_rules(self) -> None:
        """加载过滤规则"""
        # 1. 从环境变量加载内置规则
        if self._parse_bool_env('TEXT_FILTER_USE_DEFAULT_RULES', True):
            self._add_default_rules()

        # 2. 从环境变量加载自定义规则
        custom_rules_str = os.getenv('TEXT_FILTER_CUSTOM_RULES', '')
        if custom_rules_str:
            try:
                custom_rules = json.loads(custom_rules_str)
                for rule in custom_rules:
                    if isinstance(rule, dict) and 'pattern' in rule:
                        self._add_rule(
                            rule['pattern'],
                            rule.get('name', '自定义规则'),
                            rule.get('description', ''),
                            rule.get('is_regex', False)
                        )
            except json.JSONDecodeError:
                logger.error("解析自定义规则失败，请检查TEXT_FILTER_CUSTOM_RULES环境变量格式")

        # 3. 从文件加载规则
        rules_file = os.getenv('TEXT_FILTER_RULES_FILE', '')
        if rules_file:
            rules_path = Path(rules_file)
            if rules_path.exists() and rules_path.is_file():
                try:
                    with open(rules_path, 'r', encoding='utf-8') as f:
                        file_rules = json.load(f)
                        for rule in file_rules:
                            if isinstance(rule, dict) and 'pattern' in rule:
                                self._add_rule(
                                    rule['pattern'],
                                    rule.get('name', '文件规则'),
                                    rule.get('description', ''),
                                    rule.get('is_regex', False)
                                )
                except Exception as e:
                    logger.error(f"从文件加载规则失败: {str(e)}")

    def _add_default_rules(self) -> None:
        """添加默认的过滤规则"""
        # 添加默认规则 - 详情标签
        self._add_rule(
            r'<details><summary>资料\[\d+\]:.+?</summary>.*?</details>',
            '详情标签',
            '过滤<details>标签包含的引用资料',
            True
        )

        # 添加默认规则 - 思考过程
        self._add_rule(
            r'思考过程：.*?(?=\n\n|$)',
            '思考过程',
            '过滤标记为思考过程的内容',
            True
        )

        # 添加默认规则 - 链接
        self._add_rule(
            r'Link\s*\n',
            '链接标记',
            '过滤单独的Link标记行',
            True
        )

    def _add_rule(self, pattern: str, name: str, description: str, is_regex: bool) -> None:
        """添加一条过滤规则"""
        try:
            if is_regex:
                compiled_pattern = re.compile(pattern, re.DOTALL)
            else:
                # 如果不是正则表达式，转义特殊字符
                escaped_pattern = re.escape(pattern)
                compiled_pattern = re.compile(escaped_pattern)

            self.rules.append({
                'pattern': compiled_pattern,
                'name': name,
                'description': description,
                'is_regex': is_regex
            })
            logger.debug(f"已添加过滤规则: {name}")
        except re.error as e:
            logger.error(f"添加规则 '{name}' 失败: {str(e)}")

    def filter_text(self, text: str) -> Tuple[str, List[Dict]]:
        """
        过滤文本中不需要TTS的内容

        参数:
            text: 要过滤的原始文本

        返回:
            Tuple[str, List[Dict]]:
                - 过滤后的文本
                - 被过滤内容的列表，每项包含 {rule_name, content, position}
        """
        if not self.enabled or not text:
            return text, []

        filtered_text = text
        filtered_items = []

        # 应用所有规则
        for rule in self.rules:
            pattern = rule['pattern']
            matches = list(pattern.finditer(filtered_text))

            # 从后向前替换，避免位置偏移
            for match in reversed(matches):
                start, end = match.span()
                matched_content = match.group(0)

                # 记录被过滤的内容
                filtered_items.append({
                    'rule_name': rule['name'],
                    'content': matched_content,
                    'position': (start, end)
                })

                # 替换文本
                filtered_text = filtered_text[:start] + filtered_text[end:]

        # 清理多余的空行
        filtered_text = re.sub(r'\n{3,}', '\n\n', filtered_text)
        filtered_text = filtered_text.strip()

        # 记录过滤结果
        if filtered_items:
            logger.info(f"已过滤 {len(filtered_items)} 处内容，原文本长度: {len(text)}，过滤后长度: {len(filtered_text)}")

        return filtered_text, filtered_items

# 创建全局过滤器实例
text_filter = TextFilter()

def filter_text(text: str) -> str:
    """
    过滤文本中不需要TTS的内容（便捷函数）

    参数:
        text: 要过滤的原始文本

    返回:
        str: 过滤后的文本
    """
    filtered_text, _ = text_filter.filter_text(text)
    return filtered_text
