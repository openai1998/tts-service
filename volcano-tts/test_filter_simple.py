#!/usr/bin/env python
"""
简单的文本过滤测试脚本

此脚本用于测试文本过滤模块的基本功能，不依赖于完整的应用程序环境。
"""

import os
import json
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 设置环境变量以启用过滤功能（仅用于测试）
os.environ['TEXT_FILTER_ENABLED'] = 'true'
os.environ['TEXT_FILTER_USE_DEFAULT_RULES'] = 'true'

# 测试文本
TEST_TEXT = """
这是一段正常文本，下面是一段引用资料。

<details><summary>资料[0]: 乌克兰局势_新华网</summary>
王毅强调，中方从危机爆发第一天起就主张对话谈判，寻求政治解决，就在为和平奔走、为促谈努力。

Link

</details>

这是引用资料后的正常文本，应该保留。

思考过程：这是一段思考过程，不应该被朗读出来。

这是最后的总结内容，应该保留。
"""

def main():
    """主测试函数"""
    print("=" * 50)
    print("文本过滤简单测试")
    print("=" * 50)

    try:
        # 导入过滤模块（在设置环境变量后导入）
        from text_filter import TextFilter

        # 创建过滤器实例
        filter_instance = TextFilter()

        # 确保过滤器已启用
        if not filter_instance.enabled:
            print("警告：过滤器未启用，请检查环境变量设置")
            return

        print(f"已加载 {len(filter_instance.rules)} 条过滤规则")

        print("\n原始文本:")
        print("-" * 50)
        print(TEST_TEXT)

        # 应用过滤
        filtered_text, filtered_items = filter_instance.filter_text(TEST_TEXT)

        print("\n过滤后文本:")
        print("-" * 50)
        print(filtered_text)

        print("\n被过滤的内容:")
        print("-" * 50)
        for i, item in enumerate(filtered_items, 1):
            print(f"{i}. 规则: {item['rule_name']}")
            content_preview = item['content'][:50] + "..." if len(item['content']) > 50 else item['content']
            print(f"   内容: {content_preview}")

        print("\n测试完成")
        print("=" * 50)

    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
