import os
from typing import Any

import requests


DEFAULT_MPT_BASE_URL = "http://127.0.0.1:8080"


def normalize_base_url(base_url: str | None = None) -> str:
    """Return a clean MoneyPrinterTurbo API base URL."""
    value = (base_url or os.getenv("MONEYPRINTER_API_BASE_URL") or DEFAULT_MPT_BASE_URL).strip()
    return value.rstrip("/")


def build_video_payload(
    marketing_plan: dict,
    product_profile: dict,
    target_country: str,
    *,
    video_subject: str = "",
    video_terms: str = "",
    voice_name: str = "",
    video_source: str = "pexels",
    video_count: int = 1,
) -> dict[str, Any]:
    """Convert ViralGen strategy output into a MoneyPrinterTurbo video request."""
    script = (marketing_plan.get("video_script") or {}).get("english", "")
    caption = (marketing_plan.get("tiktok_caption") or {}).get("english", "")
    prompt = (marketing_plan.get("ai_video_prompt") or {}).get("english", "")
    product_name = product_profile.get("product_name", {}) if product_profile else {}

    fallback_subject = (
        product_name.get("english")
        or product_profile.get("product_type")
        or product_profile.get("fragrance")
        or "home fragrance TikTok product video"
    )
    subject = video_subject.strip() or fallback_subject
    terms = video_terms.strip() or prompt or caption or subject

    payload = {
        "video_subject": subject,
        "video_script": script or caption or terms,
        "video_terms": terms,
        "video_aspect": "9:16",
        "video_concat_mode": "random",
        "video_clip_duration": 4,
        "video_count": int(video_count or 1),
        "video_source": video_source,
        "video_language": "en",
        "voice_name": voice_name,
        "voice_volume": 1.0,
        "bgm_type": "random",
        "bgm_volume": 0.25,
        "subtitle_enabled": True,
        "subtitle_position": "bottom",
        "font_name": "Microsoft YaHei",
        "font_size": 58,
        "text_fore_color": "#FFFFFF",
        "text_background_color": "transparent",
        "stroke_color": "#000000",
        "stroke_width": 1.5,
        "n_threads": 2,
        "paragraph_number": 1,
        "metadata": {
            "source": "viralgen-ai",
            "target_country": target_country,
            "product_url": product_profile.get("_context", {}).get("product_url", ""),
        },
    }
    return payload


def check_moneyprinter_health(base_url: str | None = None) -> dict[str, Any]:
    """Check whether MoneyPrinterTurbo API is reachable."""
    url = normalize_base_url(base_url)
    candidates = [
        f"{url}/docs",
        f"{url}/openapi.json",
        f"{url}/api/v1/ping",
    ]
    last_error = ""
    for candidate in candidates:
        try:
            response = requests.get(candidate, timeout=8)
            if response.status_code < 500:
                return {"success": True, "url": url, "status_code": response.status_code}
            last_error = f"{candidate} returned {response.status_code}"
        except Exception as exc:
            last_error = str(exc)
    return {"success": False, "url": url, "error": last_error}


def submit_video_task(payload: dict[str, Any], base_url: str | None = None) -> dict[str, Any]:
    """Submit a video generation task to MoneyPrinterTurbo."""
    url = normalize_base_url(base_url)
    try:
        response = requests.post(f"{url}/api/v1/videos", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return {"success": True, "error": None, "data": data}
    except Exception as exc:
        return {"success": False, "error": str(exc), "data": None}


def query_video_task(task_id: str, base_url: str | None = None) -> dict[str, Any]:
    """Query a MoneyPrinterTurbo video task."""
    url = normalize_base_url(base_url)
    task_id = str(task_id).strip()
    endpoints = [
        f"{url}/api/v1/tasks/{task_id}",
        f"{url}/api/v1/videos/{task_id}",
    ]
    last_error = ""
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=20)
            if response.status_code == 404:
                last_error = f"{endpoint} returned 404"
                continue
            response.raise_for_status()
            return {"success": True, "error": None, "data": response.json()}
        except Exception as exc:
            last_error = str(exc)
    return {"success": False, "error": last_error, "data": None}


def extract_task_id(response_data: dict[str, Any] | None) -> str:
    """Extract task id from common MoneyPrinterTurbo response shapes."""
    if not response_data:
        return ""
    data = response_data.get("data", response_data)
    if isinstance(data, dict):
        for key in ("task_id", "taskId", "id"):
            if data.get(key):
                return str(data[key])
    for key in ("task_id", "taskId", "id"):
        if response_data.get(key):
            return str(response_data[key])
    return ""
