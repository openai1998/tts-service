#!/usr/bin/env python
"""
文本过滤测试脚本

此脚本用于测试文本过滤模块的功能，可以验证过滤规则是否正常工作。
"""

import os
import json
import logging
from pathlib import Path

# 设置环境变量以启用过滤功能（仅用于测试）
os.environ['TEXT_FILTER_ENABLED'] = 'true'
os.environ['TEXT_FILTER_USE_DEFAULT_RULES'] = 'true'

# 导入过滤模块（在设置环境变量后导入）
from text_filter import TextFilter, filter_text

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 测试文本
TEST_TEXTS = [
    # 测试1：包含详情标签的文本
    """
    这是一段正常文本，下面是一段引用资料。

    <details><summary>资料[0]: 乌克兰局势_新华网</summary>
    王毅强调，中方从危机爆发第一天起就主张对话谈判，寻求政治解决，就在为和平奔走、为促谈努力。

    Link

    </details>

    这是引用资料后的正常文本，应该保留。
    """,

    # 测试2：包含思考过程的文本
    """
    根据您的问题，我认为解决方案如下：

    思考过程：首先我需要分析问题的本质，查找相关资料，然后根据已知信息推导出可能的解决方案。这个问题涉及到多个方面，包括技术可行性、成本效益和实施难度。

    最终的解决方案是使用A方案，因为它更加高效。
    """,

    # 测试3：包含链接标记的文本
    """
    您可以参考以下资源：
    1. Python官方文档
    2. Stack Overflow上的相关讨论

    Link

    希望这些资源对您有所帮助。
    """,

    # 测试4：混合多种需要过滤的内容
    """
    以下是对您问题的回答：

    <details><summary>资料[1]: Python编程_百度百科</summary>
    Python是一种广泛使用的解释型、高级和通用的编程语言。

    Link

    </details>

    思考过程：分析问题需要考虑Python的特性和适用场景，以及与其他编程语言的比较。

    根据以上分析，Python适合用于数据分析、Web开发和人工智能等领域。

    Link

    希望这个回答对您有帮助。
    """
]

def main():
    """主测试函数"""
    print("=" * 50)
    print("文本过滤测试")
    print("=" * 50)

    # 创建过滤器实例
    filter_instance = TextFilter()

    # 确保过滤器已启用
    if not filter_instance.enabled:
        print("警告：过滤器未启用，请检查环境变量设置")
        return

    print(f"已加载 {len(filter_instance.rules)} 条过滤规则:")
    for i, rule in enumerate(filter_instance.rules, 1):
        print(f"  {i}. {rule['name']}: {rule['pattern'].pattern}")

    print("\n" + "=" * 50)

    # 测试每个文本
    for i, test_text in enumerate(TEST_TEXTS, 1):
        print(f"\n测试 {i}:")
        print("-" * 30)
        print("原始文本:")
        print("-" * 30)
        print(test_text)

        # 应用过滤
        filtered_text, filtered_items = filter_instance.filter_text(test_text)

        print("-" * 30)
        print(f"过滤后文本 (移除了 {len(filtered_items)} 处内容):")
        print("-" * 30)
        print(filtered_text)

        print("-" * 30)
        print("被过滤的内容:")
        print("-" * 30)
        for j, item in enumerate(filtered_items, 1):
            print(f"{j}. 规则: {item['rule_name']}")
            print(f"   内容: {item['content'][:50]}..." if len(item['content']) > 50 else f"   内容: {item['content']}")
            print()

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    main()
