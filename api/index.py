from pathlib import Path

from flask import Flask, jsonify, request

from utils.v2_copilot import (
    CONTENT_GOALS,
    extract_url_from_share_text,
    generate_marketing_plan,
    generate_product_profile,
    is_valid_url,
)


app = Flask(__name__)


@app.get("/")
def home():
    return (Path(__file__).with_name("index.html")).read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/profile")
def create_profile():
    payload = request.get_json(silent=True) or {}
    source = str(payload.get("source", ""))
    product_url = extract_url_from_share_text(source)
    if not is_valid_url(product_url):
        return jsonify({"detail": "没有识别到有效的商品链接。"}), 400

    result = generate_product_profile(
        product_url=product_url,
        target_country=payload.get("country", "United States"),
        target_persona=f"Age {payload.get('age_range', '18-35')}",
        content_goal=CONTENT_GOALS.get(payload.get("goal"), CONTENT_GOALS["natural_seeding"]),
        source_hint_text=source,
    )
    if not result.get("success"):
        return jsonify({"detail": result.get("error", "产品档案生成失败")}), 422
    return jsonify(result["data"])


@app.post("/api/plan")
def create_plan():
    payload = request.get_json(silent=True) or {}
    result = generate_marketing_plan(
        product_profile=payload.get("profile") or {},
        target_country=payload.get("country", "United States"),
        target_persona=f"Age {payload.get('age_range', '18-35')}",
        content_goal=CONTENT_GOALS.get(payload.get("goal"), CONTENT_GOALS["natural_seeding"]),
    )
    if not result.get("success"):
        return jsonify({"detail": result.get("error", "营销方案生成失败")}), 422
    return jsonify(result["data"])


@app.get("/api/export")
def export_example():
    return jsonify({"message": "Use the download button in the workspace."})
