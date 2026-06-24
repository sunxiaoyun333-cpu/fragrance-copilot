import base64
import os

import requests
from openai import OpenAI

from utils.api_errors import normalize_api_error
from utils.env_loader import load_project_env
from utils.retry import retry_call

load_project_env()

def init_openai():
    """初始化 OpenAI 客户端。"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 未设置，请检查 .env 文件")
    return OpenAI(api_key=api_key)


def _extract_image_payload(image_data) -> tuple[str | None, bytes | None]:
    """兼容 url 和 b64_json 两种图片返回格式。"""
    image_url = getattr(image_data, "url", None)
    image_b64 = getattr(image_data, "b64_json", None)
    image_bytes = base64.b64decode(image_b64) if image_b64 else None
    return image_url, image_bytes


def _create_image(client: OpenAI, prompt: str):
    """兼容不同 OpenAI 图片模型支持的参数，并自动降级可用模型。"""
    configured_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    fallback_models = [
        configured_model,
        "gpt-image-1",
        "dall-e-3",
        "dall-e-2",
    ]

    # 去重但保留顺序，方便用户通过环境变量指定优先模型。
    models = list(dict.fromkeys(fallback_models))
    last_error = None

    for model in models:
        try:
            params = {
                "model": model,
                "prompt": prompt,
                "size": "1024x1024",
                "n": 1,
            }

            if model.startswith("gpt-image"):
                params["quality"] = os.getenv("OPENAI_IMAGE_QUALITY", "high")
            elif model.startswith("dall-e-3"):
                params["quality"] = os.getenv("OPENAI_IMAGE_QUALITY", "hd")

            return client.images.generate(**params)
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            can_try_next = any(
                marker in message
                for marker in [
                    "does not exist",
                    "invalid_value",
                    "unknown parameter",
                    "unsupported",
                    "invalid_request_error",
                ]
            )
            if not can_try_next:
                raise

    raise last_error



def generate_banner_image(image_prompt: str) -> dict:
    """生成产品宣传图。"""
    try:
        client = init_openai()
        response = retry_call(lambda: _create_image(client, image_prompt))
        image_url, image_bytes = _extract_image_payload(response.data[0])
        return {
            "success": True,
            "error": None,
            "url": image_url,
            "image_bytes": image_bytes,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": normalize_api_error("openai", exc),
            "url": None,
            "image_bytes": None,
        }


def generate_grid_image(
    image_prompt: str,
    selected_style: dict,
    selected_scene: dict,
) -> dict:
    """生成九宫格合图。"""
    try:
        client = init_openai()
        grid_prompt = f"""A professional 3x3 grid layout image for social media,
showing a product from 9 different angles and perspectives.

Base prompt: {image_prompt}
Base style: {selected_style.get('description_english', '')}
Base scene: {selected_scene.get('english', '')}

Grid layout:
Top-left: front view, centered product
Top-center: 45-degree angle view
Top-right: close-up detail shot
Middle-left: overhead flat lay view
Middle-center: lifestyle scene with props
Middle-right: ingredient or material detail
Bottom-left: soft focus bokeh background
Bottom-center: full environment scene
Bottom-right: atmospheric mood shot

Requirements:
- Clear grid separation between each cell
- Consistent color palette and lighting throughout
- Each cell is complete and well-composed
- Professional product photography quality
- photorealistic, high quality, 8k"""

        response = retry_call(lambda: _create_image(client, grid_prompt))
        image_url, image_bytes = _extract_image_payload(response.data[0])
        return {
            "success": True,
            "error": None,
            "url": image_url,
            "image_bytes": image_bytes,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": normalize_api_error("openai", exc),
            "url": None,
            "image_bytes": None,
        }


def download_image_bytes(url: str | None) -> bytes | None:
    """从 URL 下载图片字节，供 Streamlit 下载。"""
    if not url:
        return None

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception:
        return None
