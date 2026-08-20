# -*- coding: utf-8 -*-
"""
AI 蓝屏分析接口(aiAnalyzer) - 预留
====================================
为后续"AI 解读蓝屏"预留:
- AI key 配置: setAiConfig / getAiConfig(存配置文件, key 不写入代码)
- analyzeReport: OpenAI 兼容接口调用骨架(未配置 key 时返回 None, 不影响主流程)

接入说明(后续实现时):
1. 配置 AI key: setAiConfig(api_key="sk-xxx", api_base="https://api.openai.com/v1", model="gpt-4o-mini")
2. 调用: result = analyzeReport(bsod_report_text)
   返回 AI 的分析/建议文本; 未配置返回 None
"""

import json
import os
import urllib.request

# AI 配置文件(与代码分离, key 不提交到 git)
_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_config.json")

# 默认模型(OpenAI 兼容)
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_API_BASE = "https://api.openai.com/v1"

# 分析提示词(中文通俗解读)
_SYSTEM_PROMPT = (
    "你是一位 Windows 系统安全专家, 请用通俗易懂的中文向普通用户解释蓝屏原因, "
    "并给出可操作的处理建议, 控制在 200 字以内。"
)


# ====================================================================
# AI 配置
# ====================================================================
def setAiConfig(api_key, api_base=None, model=None):
    """
    保存 AI 配置(api key 等)到本地配置文件
    :param api_key: API Key<str>
    :param api_base: 接口地址<str>, 默认 OpenAI 兼容地址
    :param model: 模型名<str>, 默认 DEFAULT_MODEL
    :return: None
    """
    config = getAiConfig()
    config["api_key"] = api_key
    if api_base:
        config["api_base"] = api_base
    if model:
        config["model"] = model
    try:
        with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[aiAnalyzer] 保存 AI 配置失败: {e}")


def getAiConfig():
    """
    读取 AI 配置
    :return: {"api_key": str, "api_base": str, "model": str}
    """
    default = {"api_key": "", "api_base": DEFAULT_API_BASE, "model": DEFAULT_MODEL}
    try:
        if os.path.exists(_CONFIG_FILE):
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            default.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass
    return default


def hasAiKey():
    """是否已配置 AI key"""
    return bool(getAiConfig().get("api_key", "").strip())


# ====================================================================
# AI 分析(预留骨架, OpenAI 兼容 chat completions)
# ====================================================================
def analyzeReport(report_text):
    """
    调用 AI 分析蓝屏报告(OpenAI 兼容接口)
    :param report_text: 蓝屏报告文本<str>
    :return: AI 分析结果<str>; 未配置 key / 调用失败返回 None
    """
    config = getAiConfig()
    api_key = config.get("api_key", "").strip()
    if not api_key:
        print("[aiAnalyzer] 未配置 AI key, 跳过 AI 分析(setAiConfig 可配置)")
        return None
    if not report_text:
        return None

    api_base = config.get("api_base", DEFAULT_API_BASE).rstrip('/')
    model = config.get("model", DEFAULT_MODEL)
    url = f"{api_base}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": report_text},
        ],
        "temperature": 0.4,
        "max_tokens": 500,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[aiAnalyzer] AI 分析调用失败: {e}")
        return None
