import json
import os
import re
from html import unescape
from urllib.parse import urlparse

import requests
from tavily import TavilyClient

from utils.api_errors import normalize_api_error
from utils.env_loader import load_project_env
from utils.fragrance_rag import retrieve_fragrance_knowledge
from utils.gemini_vision import analyze_product_images
from utils.gpt_analysis import create_json_chat_completion, init_openai, parse_json_response
from utils.retry import retry_call

load_project_env()


CONTENT_GOALS = {
    "natural_seeding": "TikTok 自然种草",
    "shop_conversion": "TikTok Shop 带货",
    "ai_video": "AI 视频生成",
    "gift_marketing": "礼物营销",
    "hook_testing": "爆款 Hook 测试",
}

AGE_RANGES = ["18-24", "18-35", "25-35", "25-44"]


def extract_url_from_share_text(text: str) -> str:
    """Extract the first URL from raw ecommerce share text."""
    if not text:
        return ""

    normalized = text.strip()
    match = re.search(r"https?://[^\s，。；,;）)】\]]+", normalized)
    if match:
        return match.group(0).strip()

    # Some pasted links omit the scheme. Keep this conservative to avoid
    # treating ordinary product titles as domains.
    match = re.search(r"((?:qr|detail|m|www)\.1688\.com/[^\s，。；,;）)】\]]+)", normalized)
    if match:
        return "https://" + match.group(1).strip()

    return normalized


def is_valid_url(url: str) -> bool:
    parsed = urlparse(extract_url_from_share_text(url))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def detect_platform(url: str) -> str:
    host = urlparse(extract_url_from_share_text(url)).netloc.lower()
    if "1688" in host:
        return "1688"
    if "alibaba" in host:
        return "Alibaba"
    if "amazon" in host:
        return "Amazon"
    if "etsy" in host:
        return "Etsy"
    if "tiktok" in host:
        return "TikTok Shop"
    if "taobao" in host or "tmall" in host:
        return "Taobao/Tmall"
    if "pinduoduo" in host or "yangkeduo" in host:
        return "Pinduoduo"
    return "Independent site"


def init_tavily():
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY 未设置，请检查 .env 文件")
    return TavilyClient(api_key=api_key)


def fetch_with_tavily(product_url: str) -> dict:
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


def search_link_snippet(product_url: str) -> str:
    """Fallback to Tavily search snippets when direct extraction is too thin."""
    client = init_tavily()
    result = retry_call(
        lambda: client.search(
            query=product_url,
            search_depth="advanced",
            max_results=3,
            include_raw_content=True,
        )
    )
    chunks = []
    for item in result.get("results", []):
        chunks.extend(
            [
                item.get("title", ""),
                item.get("content", ""),
                item.get("raw_content", ""),
            ]
        )
    return "\n\n".join(chunk for chunk in chunks if chunk).strip()


def fetch_with_jina(product_url: str) -> str:
    if product_url.startswith("https://"):
        jina_url = "https://r.jina.ai/http://" + product_url.removeprefix("https://")
    elif product_url.startswith("http://"):
        jina_url = "https://r.jina.ai/http://" + product_url.removeprefix("http://")
    else:
        jina_url = "https://r.jina.ai/http://" + product_url

    response = requests.get(jina_url, timeout=30)
    response.raise_for_status()
    return response.text


def fetch_with_scrapling(product_url: str) -> str:
    """Fetch a page with browser-like TLS/header fingerprinting as a fallback."""
    from scrapling import Fetcher

    response = Fetcher.get(
        product_url,
        stealthy_headers=True,
        impersonate="chrome",
        timeout=30,
        follow_redirects=True,
        headers={
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "referer": "https://www.1688.com/",
        },
    )

    text_parts = [
        getattr(response, "url", ""),
        getattr(response, "text", "") or "",
    ]
    try:
        text_parts.append(response.get_all_text(separator="\n"))
    except Exception:
        pass

    html = getattr(response, "html_content", "") or ""
    if html and len("\n".join(text_parts)) < 1200:
        text_parts.append(html)

    raw_text = "\n\n".join(part for part in text_parts if part).strip()
    if "1688.com" in urlparse(product_url).netloc.lower():
        summary = extract_1688_product_summary(raw_text)
        if summary:
            return f"{summary}\n\n--- Raw page excerpt ---\n{raw_text[:12000]}"
    return raw_text


def _first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.S)
    return unescape(match.group(1)).strip() if match else ""


def _unique_matches(text: str, pattern: str, limit: int = 20) -> list[str]:
    values = []
    for value in re.findall(pattern, text, flags=re.S):
        value = unescape(str(value)).strip()
        if value and value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return values


def extract_1688_product_summary(page_text: str) -> str:
    """Extract compact product facts from 1688's embedded page data."""
    if not page_text:
        return ""

    title = (
        _first_match(page_text, r'"offerTitle"\s*:\s*"([^"]+)"')
        or _first_match(page_text, r'"subject"\s*:\s*"([^"]+)"')
    )
    if not title:
        return ""

    company = _first_match(page_text, r'"companyName"\s*:\s*"([^"]+)"')
    seller = _first_match(page_text, r'"sellerLoginId"\s*:\s*"([^"]+)"') or _first_match(
        page_text, r'"loginId"\s*:\s*"([^"]+)"'
    )
    category = _first_match(page_text, r'"leafCategoryName"\s*:\s*"([^"]+)"')
    price = (
        _first_match(page_text, r'"priceDisplay"\s*:\s*"([^"]+)"')
        or _first_match(page_text, r'"offerPriceDisplay"\s*:\s*"([^"]+)"')
    )
    sale_count = _first_match(page_text, r'"saledCount"\s*:\s*(\d+)')
    if not sale_count:
        sale_values = [int(value) for value in re.findall(r'"saleCount"\s*:\s*(\d+)', page_text)]
        sale_count = str(max(sale_values)) if sale_values else ""
    unit = _first_match(page_text, r'"offerUnit"\s*:\s*"([^"]+)"') or _first_match(
        page_text, r'"unit"\s*:\s*"([^"]+)"'
    )
    delivery = _first_match(page_text, r'"deliveryLimitText"\s*:\s*"([^"]+)"') or _first_match(
        page_text, r'"logisticsText"\s*:\s*"([^"]+)"'
    )

    fragrance_options = _unique_matches(page_text, r'"sku1"\s*:\s*"([^"]+)"', 16)
    if not fragrance_options:
        fragrance_options = _unique_matches(page_text, r'"prop"\s*:\s*"香型".*?"name"\s*:\s*"([^"]+)"', 16)
    volume_options = _unique_matches(page_text, r'"sku2"\s*:\s*"([^"]+)"', 8)
    if not volume_options:
        volume_options = _unique_matches(page_text, r'"prop"\s*:\s*"净含量".*?"name"\s*:\s*"([^"]+)"', 8)
    sku_specs = _unique_matches(page_text, r'"specAttrs"\s*:\s*"([^"]+)"', 20)

    service_names = _unique_matches(page_text, r'"serviceName"\s*:\s*"([^"]+)"', 10)
    images = _unique_matches(page_text, r'"fullPathImageURI"\s*:\s*"([^"]+)"', 8)
    if not images:
        images = _unique_matches(page_text, r'https://cbu01\.alicdn\.com/img/ibank/[^"\\]+?\.jpg', 8)

    lines = [
        "1688 商品抓取摘要",
        f"商品标题: {title}",
    ]
    optional_fields = [
        ("店铺/公司", company),
        ("卖家", seller),
        ("类目", category),
        ("价格", price),
        ("成交/销量", sale_count),
        ("单位", unit),
        ("物流", delivery),
    ]
    lines.extend(f"{label}: {value}" for label, value in optional_fields if value)
    if fragrance_options:
        lines.append("香型选项: " + " / ".join(fragrance_options))
    if volume_options:
        lines.append("容量选项: " + " / ".join(volume_options))
    if sku_specs:
        lines.append("SKU 规格: " + "；".join(sku_specs[:12]))
    if service_names:
        lines.append("服务标签: " + " / ".join(service_names))
    if images:
        lines.append("主图链接: " + " | ".join(images))

    return "\n".join(lines)


def has_product_markers(text: str) -> bool:
    """Detect whether text contains product signals, even if it is short."""
    lowered = text.lower()
    product_markers = [
        "价格",
        "规格",
        "香",
        "蜡烛",
        "香薰",
        "藤条",
        "喷雾",
        "礼盒",
        "材质",
        "持久",
        "卧室",
        "龙井",
        "桂花",
        "product",
        "scent",
        "fragrance",
        "candle",
        "diffuser",
        "spray",
    ]
    return any(marker in lowered for marker in product_markers)


def is_useful_product_text(text: str) -> bool:
    lowered = text.lower()
    if len(text.strip()) < 500:
        return False

    hard_block_markers = [
        "captcha interception",
        "access denied",
        "unusual traffic",
        "detected unusual traffic",
        "we have detected unusual traffic",
        "安全验证",
        "验证码",
        "访问受限",
    ]
    if any(marker in lowered for marker in hard_block_markers):
        return False

    bad_markers = [
        "captcha",
        "verify",
        "login",
        "enable javascript",
        "access denied",
        "forbidden",
        "安全验证",
        "验证码",
        "登录",
        "页面不存在",
    ]
    if any(marker in lowered for marker in bad_markers) and len(text.strip()) < 2500:
        return False

    return has_product_markers(text)


def collect_link_content(product_url: str, source_hint_text: str = "") -> dict:
    tavily_text = ""
    image_urls = []
    errors = []

    try:
        tavily_result = fetch_with_tavily(product_url)
        results = tavily_result.get("results", [])
        if results:
            first = results[0]
            parts = [
                first.get("title", ""),
                first.get("raw_content", ""),
                first.get("content", ""),
            ]
            tavily_text = "\n\n".join(part for part in parts if part).strip()
            image_urls = first.get("images") or []
    except Exception as exc:
        errors.append(f"Tavily: {exc}")

    jina_text = ""
    if len(tavily_text) < 800:
        try:
            jina_text = fetch_with_jina(product_url)
        except Exception as exc:
            errors.append(f"Jina: {exc}")

    search_text = ""
    combined = "\n\n".join(part for part in [tavily_text, jina_text] if part).strip()
    if not is_useful_product_text(combined):
        try:
            search_text = search_link_snippet(product_url)
        except Exception as exc:
            errors.append(f"Tavily Search: {exc}")

    scrapling_text = ""
    combined_before_scrapling = "\n\n".join(
        part for part in [tavily_text, jina_text, search_text] if part
    ).strip()
    if not is_useful_product_text(combined_before_scrapling):
        try:
            scrapling_text = fetch_with_scrapling(product_url)
            if not image_urls:
                image_urls = _unique_matches(scrapling_text, r'https://cbu01\.alicdn\.com/img/ibank/[^"\s|]+?\.jpg', 12)
        except Exception as exc:
            errors.append(f"Scrapling: {exc}")

    if is_useful_product_text(scrapling_text):
        combined = "\n\n".join(part for part in [source_hint_text, scrapling_text] if part).strip()
        fetched_text = scrapling_text
    else:
        combined = "\n\n".join(
            part
            for part in [source_hint_text, tavily_text, jina_text, search_text, scrapling_text]
            if part
        ).strip()
        fetched_text = "\n\n".join(
            part for part in [tavily_text, jina_text, search_text, scrapling_text] if part
        ).strip()
    if has_product_markers(source_hint_text) and not is_useful_product_text(fetched_text):
        combined = source_hint_text.strip()
    useful = has_product_markers(source_hint_text) or is_useful_product_text(combined)
    return {
        "success": useful,
        "error": "；".join(errors) if errors and not useful else None,
        "platform": detect_platform(product_url),
        "text": combined[:24000],
        "text_length": len(combined),
        "useful": useful,
        "images": image_urls[:12],
    }


def product_profile_has_content(profile: dict) -> bool:
    if not profile:
        return False

    name = profile.get("product_name", {})
    meaningful_values = [
        name.get("chinese"),
        name.get("english"),
        profile.get("product_type"),
        profile.get("fragrance"),
        profile.get("material"),
        profile.get("volume_spec"),
        profile.get("packaging"),
        profile.get("visual_style"),
    ]
    judgment = profile.get("product_type_judgment", {}).get("result")
    if judgment and judgment not in {"Unknown", "Unsupported"}:
        meaningful_values.append(judgment)

    return any(str(value).strip() for value in meaningful_values if value is not None)


def generate_product_profile(
    product_url: str,
    target_country: str,
    target_persona: str,
    content_goal: str,
    uploaded_image=None,
    source_hint_text: str = "",
) -> dict:
    try:
        link_content = collect_link_content(product_url, source_hint_text=source_hint_text)
        if not link_content["success"] and uploaded_image is None:
            return {
                "success": False,
                "error": (
                    "链接内容读取不足。1688 页面经常存在动态渲染/登录验证/反爬，"
                    "Tavily/Jina 可能只能拿到空壳页面。请上传产品图作为兜底，"
                    "或补充一个公开可访问的 Alibaba/Amazon/独立站链接。"
                ),
                "debug": {
                    "platform": link_content.get("platform"),
                    "text_length": link_content.get("text_length"),
                    "extract_error": link_content.get("error"),
                },
                "data": None,
            }

        vision_data = None
        if uploaded_image is not None:
            vision_result = analyze_product_images(uploaded_image, None)
            if vision_result.get("success"):
                vision_data = vision_result.get("data")

        client = init_openai()
        link_text = link_content.get("text", "")
        image_text = json.dumps(vision_data or {}, ensure_ascii=False, indent=2)
        prompt = f"""你是一个专业的香薰垂直跨境电商产品经理和 TikTok 营销顾问。
用户是中国跨境卖家，准备把香薰类产品卖到北美 TikTok / TikTok Shop。

请基于商品链接内容和可选图片分析，生成结构化产品档案。

目标国家：{target_country}
目标用户：{target_persona}
内容目标：{content_goal}
链接平台：{link_content.get("platform")}
商品链接：{product_url}

链接抓取内容：
{link_text}

图片分析结果：
{image_text}

支持品类只包括：
Scented Candle, Reed Diffuser, Home Fragrance Gift Set, Room Spray, Linen Spray
如果不是以上品类，请将 product_type_judgment.result 写为 "Unsupported" 或 "Unknown"。

严格输出 JSON：
{{
  "product_name": {{"chinese": "", "english": ""}},
  "product_type": "",
  "product_type_judgment": {{
    "result": "",
    "reason_chinese": "",
    "reason_english": ""
  }},
  "fragrance": "",
  "material": "",
  "volume_spec": "",
  "packaging": "",
  "customizable": null,
  "price_range": "",
  "visual_style": "",
  "use_scenes": [],
  "gift_suitable": null,
  "tiktok_suitable": null,
  "marketing_directions": [],
  "source_summary": {{
    "chinese": "",
    "english": ""
  }}
}}"""

        response = create_json_chat_completion(
            client=client,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        data = parse_json_response(response.choices[0].message.content or "")
        if "error" in data:
            return {"success": False, "error": data["error"], "data": None}

        if not product_profile_has_content(data):
            return {
                "success": False,
                "error": (
                    "链接已被读取，但没有提取到有效商品信息。"
                    "这通常是 1688 页面被登录/反爬/动态渲染挡住了。"
                    "请上传产品主图或包装图作为兜底后重新分析。"
                ),
                "debug": {
                    "platform": link_content.get("platform"),
                    "text_length": link_content.get("text_length"),
                    "content_preview": link_content.get("text", "")[:500],
                },
                "data": None,
            }

        data["_context"] = {
            "product_url": product_url,
            "target_country": target_country,
            "target_persona": target_persona,
            "content_goal": content_goal,
            "platform": link_content.get("platform"),
            "image_urls": link_content.get("images", []),
            "link_text_length": link_content.get("text_length"),
        }
        return {"success": True, "error": None, "data": data}
    except Exception as exc:
        return {"success": False, "error": normalize_api_error("openai", exc), "data": None}


def generate_marketing_plan(
    product_profile: dict,
    target_country: str,
    target_persona: str,
    content_goal: str,
) -> dict:
    try:
        client = init_openai()
        judgment = product_profile.get("product_type_judgment", {}).get("result")
        category_candidates = [product_profile.get("product_type"), judgment]
        rag = None
        for candidate in category_candidates:
            if not candidate:
                continue
            candidate_rag = retrieve_fragrance_knowledge(candidate, content_goal)
            rag = candidate_rag
            if candidate_rag.get("supported"):
                break
        if rag is None:
            rag = retrieve_fragrance_knowledge(None, content_goal)
        if not rag.get("supported"):
            return {
                "success": False,
                "error": (
                    "当前版本专注香薰类产品，暂不支持该品类。支持："
                    + "、".join(rag.get("supported_categories", []))
                ),
                "data": None,
            }

        prompt = f"""你是专业的北美 TikTok 香薰营销策略师。
请基于产品档案、香薰 RAG 知识库、目标国家、目标用户和内容目标，生成完整 TikTok 营销方案。

要求：
- 所有内容中英文对照。
- 英文必须自然、口语化、像北美 TikTok 用户真实表达。
- 不写 Amazon Listing 风格，不堆参数。
- 围绕场景、情绪、自我护理、礼物、家居氛围。
- 避免医疗功效或夸大承诺。

产品档案：
{json.dumps(product_profile, ensure_ascii=False, indent=2)}

RAG 知识库：
{json.dumps(rag, ensure_ascii=False, indent=2)}

目标国家：{target_country}
目标用户：{target_persona}
内容目标：{content_goal}

严格输出 JSON：
{{
  "product_summary": {{"chinese": "", "english": ""}},
  "product_type_judgment": {{"chinese": "", "english": ""}},
  "recommended_directions": [
    {{"chinese": "", "english": ""}}
  ],
  "user_pain_points": [
    {{"chinese": "", "english": ""}}
  ],
  "tiktok_selling_points": [
    {{"chinese": "", "english": ""}}
  ],
  "content_angles": [
    {{"chinese": "", "english": ""}}
  ],
  "hooks": [
    {{"chinese": "", "english": ""}}
  ],
  "video_script": {{
    "chinese": "",
    "english": ""
  }},
  "ai_video_prompt": {{
    "chinese": "",
    "english": ""
  }},
  "tiktok_caption": {{
    "chinese": "",
    "english": ""
  }},
  "hashtags": [],
  "comment_replies": [
    {{"question": "", "reply": ""}}
  ],
  "listing_selling_points": [
    {{"chinese": "", "english": ""}}
  ]
}}"""

        response = create_json_chat_completion(
            client=client,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.75,
        )
        data = parse_json_response(response.choices[0].message.content or "")
        if "error" in data:
            return {"success": False, "error": data["error"], "data": None}
        return {"success": True, "error": None, "data": data, "rag": rag}
    except Exception as exc:
        return {"success": False, "error": normalize_api_error("openai", exc), "data": None}
