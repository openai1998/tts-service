#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import base64
import argparse
import os
from playsound import playsound
import tempfile

class VolcengineTTS:
    def __init__(self):
        # 语言映射
        self.language_map = {
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
            "hi": "id",
        }

        # 默认发音人
        self.default_speakers = {
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
            "hi": "id_female_noor",
        }

        # 可用的发音人列表
        self.available_speakers = {
            "zh_cn": {
                "嘻哈歌手": "zh_male_rap",
                "四川女声": "zh_female_sichuan",
                "东北男声": "tts.other.BV021_streaming",
                "粤语男声": "tts.other.BV026_streaming",
                "台湾女声": "tts.other.BV025_streaming",
                "影视配音": "zh_male_xiaoming",
                "男主播": "zh_male_zhubo",
                "女主播": "zh_female_zhubo",
                "清新女声": "zh_female_qingxin",
                "少儿故事": "zh_female_story"
            },
            "en": {
                "美式男声": "en_male_adam",
                "美式女声": "tts.other.BV027_streaming",
                "英式男声": "en_male_bob",
                "英式女声": "tts.other.BV032_TOBI_streaming",
                "澳洲男声": "tts.other.BV516_streaming",
                "澳洲女声": "en_female_sarah"
            }
            # 其他语言的发音人可以根据需要添加
        }

    def list_speakers(self, lang):
        """列出指定语言的所有可用发音人"""
        if lang in self.available_speakers:
            print(f"\n{lang} 可用发音人:")
            for name, value in self.available_speakers[lang].items():
                print(f"  {name}: {value}")
        else:
            print(f"不支持的语言: {lang}")
            print(f"支持的语言: {', '.join(self.language_map.keys())}")

    def tts(self, text, lang, speaker=None, output_file=None, play=True):
        """
        将文本转换为语音

        参数:
            text: 要转换的文本
            lang: 语言代码 (如 zh_cn, en)
            speaker: 发音人 (如果为None，则使用默认发音人)
            output_file: 输出文件路径 (如果为None，则使用临时文件)
            play: 是否播放生成的音频

        返回:
            音频文件路径
        """
        # 检查语言是否支持
        if lang not in self.language_map:
            raise ValueError(f"不支持的语言: {lang}，支持的语言: {', '.join(self.language_map.keys())}")

        # 获取语言映射
        language = self.language_map[lang]

        # 获取发音人
        if not speaker:
            speaker = self.default_speakers[lang]

        # 构建请求头
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

        # 构建请求体
        payload = {
            "text": text,
            "speaker": speaker,
            "language": language
        }

        # 发送请求
        response = requests.post(
            "https://translate.volcengine.com/crx/tts/v1/",
            headers=headers,
            json=payload
        )

        # 检查响应状态
        if response.status_code != 200:
            raise Exception(f"HTTP请求错误，状态码: {response.status_code}\n{response.text}")

        # 解析响应
        result = response.json()

        # 检查是否有音频数据
        if not result.get("audio") or not result["audio"].get("data"):
            raise Exception(f"未获取到音频数据: {result}")

        # 获取Base64编码的音频数据
        base64_data = result["audio"]["data"]

        # 解码Base64数据
        audio_data = base64.b64decode(base64_data)

        # 确定输出文件路径
        if not output_file:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            output_file = temp_file.name
            temp_file.close()

        # 写入音频数据
        with open(output_file, "wb") as f:
            f.write(audio_data)

        print(f"音频已保存到: {output_file}")

        # 播放音频
        if play:
            try:
                print("正在播放音频...")
                playsound(output_file)
            except Exception as e:
                print(f"播放音频时出错: {e}")

        return output_file

def main():
    parser = argparse.ArgumentParser(description="火山引擎TTS语音合成工具")
    parser.add_argument("--text", "-t", help="要转换为语音的文本")
    parser.add_argument("--lang", "-l", default="zh_cn", help="语言代码 (默认: zh_cn)")
    parser.add_argument("--speaker", "-s", help="发音人ID")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--no-play", action="store_true", help="不播放生成的音频")
    parser.add_argument("--list-speakers", action="store_true", help="列出指定语言的所有可用发音人")

    args = parser.parse_args()

    tts = VolcengineTTS()

    if args.list_speakers:
        tts.list_speakers(args.lang)
        return

    if not args.text:
        text = input("请输入要转换为语音的文本: ")
    else:
        text = args.text

    try:
        tts.tts(
            text=text,
            lang=args.lang,
            speaker=args.speaker,
            output_file=args.output,
            play=not args.no_play
        )
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    main()
