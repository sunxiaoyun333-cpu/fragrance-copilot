import io
import json
import os
import re
import base64
import socket

import google.generativeai as genai
from openai import OpenAI
from PIL import Image

from utils.api_errors import normalize_api_error
from utils.env_loader import load_project_env
from utils.retry import retry_call

load_project_env()


def init_gemini():
    """初始化 Gemini 客户端。"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 未设置，请检查 .env 文件")
    genai.configure(api_key=api_key)


def init_openai():
    """初始化 OpenAI 客户端，用作 Vision 降级方案。"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 未设置，请检查 .env 文件")
    return OpenAI(api_key=api_key)


def is_gemini_reachable(timeout_seconds: int = 5) -> bool:
    """快速检查本机是否能连到 Gemini API。"""
    try:
        with socket.create_connection(
            ("generativelanguage.googleapis.com", 443),
            timeout=timeout_seconds,
        ):
            return True
    except OSError:
        return False


def parse_json_response(text: str) -> dict:
    """从 Gemini 返回文本中提取 JSON。"""
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


def get_empty_product_data() -> dict:
    """返回空的产品数据结构。"""
    return {
        "product_type": None,
        "appearance": {
            "color": None,
            "packaging_style": None,
            "visual_features": None,
            "size_estimate": None,
        },
        "ingredients": [],
        "materials": None,
        "specifications": {
            "volume": None,
            "weight": None,
            "burn_time": None,
            "certifications": [],
        },
    }


def _read_uploaded_image(uploaded_file):
    image_bytes = uploaded_file.read()
    uploaded_file.seek(0)
    image = Image.open(io.BytesIO(image_bytes))
    return image_bytes, image


def _get_mime_type(uploaded_file) -> str:
    return getattr(uploaded_file, "type", None) or "image/png"


def _build_product_prompt(has_ingredient_image: bool = True) -> str:
    ingredient_context = (
        "图片2：产品配料表或成分说明图。请优先从这张图提取成分、材质、规格和认证。"
        if has_ingredient_image
        else "未提供配料表或成分说明图。不要因为缺少配料图而判定失败，只从产品图可见文字和视觉信息中提取。"
    )
    prompt = """你是一个专业的电商产品视觉识别和信息提取助手。
我将提供：
- 图片1：产品外观图
- __INGREDIENT_CONTEXT__

请仔细分析图片，提取以下信息：

从产品外观图提取：
- 产品类型（product_type）：例如 aromatherapy candle、ceramic mug、skincare serum
- 品牌名或产品名如果可见，请写入 visual_features
- 外观颜色（color）：产品的主要颜色
- 包装风格（packaging_style）：例如简约、奢华、自然风格等
- 品牌视觉特征（visual_features）：包装上的文字、Logo、图案、标签、形状、材质质感
- 产品尺寸估计（size_estimate）：如果可以判断的话

从配料表图或产品图可见文字提取：
- 核心成分列表（ingredients）：所有可见的成分
- 材质信息（materials）：例如天然大豆蜡、椰子蜡等
- 规格参数（specifications）：容量、重量、燃烧时长等
- 产品认证信息（certifications）：例如天然、有机、无毒、纯素等

重要规则：
1. 只提取图片中实际可见的信息
2. 无法判断的字段填写 null
3. 不要推测或添加图片中没有的信息
4. 所有提取的内容尽量使用图片原文，不要翻译
5. 如果配料图没有提供，ingredients 使用 []，materials / specifications 中不可见字段填 null
6. 如果产品图上有清晰文字，请优先利用文字判断产品类型，不要只凭外观猜测
7. product_type 应该尽量具体，但必须基于图片可见信息；如果只能大致判断，请写较宽泛类型

请严格按照以下 JSON 格式输出，不要添加任何额外文字：

{
  "product_type": "",
  "appearance": {
    "color": "",
    "packaging_style": "",
    "visual_features": "",
    "size_estimate": null
  },
  "ingredients": [],
  "materials": "",
  "specifications": {
    "volume": null,
    "weight": null,
    "burn_time": null,
    "certifications": []
  }
}"""
    return prompt.replace("__INGREDIENT_CONTEXT__", ingredient_context)


def _analyze_with_openai_vision(
    product_image_bytes: bytes,
    product_mime_type: str,
    ingredient_image_bytes: bytes | None = None,
    ingredient_mime_type: str | None = None,
) -> dict:
    client = init_openai()
    has_ingredient_image = ingredient_image_bytes is not None
    prompt = _build_product_prompt(has_ingredient_image)
    product_data_url = (
        f"data:{product_mime_type};base64,"
        f"{base64.b64encode(product_image_bytes).decode('utf-8')}"
    )
    content = [
        {"type": "text", "text": prompt},
        {"type": "text", "text": "图片1 - 产品外观图："},
        {
            "type": "image_url",
            "image_url": {"url": product_data_url, "detail": "high"},
        },
    ]
    if has_ingredient_image:
        ingredient_data_url = (
            f"data:{ingredient_mime_type};base64,"
            f"{base64.b64encode(ingredient_image_bytes).decode('utf-8')}"
        )
        content.extend(
            [
                {"type": "text", "text": "图片2 - 配料表图或成分说明图："},
                {
                    "type": "image_url",
                    "image_url": {"url": ingredient_data_url, "detail": "high"},
                },
            ]
        )

    response = retry_call(
        lambda: client.chat.completions.create(
            model=os.getenv("OPENAI_VISION_MODEL", "gpt-4o"),
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
    )
    return parse_json_response(response.choices[0].message.content or "")


def analyze_product_images(product_image_file, ingredient_image_file=None) -> dict:
    """使用 Gemini Vision 分析图片；Gemini 不可达时自动降级到 OpenAI Vision。"""
    product_image_bytes, product_image = _read_uploaded_image(product_image_file)
    product_image_file.seek(0)

    has_ingredient_image = ingredient_image_file is not None
    ingredient_image_bytes = None
    ingredient_image = None
    if has_ingredient_image:
        ingredient_image_bytes, ingredient_image = _read_uploaded_image(ingredient_image_file)
        ingredient_image_file.seek(0)

    try:
        if is_gemini_reachable():
            init_gemini()
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = genai.GenerativeModel(model_name)
            gemini_parts = [
                _build_product_prompt(has_ingredient_image),
                "图片1 - 产品外观图：",
                product_image,
            ]
            if has_ingredient_image:
                gemini_parts.extend(
                    [
                        "图片2 - 配料表图或成分说明图：",
                        ingredient_image,
                    ]
                )
            response = model.generate_content(gemini_parts, request_options={"timeout": 90})
            result = parse_json_response(getattr(response, "text", "") or "")
        else:
            result = _analyze_with_openai_vision(
                product_image_bytes=product_image_bytes,
                product_mime_type=_get_mime_type(product_image_file),
                ingredient_image_bytes=ingredient_image_bytes,
                ingredient_mime_type=(
                    _get_mime_type(ingredient_image_file)
                    if has_ingredient_image
                    else None
                ),
            )

        if "error" in result:
            return {
                "success": False,
                "error": result["error"],
                "raw_text": result.get("raw_text", ""),
                "data": get_empty_product_data(),
            }

        return {
            "success": True,
            "error": None,
            "data": result,
        }

    except Exception as exc:
        return {
            "success": False,
            "error": normalize_api_error("gemini", exc),
            "data": get_empty_product_data(),
        }
