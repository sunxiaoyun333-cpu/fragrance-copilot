import json
import os
import re

from openai import OpenAI

from utils.api_errors import normalize_api_error
from utils.env_loader import load_project_env
from utils.retry import retry_call
from utils.tavily_search import format_tavily_for_gpt

load_project_env()


def init_openai():
    """初始化 OpenAI 客户端。"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 未设置，请检查 .env 文件")
    return OpenAI(api_key=api_key)


def parse_json_response(text: str) -> dict:
    """从 GPT 返回文本中提取 JSON。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    pattern = r"```(?:json)?\s*([\s\S]*?)```"
    match = re.search(pattern, text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    return {
        "error": "JSON 解析失败",
        "raw_text": text,
    }


SYSTEM_PROMPT = """你是一个专业的跨境电商营销策略师，精通 TikTok 平台的内容营销。
你深度了解各国消费者的购买心理和文化背景。

你的输出必须同时包含中文和英文。
英文内容必须：
- 符合目标国家 TikTok 用户的真实表达习惯
- 使用口语化、有感染力的表达
- 避免任何翻译腔
- 避免过于正式的书面表达
- 听起来像是母语为英语的人写的

所有输出必须严格按照要求的 JSON 格式，不要添加任何额外的解释文字。"""


def create_json_chat_completion(
    client,
    messages: list[dict],
    temperature: float,
):
    """调用 OpenAI JSON 输出接口，并对短暂网络错误重试。"""
    return retry_call(
        lambda: client.chat.completions.create(
            model=os.getenv("OPENAI_TEXT_MODEL", "gpt-4o"),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )
    )


def generate_analysis_report(
    gemini_output: dict,
    tavily_results: dict,
    target_country: str,
) -> dict:
    """整合 Gemini 和 Tavily 的结果，生成产品分析报告。"""
    try:
        client = init_openai()
        gemini_data = json.dumps(
            gemini_output.get("data", {}),
            ensure_ascii=False,
            indent=2,
        )
        tavily_text = format_tavily_for_gpt(tavily_results)

        user_prompt = f"""请基于以下信息生成产品分析报告：

产品信息（来自图片识别）：
{gemini_data}

竞品参考数据（来自网络搜索）：
{tavily_text}

目标国家：{target_country}

请输出以下内容：

1. pain_points：目标国家消费者痛点（2-3条）
2. selling_points：产品核心卖点（3条）
3. target_persona：目标人群定位（1个精准画像）
4. competitor_reference：竞品参考分析

严格按照以下 JSON 格式输出：

{{
  "pain_points": [
    {{
      "chinese": "痛点中文描述",
      "english": "Pain point in English"
    }}
  ],
  "selling_points": [
    {{
      "chinese": "卖点中文描述",
      "english": "Selling point in English"
    }}
  ],
  "target_persona": {{
    "chinese": "年龄、性别、生活方式、消费动机的中文描述",
    "english": "Age, gender, lifestyle, purchase motivation in English"
  }},
  "competitor_reference": {{
    "title_style": "热门标题风格描述",
    "content_style": "内容风格特征描述"
  }}
}}"""

        response = create_json_chat_completion(
            client=client,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )

        result = parse_json_response(response.choices[0].message.content or "")
        if "error" in result:
            return {"success": False, "error": result["error"], "data": None}

        return {"success": True, "error": None, "data": result}

    except Exception as exc:
        return {
            "success": False,
            "error": normalize_api_error("openai", exc),
            "data": None,
        }


def generate_titles(analysis_report: dict) -> dict:
    """基于产品分析报告生成 3 个 TikTok 标题。"""
    try:
        client = init_openai()
        report_text = json.dumps(
            analysis_report.get("data", {}),
            ensure_ascii=False,
            indent=2,
        )

        user_prompt = f"""基于以下产品分析报告：
{report_text}

请生成 3 个风格明显不同的 TikTok 标题。

标题要求：
- 符合 TikTok 英文表达习惯
- 口语化，有感染力，能引发共鸣
- 避免翻译腔
- 长度不超过 150 字符
- 包含 1-2 个相关 Emoji
- 三个标题风格明显不同
  风格一：悬念式（制造好奇心）
  风格二：共鸣式（说出用户心声）
  风格三：场景式（描述使用场景）

严格按照以下 JSON 格式输出：

{{
  "titles": [
    {{
      "style": "悬念式",
      "english": "English title here 🕯️",
      "chinese": "中文释义"
    }},
    {{
      "style": "共鸣式",
      "english": "English title here ✨",
      "chinese": "中文释义"
    }},
    {{
      "style": "场景式",
      "english": "English title here 🌿",
      "chinese": "中文释义"
    }}
  ]
}}"""

        response = create_json_chat_completion(
            client=client,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
        )

        result = parse_json_response(response.choices[0].message.content or "")
        if "error" in result:
            return {"success": False, "error": result["error"], "data": None}

        return {"success": True, "error": None, "data": result}

    except Exception as exc:
        return {
            "success": False,
            "error": normalize_api_error("openai", exc),
            "data": None,
        }


def generate_copies(analysis_report: dict, selected_title: dict) -> dict:
    """基于产品分析报告和选定标题生成 3 版营销文案。"""
    try:
        client = init_openai()
        report_text = json.dumps(
            analysis_report.get("data", {}),
            ensure_ascii=False,
            indent=2,
        )

        user_prompt = f"""基于以下信息：

产品分析报告：
{report_text}

用户选定的标题：
{selected_title.get('english', '')}
（风格：{selected_title.get('style', '')}）

请生成 3 版风格不同的 TikTok 营销文案。

文案要求：
- 与选定标题的风格保持一致
- 符合 TikTok 英文表达习惯
- 口语化，有情感共鸣
- 长度不超过 150 字
- 包含适当 Emoji
- 结尾必须包含明确的 CTA
  （例如：Shop now、Link in bio、Try it tonight 等）

Tag 要求：
- 每版文案配套 5-8 个 Tag
- 包含热门通用 Tag
- 包含产品相关精准 Tag
- Tag 前带 # 号

严格按照以下 JSON 格式输出：

{{
  "copies": [
    {{
      "version": "版本A",
      "english": "English copy here...",
      "chinese": "中文释义...",
      "tags": [
        "#SleepRoutine",
        "#SoyWaxCandle"
      ]
    }},
    {{
      "version": "版本B",
      "english": "English copy here...",
      "chinese": "中文释义...",
      "tags": [
        "#AromatherapyCandle",
        "#TikTokShop"
      ]
    }},
    {{
      "version": "版本C",
      "english": "English copy here...",
      "chinese": "中文释义...",
      "tags": [
        "#SelfCare",
        "#BedtimeVibes"
      ]
    }}
  ]
}}"""

        response = create_json_chat_completion(
            client=client,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
        )

        result = parse_json_response(response.choices[0].message.content or "")
        if "error" in result:
            return {"success": False, "error": result["error"], "data": None}

        return {"success": True, "error": None, "data": result}

    except Exception as exc:
        return {
            "success": False,
            "error": normalize_api_error("openai", exc),
            "data": None,
        }
