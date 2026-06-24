import os

from tavily import TavilyClient

from utils.api_errors import normalize_api_error
from utils.env_loader import load_project_env
from utils.retry import retry_call

load_project_env()

def init_tavily():
    """初始化 Tavily 客户端。"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY 未设置，请检查 .env 文件")
    return TavilyClient(api_key=api_key)


def search_tiktok_competitors(product_type: str, target_country: str) -> dict:
    """搜索 TikTok 上同类产品的热门内容。"""
    try:
        client = init_tavily()
        normalized_product_type = product_type or "product"
        query = (
            f"TikTok best selling {normalized_product_type} "
            f"{target_country} top creator video titles content style 2024"
        )

        results = retry_call(
            lambda: client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=True,
            )
        )

        extracted = []
        for result in results.get("results", []):
            extracted.append(
                {
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "url": result.get("url", ""),
                }
            )

        return {
            "success": True,
            "error": None,
            "answer": results.get("answer", ""),
            "results": extracted,
        }

    except Exception as exc:
        return {
            "success": False,
            "error": normalize_api_error("tavily", exc),
            "answer": "",
            "results": [],
        }


def format_tavily_for_gpt(tavily_data: dict) -> str:
    """将 Tavily 搜索结果格式化为 GPT 可以理解的文本。"""
    if not tavily_data.get("success"):
        return "暂无竞品数据"

    lines = []
    if tavily_data.get("answer"):
        lines.append(f"搜索摘要：{tavily_data['answer']}")

    for i, result in enumerate(tavily_data.get("results", [])[:3], 1):
        content = result.get("content", "")
        if content:
            lines.append(f"参考{i}：{content[:300]}")

    return "\n".join(lines) if lines else "暂无竞品数据"
