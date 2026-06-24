import json
from pathlib import Path


KB_DIR = Path(__file__).resolve().parents[1] / "knowledge_base"

CATEGORY_FILES = {
    "Scented Candle": "scented_candle.json",
    "Reed Diffuser": "reed_diffuser.json",
    "Home Fragrance Gift Set": "gift_set.json",
    "Room Spray": "room_spray.json",
    "Linen Spray": "linen_spray.json",
}

SUPPORTED_CATEGORIES = list(CATEGORY_FILES.keys())

BUILTIN_ALIASES = {
    "Scented Candle": ["香薰蜡烛", "香氛蜡烛", "芳香蜡烛", "大豆蜡烛"],
    "Reed Diffuser": ["无火香薰", "藤条香薰", "香薰藤条", "扩香瓶"],
    "Home Fragrance Gift Set": ["香薰礼盒", "香氛礼盒", "蜡烛礼盒"],
    "Room Spray": ["室内喷雾", "房间喷雾", "家居香氛喷雾"],
    "Linen Spray": ["织物喷雾", "床品喷雾", "衣物香氛喷雾"],
}


def load_json(name: str) -> dict:
    path = KB_DIR / name
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_category(product_type: str | None) -> str:
    if not product_type:
        return "Unknown"

    lowered = product_type.lower()
    for category, file_name in CATEGORY_FILES.items():
        data = load_json(file_name)
        aliases = [category, *BUILTIN_ALIASES.get(category, []), *data.get("aliases", [])]
        if any(alias.lower() in lowered for alias in aliases):
            return category

    unsupported_markers = [
        "essential oil diffuser",
        "car fragrance",
        "incense",
        "perfume",
        "skincare",
        "pet",
        "kitchen",
        "electronic",
    ]
    if any(marker in lowered for marker in unsupported_markers):
        return "Unsupported"

    return "Unknown"


def retrieve_fragrance_knowledge(product_type: str | None, content_goal: str) -> dict:
    category = normalize_category(product_type)
    if category not in CATEGORY_FILES:
        return {
            "category": category,
            "supported": False,
            "supported_categories": SUPPORTED_CATEGORIES,
            "compliance": load_json("compliance.json"),
            "fragrance_semantics": load_json("fragrance_semantics.json"),
        }

    return {
        "category": category,
        "supported": True,
        "category_knowledge": load_json(CATEGORY_FILES[category]),
        "content_goal": content_goal,
        "compliance": load_json("compliance.json"),
        "fragrance_semantics": load_json("fragrance_semantics.json"),
    }
