import json
import os

from tavily import TavilyClient

from utils.api_errors import normalize_api_error
from utils.env_loader import load_project_env
from utils.gpt_analysis import create_json_chat_completion, init_openai, parse_json_response
from utils.retry import retry_call

load_project_env()


def init_tavily():
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY 未设置，请检查 .env 文件")
    return TavilyClient(api_key=api_key)


def get_empty_product_data() -> dict:
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
        "source_url": None,
        "source_summary": None,
    }


def _extract_url_content(product_url: str) -> dict:
    client = init_tavily()
    return retry_call(
        lambda: client.extract(
            urls=product_url,
            include_images=True,
            extract_depth="advanced",
            format="markdown",
            timeout=45,
        )
    )


def _collect_extract_text(extract_result: dict) -> str:
    results = extract_result.get("results", [])
    if not results:
        return ""

    first = results[0]
    chunks = [
        first.get("title", ""),
        first.get("raw_content", ""),
        first.get("content", ""),
    ]
    images = first.get("images") or []
    if images:
        chunks.append("页面图片链接：\n" + "\n".join(images[:12]))

    return "\n\n".join(chunk for chunk in chunks if chunk).strip()


def _parse_product_page(product_url: str, page_text: str) -> dict:
    client = init_openai()
    clipped_text = page_text[:18000]
    prompt = f"""你是一个专业的跨境电商商品信息提取助手。
请从下面的商品链接页面内容中提取产品信息。页面可能来自 1688、淘宝、拼多多、独立站或供应商网站。

重要规则：
1. 优先提取页面真实存在的商品标题、卖点、规格、材质、成分、适用场景。
2. 如果页面内容是中文，可以保留中文原文；不要编造页面没有的信息。
3. 如果字段无法判断，填写 null；ingredients 没有就返回 []。
4. product_type 要尽量具体，例如 "portable electric blender"、"soy aromatherapy candle"。
5. visual_features 可写商品标题、主图描述、包装文字、页面卖点摘要。

商品链接：
{product_url}

页面内容：
{clipped_text}

严格输出 JSON：
{{
  "product_type": "",
  "appearance": {{
    "color": null,
    "packaging_style": null,
    "visual_features": "",
    "size_estimate": null
  }},
  "ingredients": [],
  "materials": null,
  "specifications": {{
    "volume": null,
    "weight": null,
    "burn_time": null,
    "certifications": []
  }},
  "source_url": "",
  "source_summary": ""
}}"""

    response = create_json_chat_completion(
        client=client,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return parse_json_response(response.choices[0].message.content or "")


def analyze_product_link(product_url: str) -> dict:
    try:
        extract_result = _extract_url_content(product_url)
        page_text = _collect_extract_text(extract_result)
        if not page_text:
            return {
                "success": False,
                "error": "未能从该链接提取到商品页面内容，请换一个公开可访问的商品链接。",
                "data": get_empty_product_data(),
            }

        data = _parse_product_page(product_url, page_text)
        if "error" in data:
            return {
                "success": False,
                "error": data["error"],
                "raw_text": data.get("raw_text", ""),
                "data": get_empty_product_data(),
            }

        data["source_url"] = data.get("source_url") or product_url
        return {
            "success": True,
            "error": None,
            "data": data,
            "raw_extract": page_text[:3000],
        }
    except Exception as exc:
        return {
            "success": False,
            "error": normalize_api_error("tavily", exc),
            "data": get_empty_product_data(),
        }


def merge_product_data(primary: dict, secondary: dict | None) -> dict:
    """Merge link and image extraction. Primary values win; secondary fills gaps."""
    if not secondary:
        return primary

    merged = json.loads(json.dumps(primary, ensure_ascii=False))
    secondary_data = secondary

    for key in ["product_type", "materials"]:
        if not merged.get(key) and secondary_data.get(key):
            merged[key] = secondary_data[key]

    merged.setdefault("appearance", {})
    for key, value in secondary_data.get("appearance", {}).items():
        if not merged["appearance"].get(key) and value:
            merged["appearance"][key] = value

    if not merged.get("ingredients") and secondary_data.get("ingredients"):
        merged["ingredients"] = secondary_data["ingredients"]

    merged.setdefault("specifications", {})
    for key, value in secondary_data.get("specifications", {}).items():
        if not merged["specifications"].get(key) and value:
            merged["specifications"][key] = value

    return merged
