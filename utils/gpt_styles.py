import json
import os

from openai import OpenAI

from utils.api_errors import normalize_api_error
from utils.env_loader import load_project_env
from utils.gpt_analysis import (
    SYSTEM_PROMPT,
    create_json_chat_completion,
    parse_json_response,
)

load_project_env()


def init_openai():
    """初始化 OpenAI 客户端。"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 未设置，请检查 .env 文件")
    return OpenAI(api_key=api_key)


def generate_styles(
    gemini_output: dict,
    analysis_report: dict,
    selected_title: dict,
    selected_copy: dict,
) -> dict:
    """基于产品特征和用户选择生成 3 种视觉风格。"""
    try:
        client = init_openai()
        product_data = json.dumps(
            gemini_output.get("data", {}),
            ensure_ascii=False,
            indent=2,
        )
        persona = analysis_report.get("data", {}).get("target_persona", {})

        user_prompt = f"""基于以下信息：

产品特征：
{product_data}

目标人群：
中文：{persona.get('chinese', '')}
英文：{persona.get('english', '')}

选定标题：{selected_title.get('english', '')}
选定文案：{selected_copy.get('english', '')}

请生成 3 种差异明显的视觉风格。

风格要求：
- 与产品特性高度相关
- 与目标人群审美匹配
- 三种风格之间差异明显
- 适合 TikTok 内容的视觉表达
- 视觉关键词要具体，可以直接用于图片生成

严格按照以下 JSON 格式输出：

{{
  "styles": [
    {{
      "name_english": "Forest Calm",
      "name_chinese": "森林宁静",
      "description_english": "Dark green tones, soft morning mist, natural wood textures, candlelight in dim forest setting",
      "description_chinese": "深绿色调，柔和晨雾，天然木质纹理，昏暗森林环境中的烛光",
      "visual_keywords": ["dark green", "morning mist", "wood texture", "candlelight"]
    }},
    {{
      "name_english": "Cozy Night",
      "name_chinese": "温暖夜晚",
      "description_english": "Warm amber lighting, soft bedding, minimalist bedroom, candle as centerpiece",
      "description_chinese": "暖琥珀色灯光，柔软床品，极简卧室风格，蜡烛作为视觉焦点",
      "visual_keywords": ["warm amber", "soft bedding", "minimalist", "cozy"]
    }},
    {{
      "name_english": "Clean Minimal",
      "name_chinese": "清爽极简",
      "description_english": "White background, natural light, botanical elements, clean and fresh aesthetic",
      "description_chinese": "白色背景，自然光线，植物元素点缀，干净清爽的美学风格",
      "visual_keywords": ["white background", "natural light", "botanical", "minimal"]
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


def generate_scenes(selected_style: dict) -> dict:
    """基于选定视觉风格生成 5 个具体拍摄场景。"""
    try:
        client = init_openai()
        user_prompt = f"""基于以下视觉风格：

风格名称：{selected_style.get('name_english', '')}
风格描述：{selected_style.get('description_english', '')}
视觉关键词：{', '.join(selected_style.get('visual_keywords', []))}

请生成 5 个具体的拍摄场景。

场景要求：
- 与选定风格强相关
- 场景描述具体，可以直接用于图片生成
- 适合产品展示
- 五个场景之间有明显差异
- 英文描述要专业，适合作为图片生成指令

严格按照以下 JSON 格式输出：

{{
  "scenes": [
    {{
      "english": "Mossy forest floor with soft morning light rays filtering through tall trees",
      "chinese": "苔藓覆盖的森林地面，柔和晨光透过高大树木照射"
    }},
    {{
      "english": "Rustic wooden cabin windowsill overlooking misty forest trees at dawn",
      "chinese": "质朴木屋窗台，俯瞰黎明时分薄雾中的森林树木"
    }},
    {{
      "english": "Smooth stone surface beside a quiet forest stream with dappled light",
      "chinese": "宁静森林小溪旁的光滑石面，阳光斑驳"
    }},
    {{
      "english": "Bedroom nightstand with dried botanicals and soft warm lamp light",
      "chinese": "卧室床头柜，搭配干燥植物装饰和柔和暖灯光"
    }},
    {{
      "english": "Marble bathtub edge with fresh eucalyptus branches and morning steam",
      "chinese": "大理石浴缸边缘，搭配新鲜尤加利树枝和晨间蒸汽"
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


def generate_prompts(
    gemini_output: dict,
    selected_style: dict,
    selected_scene: dict,
) -> dict:
    """整合所有选择，生成图片和视频 Prompt。"""
    try:
        client = init_openai()
        product_type = gemini_output.get("data", {}).get("product_type", "product")
        product_color = (
            gemini_output.get("data", {}).get("appearance", {}).get("color", "")
        )

        user_prompt = f"""基于以下信息：

产品类型：{product_type}
产品颜色：{product_color}

视觉风格：
英文：{selected_style.get('description_english', '')}
视觉关键词：{', '.join(selected_style.get('visual_keywords', []))}

拍摄场景：
英文：{selected_scene.get('english', '')}

请生成两组 AI 图片和视频生成指令。

图片 Prompt 要求：
- 专业产品摄影风格描述
- 包含场景、光线、色调、质感
- 突出产品本身
- 适配 DALL-E 3
- 使用专业摄影术语
- 结尾加上：photorealistic, high quality, 8k

视频 Prompt 要求：
- 包含场景、动作、氛围、节奏
- 适合 TikTok 竖屏短视频风格
- 有明确的视觉叙事逻辑
- 描述镜头运动方式

严格按照以下 JSON 格式输出：

{{
  "image_prompt": {{
    "english": "Product photography of [product] on [scene], [lighting], [color tones], [texture details], [atmosphere], photorealistic, high quality, 8k",
    "chinese": "对应的中文说明"
  }},
  "video_prompt": {{
    "english": "Slow cinematic [camera movement] of [product] in [scene], [atmosphere], [lighting], TikTok vertical format, [mood]",
    "chinese": "对应的中文说明"
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
