import json
import os

import streamlit as st

from utils.env_loader import load_project_env
from utils.fragrance_rag import SUPPORTED_CATEGORIES
from utils.moneyprinter_turbo import (
    DEFAULT_MPT_BASE_URL,
    build_video_payload,
    check_moneyprinter_health,
    extract_task_id,
    query_video_task,
    submit_video_task,
)
from utils.v2_copilot import (
    AGE_RANGES,
    CONTENT_GOALS,
    detect_platform,
    extract_url_from_share_text,
    generate_marketing_plan,
    generate_product_profile,
    is_valid_url,
)


load_project_env()

st.set_page_config(
    page_title="ViralGen AI | Fragrance Concierge",
    page_icon="鈾笍",
    layout="wide",
)


PHASES = [
    ("Input", "输入", 0),
    ("Profile", "档案", 1),
    ("Confirm", "确认", 2),
    ("Plan", "方案", 3),
    ("Export", "导出", 4),
]

LANGUAGE_OPTIONS = {
    "中文": "zh",
    "English": "en",
}

TEXT = {
    "language_title": {"zh": "界面语言", "en": "Language"},
    "workspace": {"zh": "个人工作区", "en": "Personal"},
    "campaign_steps": {"zh": "项目流程", "en": "Campaign Steps"},
    "new_campaign": {"zh": "+ 新建项目", "en": "+ New Campaign"},
    "now": {"zh": "当前", "en": "NOW"},
    "done": {"zh": "完成", "en": "DONE"},
    "lock": {"zh": "锁定", "en": "LOCK"},
    "save_continue": {"zh": "保存并继续 →", "en": "Save & Continue →"},
    "save_draft": {"zh": "保存草稿", "en": "Save Draft"},
    "product_source": {"zh": "商品链接 / 1688 分享文本", "en": "Product Source URL / 1688 Share Text"},
    "product_source_placeholder": {
        "zh": "可以粘贴完整 1688 分享文本，例如：复制口令并打开手机阿里查看：https://qr.1688.com/s/...",
        "en": "Paste a clean product URL or full 1688 share text, e.g. copied token plus https://qr.1688.com/s/...",
    },
    "product_source_help": {
        "zh": "支持干净 URL，也支持 1688 / 淘宝 / 拼多多这类带口令的整段分享文本。",
        "en": "Supports clean URLs and full ecommerce share text with tokens from 1688, Taobao, or Pinduoduo.",
    },
    "detected_source": {"zh": "已识别来源", "en": "Detected source"},
    "detected_link": {"zh": "已提取链接", "en": "extracted link"},
    "invalid_link": {
        "zh": "没有识别到有效链接。可以直接粘贴完整分享文本，系统会自动提取 http/https 链接。",
        "en": "No valid link detected. Paste the full share text and the app will extract the http/https link automatically.",
    },
    "target_market": {"zh": "目标市场", "en": "Target Market"},
    "target_age": {"zh": "目标用户年龄", "en": "Target Audience Age"},
    "primary_goal": {"zh": "主要营销目标", "en": "Primary Marketing Objective"},
    "optional_image": {"zh": "可选产品图", "en": "Optional Product Image"},
    "optional_image_help": {
        "zh": "如果链接读取不完整，可以上传产品主图或包装图作为兜底。",
        "en": "Upload a product or packaging image if the URL cannot be read completely.",
    },
    "image_preview": {"zh": "产品图预览", "en": "Product image preview"},
    "input_card_title": {"zh": "定义产品参数", "en": "Define Product Parameters"},
    "input_card_desc": {
        "zh": "系统会自动提取香型、品牌信息和当前商品定位。",
        "en": "We'll automatically extract scent notes, brand identity, and current positioning.",
    },
    "strategy_insights": {"zh": "策略洞察", "en": "Strategy Insights"},
    "trending_title": {"zh": "趋势：美食调与琥珀调", "en": "Trending: Gourmand & Amber"},
    "trending_desc": {
        "zh": "近期内容里，香草、咖啡、零陵香豆、琥珀等温暖可食感香调，在 18-35 岁用户中更容易获得互动。",
        "en": "Recent analytics show stronger engagement for warm edible notes such as vanilla, coffee, tonka sugar, and amber bases, especially in the 18-35 audience.",
    },
    "good_title": {"zh": "适合：自然种草", "en": "Good: Natural Seeding"},
    "good_desc": {
        "zh": "自然种草更适合把香氛融入生活方式场景，而不是直接硬卖香调参数。",
        "en": "Natural seeding works best when the fragrance is integrated into a lifestyle aesthetic instead of hard-selling the scent notes.",
    },
    "top_categories": {"zh": "美国热门香调类型", "en": "Top Performing Categories (US)"},
    "woody_earthy": {"zh": "木质与泥土调", "en": "Woody & Earthy"},
    "fresh_citrus": {"zh": "清新与柑橘调", "en": "Fresh & Citrus"},
    "gourmand_amber": {"zh": "美食与琥珀调", "en": "Gourmand & Amber"},
    "download_full_plan": {"zh": "下载完整方案 TXT", "en": "Download Full Plan TXT"},
    "ready_post": {"zh": "可直接复制的英文发布内容", "en": "Ready-to-copy English Post"},
    "english_publish_content": {"zh": "英文发布内容", "en": "English publish content"},
    "profile_generated": {"zh": "产品档案已生成。", "en": "Product profile generated."},
    "review_confirm_profile": {"zh": "查看并确认产品档案", "en": "Review & Confirm Profile"},
    "product_intelligence": {"zh": "产品信息", "en": "Product Intelligence"},
    "marketing_attributes": {"zh": "营销属性", "en": "Marketing Attributes"},
    "field_name": {"zh": "名称", "en": "Name"},
    "field_type": {"zh": "类型", "en": "Type"},
    "field_category": {"zh": "品类判断", "en": "Category"},
    "field_fragrance": {"zh": "香型", "en": "Fragrance"},
    "field_material": {"zh": "材质", "en": "Material"},
    "field_spec": {"zh": "规格", "en": "Spec"},
    "field_price": {"zh": "价格", "en": "Price"},
    "field_packaging": {"zh": "包装", "en": "Packaging"},
    "field_visual_style": {"zh": "视觉风格", "en": "Visual Style"},
    "field_gift_suitable": {"zh": "适合送礼", "en": "Gift Suitable"},
    "field_tiktok_suitable": {"zh": "适合 TikTok", "en": "TikTok Suitable"},
    "field_customizable": {"zh": "支持定制", "en": "Customizable"},
    "use_scenes": {"zh": "使用场景", "en": "Use Scenes"},
    "recommended_directions": {"zh": "推荐营销方向", "en": "Recommended Marketing Directions"},
    "no_scene_data": {"zh": "暂无场景数据。", "en": "No scene data yet."},
    "no_direction_data": {"zh": "暂无营销方向数据。", "en": "No direction data yet."},
}

PHASE_TITLES = {
    0: {
        "zh": ("1. 产品输入", "配置香氛营销项目的基础信息。"),
        "en": ("1. Product Input", "Configure the base settings for your fragrance campaign."),
    },
    1: {
        "zh": ("2. 产品档案", "从商品链接中提取香型、品牌识别和当前定位。"),
        "en": ("2. Product Profile", "Extract scent notes, brand identity, and current positioning."),
    },
    2: {
        "zh": ("3. 确认档案", "在生成策略前，检查并修正产品信息。"),
        "en": ("3. Confirm Profile", "Review and refine the product intelligence before strategy generation."),
    },
    3: {
        "zh": ("4. 营销方案", "基于香氛知识库生成 TikTok 营销方案。"),
        "en": ("4. Marketing Plan", "Generate a TikTok-ready growth plan using fragrance-specific RAG."),
    },
    4: {
        "zh": ("5. 导出交付", "复制英文发布内容，或下载完整双语方案。"),
        "en": ("5. Export", "Copy English assets or download the full bilingual campaign brief."),
    },
}

COUNTRIES = {
    "United States (US)": "United States",
    "Canada (CA)": "Canada",
    "Mexico (MX)": "Mexico",
}

COUNTRY_LABELS = {
    "United States": {"zh": "美国 (US)", "en": "United States (US)"},
    "Canada": {"zh": "加拿大 (CA)", "en": "Canada (CA)"},
    "Mexico": {"zh": "墨西哥 (MX)", "en": "Mexico (MX)"},
}

GOAL_LABELS = {
    "natural_seeding": {"zh": "自然种草", "en": "Natural Seeding"},
    "shop_conversion": {"zh": "店铺转化", "en": "Shop Conversion"},
    "ai_video": {"zh": "AI 视频脚本", "en": "AI Video Script"},
    "gift_marketing": {"zh": "礼物营销", "en": "Gift Marketing"},
    "hook_testing": {"zh": "爆款 Hook 测试", "en": "Hook Testing"},
}

GOAL_HELP = {
    "natural_seeding": {
        "zh": "强调生活方式融入和审美氛围，适合做上层曝光和种草。",
        "en": "Organic identity integration and aesthetic focus. Best for top-of-funnel awareness.",
    },
    "shop_conversion": {
        "zh": "强调直接购买、明确 CTA、紧迫感和香型利益点，促进转化。",
        "en": "Direct sales and strong CTA focus. Emphasizes urgency and scent profile benefits.",
    },
    "ai_video": {
        "zh": "围绕趋势 Hook、视觉叙事和 AI 视频提示词生成内容。",
        "en": "Trend-aligned hook focus with visual storytelling and AI video prompts.",
    },
    "gift_marketing": {
        "zh": "围绕送礼场景、质感包装、节日节点和情绪价值展开。",
        "en": "Gift-scenario pain points, premium presentation, and seasonal hooks.",
    },
    "hook_testing": {
        "zh": "生成多组创意开头，用于快速测试 TikTok 爆款角度。",
        "en": "Multiple creative hook angles for fast TikTok testing.",
    },
}

GOAL_ICONS = {
    "natural_seeding": "◇",
    "shop_conversion": "▣",
    "ai_video": "▸",
    "gift_marketing": "✦",
    "hook_testing": "⚡",
}

def init_state():
    defaults = {
        "phase": 0,
        "product_url": "",
        "product_share_text": "",
        "target_country": "United States",
        "age_range": "18-35",
        "content_goal": "natural_seeding",
        "fallback_image": None,
        "product_profile_result": None,
        "product_profile": None,
        "marketing_plan_result": None,
        "ui_language": "zh",
        "moneyprinter_base_url": os.getenv("MONEYPRINTER_API_BASE_URL", DEFAULT_MPT_BASE_URL),
        "moneyprinter_payload": None,
        "moneyprinter_submit_result": None,
        "moneyprinter_task_id": "",
        "moneyprinter_task_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def current_language() -> str:
    return st.session_state.get("ui_language", "zh")


def t(key: str) -> str:
    return TEXT.get(key, {}).get(current_language(), TEXT.get(key, {}).get("en", key))


def phase_label(name_en: str, name_cn: str) -> str:
    return name_cn if current_language() == "zh" else name_en


def goal_label(key: str) -> str:
    return GOAL_LABELS[key][current_language()]


def goal_help(key: str) -> str:
    return GOAL_HELP[key][current_language()]


def country_label(country: str) -> str:
    return COUNTRY_LABELS.get(country, {}).get(current_language(), country)


def localize_value(value) -> str:
    if value is True:
        return "是" if current_language() == "zh" else "True"
    if value is False:
        return "否" if current_language() == "zh" else "False"
    if value is None or value == "":
        return "未识别" if current_language() == "zh" else "-"
    text = str(value)
    if current_language() != "zh":
        return text
    replacements = {
        "Supported": "支持",
        "Unsupported": "暂不支持",
        "Unknown": "未知",
        "Not specified": "未标明",
        "None": "无",
        "True": "是",
        "False": "否",
        "Bedroom": "卧室",
        "Living Room": "客厅",
        "Gift": "送礼",
    }
    return replacements.get(text, text)

def reset_workflow():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700&display=swap');

        :root {
            --vg-bg: #fbf9f2;
            --vg-sidebar: #f4f0e7;
            --vg-card: #fffdf8;
            --vg-card-soft: #f8f4ec;
            --vg-border: #e5dccd;
            --vg-border-strong: #b9d7ff;
            --vg-blue: #2f7df6;
            --vg-blue-soft: #e7f1ff;
            --vg-cyan: #67dff1;
            --vg-ink: #242322;
            --vg-muted: #91a0b6;
            --vg-muted-strong: #71819b;
            --vg-dark: #403d3a;
            --vg-code: #1d1e2a;
            --vg-green: #10b56f;
            --vg-danger: #e65858;
        }

        .stApp {
            background: var(--vg-bg);
            color: var(--vg-ink);
            font-family: Inter, sans-serif;
        }

        [data-testid="stHeader"], [data-testid="stToolbar"], footer, #MainMenu {
            display: none;
        }

        .block-container {
            max-width: 1320px;
            padding: 2.2rem 2.6rem 4rem;
        }

        [data-testid="stSidebar"] {
            background: var(--vg-sidebar);
            border-right: 1px solid var(--vg-border);
            box-shadow: 10px 0 34px rgba(36, 35, 34, .045);
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
            color: var(--vg-ink);
        }

        [data-testid="stSidebar"] h3 {
            font-size: 1.08rem !important;
            letter-spacing: -.025em;
            margin-top: 1.3rem !important;
            margin-bottom: .75rem !important;
        }

        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p {
            color: var(--vg-ink) !important;
            font-weight: 700;
        }

        [data-testid="stSidebar"] [role="radiogroup"] {
            gap: .85rem;
            padding: .25rem 0 .65rem;
        }

        [data-testid="stSidebar"] [role="radio"] {
            color: var(--vg-muted-strong) !important;
            font-weight: 750;
        }

        [data-testid="stSidebar"] [role="radio"][aria-checked="true"] {
            color: #0f2345 !important;
        }

        h1, h2, h3 {
            color: var(--vg-ink) !important;
            letter-spacing: -.04em;
        }

        h1 {
            font-size: clamp(2.15rem, 4vw, 3.6rem) !important;
            line-height: 1.04 !important;
            font-weight: 800 !important;
            margin-bottom: .35rem !important;
        }

        h2, h3 {
            font-weight: 800 !important;
        }

        label, p, span {
            color: var(--vg-ink);
        }

        .vg-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .vg-title-row {
            display: flex;
            flex-direction: column;
            gap: .3rem;
        }

        .vg-page-kicker {
            color: var(--vg-muted);
            font-size: .95rem;
        }

        .vg-search {
            min-width: 260px;
            padding: .85rem 1.1rem;
            border: 1px solid var(--vg-border);
            border-radius: 999px;
            color: var(--vg-muted);
            background: var(--vg-card);
            box-shadow: 0 18px 40px rgba(44, 43, 42, .06);
        }

        .vg-account {
            text-align: right;
            color: var(--vg-ink);
            font-weight: 800;
        }

        .vg-account small {
            display: block;
            color: var(--vg-blue);
            font-weight: 700;
        }

        [data-testid="stSidebar"] [data-testid="stImage"] {
            display: flex;
            justify-content: center;
            margin: 12px 0 0;
        }

        [data-testid="stSidebar"] [data-testid="stImage"] img {
            width: 80px !important;
            height: 80px !important;
            object-fit: contain;
        }

        .vg-logo-sub {
            color: var(--vg-muted);
            font-size: 14px;
            line-height: 1.25;
            margin-top: 8px;
            text-align: center;
        }

        .vg-sidebar-link {
            display: flex;
            align-items: center;
            gap: .75rem;
            padding: .95rem 1rem;
            border-radius: 999px;
            color: var(--vg-muted);
            margin: .45rem 0;
            border: 1px solid transparent;
        }

        .vg-sidebar-link.active {
            color: #192349;
            background: #eaf3ff;
            border: 1px solid #c7ddfb;
        }

        [data-testid="stSidebar"] .stButton button {
            border-radius: 999px;
            min-height: 3.65rem;
            justify-content: center;
            background: transparent;
            color: var(--vg-muted);
            border: 1px solid transparent;
            font-weight: 760;
            font-size: .98rem;
            letter-spacing: -.01em;
        }

        [data-testid="stSidebar"] .stButton button[kind="primary"] {
            background: var(--vg-blue-soft);
            color: #0f2345;
            border: 1px solid var(--vg-border-strong);
            box-shadow: inset 0 0 0 1px rgba(255,255,255,.58), 0 14px 30px rgba(47, 125, 246, .09);
        }

        [data-testid="stSidebar"] .stButton button:hover:not(:disabled) {
            color: #0f2345;
            background: #edf5ff;
            border-color: #c8ddfb;
        }

        [data-testid="stSidebar"] .stButton button:disabled {
            opacity: 1;
            color: #a8b2c1;
            background: transparent;
            border-color: transparent;
        }

        .vg-pro-card {
            padding: 1.15rem 1.25rem;
            border: 1px solid var(--vg-border);
            border-radius: 17px;
            background: var(--vg-card);
            margin-top: 2rem;
            box-shadow: 0 18px 38px rgba(36, 35, 34, .07);
        }

        .vg-progress {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: .35rem;
            padding: 1.5rem 1.65rem;
            border: 1px solid var(--vg-border);
            border-radius: 18px;
            background: var(--vg-card);
            box-shadow: 0 18px 42px rgba(44, 43, 42, .06);
            margin-bottom: 1rem;
        }

        .vg-step {
            position: relative;
            text-align: center;
            color: var(--vg-muted);
        }

        .vg-step:not(:last-child)::after {
            content: "";
            position: absolute;
            top: 20px;
            left: calc(50% + 27px);
            width: calc(100% - 54px);
            height: 1px;
            background: #e1d8c8;
        }

        .vg-step-num {
            width: 42px;
            height: 42px;
            display: grid;
            place-items: center;
            margin: 0 auto .55rem;
            border-radius: 50%;
            border: 1px solid var(--vg-border);
            background: #f6f1e8;
            color: var(--vg-ink);
            font-weight: 800;
        }

        .vg-step.active .vg-step-num,
        .vg-step.done .vg-step-num {
            color: #ffffff;
            border-color: #2f7df6;
            background: #3d9df5;
            box-shadow: 0 0 0 5px rgba(61, 157, 245, .16);
        }

        .vg-step-label {
            font-size: .82rem;
            color: var(--vg-muted-strong);
            font-weight: 550;
        }

        .vg-card {
            border: 1px solid var(--vg-border);
            border-radius: 18px;
            background: var(--vg-card);
            box-shadow: 0 18px 44px rgba(36, 35, 34, .06);
            padding: 1.55rem;
        }

        .vg-card h3 {
            margin-top: 0 !important;
        }

        .vg-panel-title {
            display: flex;
            gap: .8rem;
            align-items: flex-start;
            margin-bottom: .45rem;
        }

        .vg-panel-title h3 {
            margin: 0 !important;
            font-size: 1.15rem !important;
            line-height: 1.2 !important;
            letter-spacing: 0 !important;
            white-space: normal;
            word-break: keep-all;
        }

        .vg-panel-title .vg-muted {
            margin: .32rem 0 0;
            font-size: .92rem;
            line-height: 1.5;
            white-space: normal;
        }

        .vg-icon-badge {
            width: 42px;
            height: 42px;
            display: grid;
            place-items: center;
            border-radius: 50%;
            color: #2f7df6;
            background: #edf5ff;
            border: 1px solid #d2e5ff;
        }

        .vg-muted {
            color: var(--vg-muted);
        }

        .vg-metric {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            padding: .7rem 0;
            border-bottom: 1px solid var(--vg-border);
        }

        .vg-bar {
            width: 72px;
            height: 5px;
            border-radius: 999px;
            background: #e1dfd6;
            overflow: hidden;
        }

        .vg-bar > span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #62dbea, #2f7df6);
        }

        .vg-pill {
            display: inline-block;
            margin: .22rem .32rem .22rem 0;
            padding: .38rem .62rem;
            border-radius: 999px;
            color: #2772e7;
            border: 1px solid #cfe4ff;
            background: #eef6ff;
            font-family: "JetBrains Mono", monospace;
            font-size: .78rem;
        }

        .vg-objective-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .9rem;
            margin-top: .8rem;
        }

        .vg-objective {
            min-height: 122px;
            padding: 1.05rem;
            border: 1px solid var(--vg-border);
            border-radius: 16px;
            background: var(--vg-card);
            box-shadow: 0 12px 26px rgba(36, 35, 34, .035);
        }

        .vg-objective.active {
            border-color: #b9d7ff;
            background: var(--vg-blue-soft);
            box-shadow: inset 0 0 0 1px rgba(255,255,255,.65), 0 16px 32px rgba(47, 125, 246, .08);
        }

        .vg-objective-title {
            color: var(--vg-ink);
            font-weight: 800;
            margin-bottom: .35rem;
        }

        .vg-objective-desc {
            color: var(--vg-muted);
            font-size: .92rem;
            line-height: 1.5;
        }

        .stTextInput input,
        .stTextArea textarea,
        [data-baseweb="select"] > div {
            background: var(--vg-card) !important;
            border-color: #ded7ca !important;
            color: var(--vg-ink) !important;
            border-radius: 14px !important;
            box-shadow: none !important;
        }

        .stTextInput input:focus,
        .stTextArea textarea:focus {
            border-color: #a7cbfb !important;
            box-shadow: 0 0 0 4px rgba(47, 125, 246, .09) !important;
        }

        .stButton button {
            border-radius: 999px;
            min-height: 3rem;
            font-weight: 800;
        }

        .stButton button[kind="primary"] {
            background: var(--vg-dark);
            color: #fff !important;
            border: 0;
        }

        .stButton button[kind="primary"] p,
        .stButton button[kind="primary"] span {
            color: #fff !important;
        }

        [data-testid="stSidebar"] .stButton button,
        [data-testid="stSidebar"] .stButton button p,
        [data-testid="stSidebar"] .stButton button span {
            color: #111111 !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: .35rem;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            padding: .55rem 1rem;
            color: var(--vg-muted);
        }

        .stTabs [aria-selected="true"] {
            background: #f2fbfd;
            color: #37cce5;
        }

        @media (max-width: 900px) {
            .vg-topbar {
                flex-direction: column;
                align-items: flex-start;
            }

            .vg-progress,
            .vg-objective-grid {
                grid-template-columns: 1fr;
            }

            .vg-step:not(:last-child)::after {
                display: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    file_button_label = "涓婁紶" if current_language() == "zh" else "Upload"
    file_limit_label = (
        "鍗曚釜鏂囦欢鏈€澶?200MB 路 鏀寔 JPG銆丳NG銆乄EBP"
        if current_language() == "zh"
        else "200MB per file 鈥?JPG, PNG, WEBP"
    )
    st.markdown(
        f"""
        <style>
        [data-testid="stFileUploaderDropzone"] button {{
            font-size: 0 !important;
        }}
        [data-testid="stFileUploaderDropzone"] button::after {{
            content: "{file_button_label}";
            font-size: .92rem !important;
        }}
        [data-testid="stFileUploaderDropzone"] small {{
            font-size: 0 !important;
        }}
        [data-testid="stFileUploaderDropzone"] small::after {{
            content: "{file_limit_label}";
            font-size: .92rem !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def target_persona_text() -> str:
    return f"Women {st.session_state.age_range}, North America home fragrance buyers"


def can_visit(phase: int) -> bool:
    if phase == 0:
        return True
    if phase == 1:
        return bool(st.session_state.product_url and is_valid_url(st.session_state.product_url))
    if phase == 2:
        return bool(st.session_state.product_profile)
    if phase in {3, 4}:
        return bool(
            st.session_state.marketing_plan_result
            and st.session_state.marketing_plan_result.get("success")
        )
    return False


def current_phase_title() -> tuple[str, str]:
    return PHASE_TITLES[st.session_state.phase][current_language()]


def render_sidebar():
    with st.sidebar:
        st.image("assets/viralgen_logo.svg", width=80)
        st.markdown('<div class="vg-logo-sub">Fragrance Copilot</div>', unsafe_allow_html=True)

        st.markdown(
            """
            <div class="vg-pro-card" style="margin-top:.2rem;margin-bottom:1.4rem;">
              <b style="color:#2f7df6;">{workspace}</b>
              <span style="float:right;color:#8c9ab0;">⌄</span>
            </div>
            """.format(workspace=t("workspace")),
            unsafe_allow_html=True,
        )

        selected_language = st.radio(
            t("language_title"),
            options=list(LANGUAGE_OPTIONS.keys()),
            index=list(LANGUAGE_OPTIONS.values()).index(current_language()),
            horizontal=True,
        )
        new_language = LANGUAGE_OPTIONS[selected_language]
        if new_language != current_language():
            st.session_state.ui_language = new_language
            st.rerun()

        st.markdown("### " + t("campaign_steps"))
        for name_en, name_cn, phase_id in PHASES:
            active = st.session_state.phase == phase_id
            done = st.session_state.phase > phase_id
            status = t("now") if active else t("done") if done else t("lock")
            label = f"{status}  {phase_label(name_en, name_cn)}"
            if st.button(
                label,
                key=f"nav_{phase_id}",
                type="primary" if active else "secondary",
                disabled=not can_visit(phase_id) and phase_id > st.session_state.phase,
                use_container_width=True,
            ):
                st.session_state.phase = phase_id
                st.rerun()

        if st.button(t("new_campaign"), type="primary", use_container_width=True):
            reset_workflow()


def render_header():
    title, subtitle = current_phase_title()
    st.markdown(
        f"""
        <div class="vg-topbar">
          <div class="vg-title-row">
            <h1>{title}</h1>
            <div class="vg-page-kicker">{subtitle}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_progress()


def render_progress():
    steps = []
    for index, (name_en, name_cn, phase_id) in enumerate(PHASES, start=1):
        state = "active" if st.session_state.phase == phase_id else "done" if st.session_state.phase > phase_id else ""
        steps.append(
            f'<div class="vg-step {state}">'
            f'<div class="vg-step-num">{index}</div>'
            f'<div class="vg-step-label">{phase_label(name_en, name_cn)}</div>'
            f'</div>'
        )
    st.html(f'<div class="vg-progress">{"".join(steps)}</div>')


def render_strategy_insights():
    st.html(
        f"""
        <div class="vg-card">
          <div class="vg-panel-title">
            <div class="vg-icon-badge">✓</div>
            <h3>{t("strategy_insights")}</h3>
          </div>
          <div class="vg-card" style="box-shadow:none;margin-top:1rem;">
            <b style="color:#2f7df6;">→ {t("trending_title")}</b>
            <p class="vg-muted">{t("trending_desc")}</p>
            <hr style="border-color:#e8e0d2;">
            <b style="color:#10b56f;">● {t("good_title")}</b>
            <p class="vg-muted">{t("good_desc")}</p>
          </div>
          <h4>{t("top_categories")}</h4>
          <div class="vg-metric"><span>{t("woody_earthy")}</span><span><div class="vg-bar"><span style="width:85%"></span></div></span><b>85%</b></div>
          <div class="vg-metric"><span>{t("fresh_citrus")}</span><span><div class="vg-bar"><span style="width:63%"></span></div></span><b>63%</b></div>
          <div class="vg-metric"><span>{t("gourmand_amber")}</span><span><div class="vg-bar"><span style="width:42%"></span></div></span><b>42%</b></div>
        </div>
        """
    )


def render_input_phase():
    left, right = st.columns([2.1, 1], gap="large")
    with left:
        st.html(
            f"""
            <div class="vg-card">
              <div class="vg-panel-title">
                <div class="vg-icon-badge">▣</div>
                <div>
                  <h3>{t("input_card_title")}</h3>
                  <p class="vg-muted">{t("input_card_desc")}</p>
                </div>
              </div>
            </div>
            """
        )

        share_text = st.text_area(
            t("product_source"),
            value=st.session_state.product_share_text or st.session_state.product_url,
            placeholder=t("product_source_placeholder"),
            help=t("product_source_help"),
            height=110,
        ).strip()
        st.session_state.product_share_text = share_text
        product_url = extract_url_from_share_text(share_text)
        st.session_state.product_url = product_url

        if share_text:
            if is_valid_url(product_url):
                st.success(
                    f"{t('detected_source')}: {detect_platform(product_url)} 路 "
                    f"{t('detected_link')}: {product_url}"
                )
            else:
                st.error(t("invalid_link"))

        col1, col2 = st.columns(2)
        with col1:
            country_values = list(COUNTRY_LABELS.keys())
            selected_country = st.selectbox(
                t("target_market"),
                options=country_values,
                index=country_values.index(st.session_state.target_country),
                format_func=country_label,
            )
            st.session_state.target_country = selected_country
        with col2:
            st.session_state.age_range = st.selectbox(
                t("target_age"),
                options=AGE_RANGES,
                index=AGE_RANGES.index(st.session_state.age_range),
            )

        st.markdown("#### " + t("primary_goal"))
        goal_keys = list(CONTENT_GOALS.keys())
        selected_goal = st.radio(
            t("primary_goal"),
            options=goal_keys,
            format_func=goal_label,
            index=goal_keys.index(st.session_state.content_goal),
            horizontal=True,
            label_visibility="collapsed",
        )
        st.session_state.content_goal = selected_goal

        objective_cards = []
        for key in ["natural_seeding", "shop_conversion", "ai_video", "gift_marketing"]:
            active = "active" if st.session_state.content_goal == key else ""
            objective_cards.append(
                f'<div class="vg-objective {active}">'
                f'<div class="vg-objective-title">{GOAL_ICONS[key]} &nbsp; {goal_label(key)}</div>'
                f'<div class="vg-objective-desc">{goal_help(key)}</div>'
                f'</div>'
            )
        st.html(f'<div class="vg-objective-grid">{"".join(objective_cards)}</div>')

        st.markdown("#### " + t("optional_image"))
        fallback_image = st.file_uploader(
            t("optional_image_help"),
            type=["jpg", "jpeg", "png", "webp"],
        )
        if fallback_image is not None:
            st.session_state.fallback_image = fallback_image
            st.image(fallback_image, caption=t("image_preview"), width=260)

        can_start = bool(product_url and is_valid_url(product_url))
        cta_col, draft_col = st.columns([1.2, 1])
        with cta_col:
            if st.button(t("save_continue"), type="primary", disabled=not can_start, use_container_width=True):
                st.session_state.product_profile_result = None
                st.session_state.product_profile = None
                st.session_state.marketing_plan_result = None
                st.session_state.phase = 1
                st.rerun()
        with draft_col:
            st.caption(t("save_draft"))

    with right:
        render_strategy_insights()


def render_profile_generation_phase():
    if st.session_state.product_profile_result is None:
        with st.spinner("Reading product page and generating product profile..."):
            result = generate_product_profile(
                product_url=st.session_state.product_url,
                target_country=st.session_state.target_country,
                target_persona=target_persona_text(),
                content_goal=CONTENT_GOALS[st.session_state.content_goal],
                uploaded_image=st.session_state.fallback_image,
                source_hint_text=st.session_state.product_share_text,
            )
            st.session_state.product_profile_result = result
            if result.get("success"):
                st.session_state.product_profile = result["data"]

    result = st.session_state.product_profile_result
    if not result.get("success"):
        st.error(result.get("error", "产品档案生成失败" if current_language() == "zh" else "Product profile generation failed"))
        debug = result.get("debug") or {}
        if debug:
            title = "查看链接读取诊断" if current_language() == "zh" else "View link extraction diagnostics"
            with st.expander(title, expanded=True):
                platform_label = "平台识别" if current_language() == "zh" else "Detected platform"
                length_label = "抓取文本长度" if current_language() == "zh" else "Fetched text length"
                preview_label = "抓取内容预览" if current_language() == "zh" else "Fetched content preview"
                st.write(f"{platform_label}: {debug.get('platform', '-')}")
                st.write(f"{length_label}: {debug.get('text_length', '-')}")
                if debug.get("extract_error"):
                    st.caption(debug.get("extract_error"))
                if debug.get("content_preview"):
                    st.text_area(preview_label, debug.get("content_preview", ""), height=140)
                st.info(
                    "建议：1688 链接经常需要登录或动态加载。请上传产品主图/包装图作为兜底，"
                    "或者换成 Alibaba / Amazon / 独立站等公开页面链接。"
                    if current_language() == "zh"
                    else "Tip: 1688 links often require login or dynamic loading. Upload a product/packaging image as fallback, or use a public Alibaba, Amazon, or brand site URL."
                )
        col1, col2 = st.columns(2)
        with col1:
            back_label = "返回输入" if current_language() == "zh" else "Back to Input"
            if st.button(back_label, use_container_width=True):
                st.session_state.phase = 0
                st.rerun()
        with col2:
            retry_label = "重试提取" if current_language() == "zh" else "Retry Extraction"
            if st.button(retry_label, type="primary", use_container_width=True):
                st.session_state.product_profile_result = None
                st.rerun()
        return

    st.success(t("profile_generated"))
    render_profile_cards(st.session_state.product_profile)
    if st.button(t("review_confirm_profile"), type="primary", use_container_width=True):
        st.session_state.phase = 2
        st.rerun()


def render_profile_cards(profile: dict):
    name = profile.get("product_name", {})
    judgment = profile.get("product_type_judgment", {})
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown(
            f"""
            <div class="vg-card">
              <h3>{t("product_intelligence")}</h3>
              <p><b>{t("field_name")}:</b> {localize_value(name.get('chinese'))} / {localize_value(name.get('english'))}</p>
              <p><b>{t("field_type")}:</b> {localize_value(profile.get('product_type'))}</p>
              <p><b>{t("field_category")}:</b> {localize_value(judgment.get('result'))}</p>
              <p><b>{t("field_fragrance")}:</b> {localize_value(profile.get('fragrance'))}</p>
              <p><b>{t("field_material")}:</b> {localize_value(profile.get('material'))}</p>
              <p><b>{t("field_spec")}:</b> {localize_value(profile.get('volume_spec'))}</p>
              <p><b>{t("field_price")}:</b> {localize_value(profile.get('price_range'))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="vg-card">
              <h3>{t("marketing_attributes")}</h3>
              <p><b>{t("field_packaging")}:</b> {localize_value(profile.get('packaging'))}</p>
              <p><b>{t("field_visual_style")}:</b> {localize_value(profile.get('visual_style'))}</p>
              <p><b>{t("field_gift_suitable")}:</b> {localize_value(profile.get('gift_suitable'))}</p>
              <p><b>{t("field_tiktok_suitable")}:</b> {localize_value(profile.get('tiktok_suitable'))}</p>
              <p><b>{t("field_customizable")}:</b> {localize_value(profile.get('customizable'))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("#### " + t("use_scenes"))
    scenes = profile.get("use_scenes") or []
    if scenes:
        st.html(" ".join(f"<span class='vg-pill'>{localize_value(scene)}</span>" for scene in scenes))
    else:
        st.caption(t("no_scene_data"))

    st.markdown("#### " + t("recommended_directions"))
    directions = profile.get("marketing_directions") or []
    if directions:
        for item in directions:
            st.markdown(f"- {item}")
    else:
        st.caption(t("no_direction_data"))


def render_confirm_phase():
    profile = st.session_state.product_profile
    if not profile:
        st.warning("请先生成产品档案。" if current_language() == "zh" else "Please generate a product profile first.")
        return

    zh = current_language() == "zh"
    render_profile_cards(profile)
    st.markdown("### " + ("编辑关键字段" if zh else "Edit Key Fields"))
    with st.form("profile_edit_form"):
        name = profile.get("product_name", {})
        col1, col2 = st.columns(2)
        with col1:
            name_cn = st.text_input("产品名称（中文）" if zh else "Product Name (Chinese)", value=name.get("chinese", ""))
            product_type = st.text_input("产品类型 / 品类判断" if zh else "Product Type / Category", value=profile.get("product_type", ""))
            fragrance = st.text_input("香味信息" if zh else "Fragrance", value=profile.get("fragrance", ""))
            material = st.text_input("材质信息" if zh else "Material", value=profile.get("material", ""))
        with col2:
            name_en = st.text_input("产品名称（英文）" if zh else "Product Name (English)", value=name.get("english", ""))
            volume_spec = st.text_input("容量或规格" if zh else "Volume / Spec", value=profile.get("volume_spec", ""))
            packaging = st.text_input("包装形式" if zh else "Packaging", value=profile.get("packaging", ""))
            visual_style = st.text_input("视觉风格" if zh else "Visual Style", value=profile.get("visual_style", ""))

        submitted = st.form_submit_button("保存修改" if zh else "Save Changes", use_container_width=True)
        if submitted:
            profile["product_name"] = {"chinese": name_cn, "english": name_en}
            profile["product_type"] = product_type
            profile.setdefault("product_type_judgment", {})["result"] = product_type
            profile["fragrance"] = fragrance
            profile["material"] = material
            profile["volume_spec"] = volume_spec
            profile["packaging"] = packaging
            profile["visual_style"] = visual_style
            st.session_state.product_profile = profile
            st.success("已保存。" if zh else "Saved.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("生成营销方案" if zh else "Generate Marketing Plan", type="primary", use_container_width=True):
            st.session_state.marketing_plan_result = None
            st.session_state.phase = 3
            st.rerun()
    with col2:
        if st.button("重新读取商品链接" if zh else "Re-read Product URL", use_container_width=True):
            st.session_state.product_profile_result = None
            st.session_state.product_profile = None
            st.session_state.phase = 1
            st.rerun()

def render_plan_phase():
    if st.session_state.marketing_plan_result is None:
        spinner_text = (
            "正在调用香氛知识库并生成 TikTok 营销方案..."
            if current_language() == "zh"
            else "Calling fragrance knowledge base and generating TikTok campaign plan..."
        )
        with st.spinner(spinner_text):
            st.session_state.marketing_plan_result = generate_marketing_plan(
                product_profile=st.session_state.product_profile,
                target_country=st.session_state.target_country,
                target_persona=target_persona_text(),
                content_goal=CONTENT_GOALS[st.session_state.content_goal],
            )

    result = st.session_state.marketing_plan_result
    if not result.get("success"):
        fallback_error = "营销方案生成失败" if current_language() == "zh" else "Marketing plan generation failed"
        back_label = "返回产品档案" if current_language() == "zh" else "Back to Product Profile"
        st.error(result.get("error", fallback_error))
        if st.button(back_label, type="primary", use_container_width=True):
            st.session_state.phase = 2
            st.rerun()
        return

    st.success("营销方案已生成。" if current_language() == "zh" else "Marketing plan generated.")
    render_plan_tabs(result["data"])
    export_label = "前往导出" if current_language() == "zh" else "Go to Export"
    if st.button(export_label, type="primary", use_container_width=True):
        st.session_state.phase = 4
        st.rerun()


def bilingual_list(items):
    if not items:
        st.caption("暂无数据。" if current_language() == "zh" else "No data yet.")
        return
    for item in items:
        if isinstance(item, dict):
            st.markdown(f"- **EN:** {item.get('english', item.get('reply', ''))}")
            st.caption(f"CN: {item.get('chinese', item.get('question', ''))}")
        else:
            st.markdown(f"- {item}")


def render_plan_tabs(plan: dict):
    zh = current_language() == "zh"
    tabs = st.tabs(
        ["方案摘要", "痛点与卖点", "Hooks", "视频脚本", "发布文案", "评论与卖点"]
        if zh
        else ["Summary", "Pain & Selling", "Hooks", "Video", "Caption", "Replies & Listing"]
    )

    with tabs[0]:
        st.markdown("### " + ("产品摘要" if zh else "Product Summary"))
        st.info(plan.get("product_summary", {}).get("chinese", ""))
        st.success(plan.get("product_summary", {}).get("english", ""))
        st.markdown("### " + ("产品类型判断" if zh else "Product Type Judgment"))
        st.info(plan.get("product_type_judgment", {}).get("chinese", ""))
        st.success(plan.get("product_type_judgment", {}).get("english", ""))
        st.markdown("### " + ("推荐营销方向" if zh else "Recommended Directions"))
        bilingual_list(plan.get("recommended_directions", []))

    with tabs[1]:
        st.markdown("### " + ("用户痛点" if zh else "User Pain Points"))
        bilingual_list(plan.get("user_pain_points", []))
        st.markdown("### " + ("TikTok 卖点" if zh else "TikTok Selling Points"))
        bilingual_list(plan.get("tiktok_selling_points", []))

    with tabs[2]:
        st.markdown("### " + ("内容角度" if zh else "Content Angles"))
        bilingual_list(plan.get("content_angles", []))
        st.markdown("### " + ("爆款 Hooks" if zh else "Viral Hooks"))
        bilingual_list(plan.get("hooks", []))

    with tabs[3]:
        st.markdown("### " + ("视频脚本" if zh else "Video Script"))
        st.text_area("中文脚本" if zh else "Chinese Script", plan.get("video_script", {}).get("chinese", ""), height=180)
        st.text_area("英文脚本" if zh else "English Script", plan.get("video_script", {}).get("english", ""), height=180)
        st.markdown("### " + ("AI 视频提示词" if zh else "AI Video Prompt"))
        st.text_area("中文提示词" if zh else "Chinese Prompt", plan.get("ai_video_prompt", {}).get("chinese", ""), height=130)
        st.text_area("英文提示词" if zh else "English Prompt", plan.get("ai_video_prompt", {}).get("english", ""), height=130)

    with tabs[4]:
        st.markdown("### " + ("TikTok 发布文案" if zh else "TikTok Caption"))
        st.text_area("中文文案" if zh else "Chinese Caption", plan.get("tiktok_caption", {}).get("chinese", ""), height=140)
        st.text_area("英文文案" if zh else "English Caption", plan.get("tiktok_caption", {}).get("english", ""), height=140)
        st.markdown("### " + ("话题标签" if zh else "Hashtags"))
        st.code(" ".join(plan.get("hashtags", [])))

    with tabs[5]:
        st.markdown("### " + ("评论回复" if zh else "Comment Replies"))
        replies = plan.get("comment_replies", [])
        for item in replies:
            st.markdown(f"- **Q:** {item.get('question', '')}")
            st.caption(f"A: {item.get('reply', '')}")
        st.markdown("### " + ("商品页卖点" if zh else "Listing Selling Points"))
        bilingual_list(plan.get("listing_selling_points", []))

def build_export_text() -> str:
    payload = {
        "product_url": st.session_state.product_url,
        "target_country": st.session_state.target_country,
        "target_persona": target_persona_text(),
        "content_goal": CONTENT_GOALS[st.session_state.content_goal],
        "product_profile": st.session_state.product_profile,
        "marketing_plan": st.session_state.marketing_plan_result.get("data", {}),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_export_phase():
    result = st.session_state.marketing_plan_result
    if not result or not result.get("success"):
        st.warning("Please generate a marketing plan first.")
        return

    plan = result["data"]
    render_plan_tabs(plan)
    export_text = build_export_text()
    st.download_button(
        t("download_full_plan"),
        data=export_text.encode("utf-8"),
        file_name="viralgen_home_fragrance_plan.txt",
        mime="text/plain",
        use_container_width=True,
    )

    english_caption = result["data"].get("tiktok_caption", {}).get("english", "")
    hashtags = " ".join(result["data"].get("hashtags", []))
    st.markdown("### " + t("ready_post"))
    st.text_area(t("english_publish_content"), f"{english_caption}\n\n{hashtags}", height=180)

    render_moneyprinter_export(plan)


def render_moneyprinter_export(plan: dict):
    st.markdown("---")
    st.markdown("### MoneyPrinterTurbo Video Engine")
    st.caption(
        "Use MoneyPrinterTurbo as the downstream video factory: ViralGen provides product intelligence, "
        "script, caption and visual direction; MoneyPrinterTurbo generates the 9:16 short video."
    )

    col1, col2 = st.columns([1.4, 1])
    with col1:
        base_url = st.text_input(
            "MoneyPrinterTurbo API Base URL",
            value=st.session_state.moneyprinter_base_url,
            help="Start MoneyPrinterTurbo API locally, then keep this as http://127.0.0.1:8080 unless you changed its port.",
        ).strip()
        st.session_state.moneyprinter_base_url = base_url or DEFAULT_MPT_BASE_URL

    with col2:
        if st.button("Check API Connection", use_container_width=True):
            st.session_state.moneyprinter_task_result = check_moneyprinter_health(
                st.session_state.moneyprinter_base_url
            )

    health = st.session_state.moneyprinter_task_result
    if health:
        if health.get("success"):
            st.success(f"MoneyPrinterTurbo API reachable: {health.get('url')}")
        else:
            st.warning(
                "MoneyPrinterTurbo API is not reachable yet. Start its API service first, "
                f"then retry. Detail: {health.get('error')}"
            )

    profile = st.session_state.product_profile or {}
    product_name = profile.get("product_name", {}) if profile else {}
    default_subject = product_name.get("english") or profile.get("product_type") or "home fragrance TikTok video"
    default_terms = (plan.get("ai_video_prompt") or {}).get("english", "") or default_subject

    control_col1, control_col2, control_col3 = st.columns([1.2, 1.2, 0.8])
    with control_col1:
        video_subject = st.text_input("Video Subject", value=default_subject)
    with control_col2:
        video_terms = st.text_input("Search / Visual Terms", value=default_terms[:180])
    with control_col3:
        video_count = st.number_input("Videos", min_value=1, max_value=5, value=1, step=1)

    option_col1, option_col2 = st.columns(2)
    with option_col1:
        video_source = st.selectbox(
            "Material Source",
            options=["pexels", "pixabay", "local"],
            index=0,
            help="Use pexels/pixabay if MoneyPrinterTurbo is configured with those API keys. Use local if you prepare local assets there.",
        )
    with option_col2:
        voice_name = st.text_input(
            "Voice Name",
            value="",
            placeholder="Optional, leave blank to use MoneyPrinterTurbo default",
        )

    payload = build_video_payload(
        marketing_plan=plan,
        product_profile=profile,
        target_country=st.session_state.target_country,
        video_subject=video_subject,
        video_terms=video_terms,
        video_source=video_source,
        video_count=int(video_count),
        voice_name=voice_name,
    )
    st.session_state.moneyprinter_payload = payload

    with st.expander("Preview MoneyPrinterTurbo API Payload", expanded=False):
        st.json(payload)

    submit_col, task_col, refresh_col = st.columns([1, 1, 1])
    with submit_col:
        if st.button("Send to MoneyPrinterTurbo", type="primary", use_container_width=True):
            submit_result = submit_video_task(payload, st.session_state.moneyprinter_base_url)
            st.session_state.moneyprinter_submit_result = submit_result
            if submit_result.get("success"):
                st.session_state.moneyprinter_task_id = extract_task_id(submit_result.get("data"))
            st.rerun()

    with task_col:
        task_id = st.text_input(
            "Task ID",
            value=st.session_state.moneyprinter_task_id,
            placeholder="Auto-filled after submit",
        ).strip()
        st.session_state.moneyprinter_task_id = task_id

    with refresh_col:
        if st.button("Query Task Status", use_container_width=True, disabled=not st.session_state.moneyprinter_task_id):
            st.session_state.moneyprinter_task_result = query_video_task(
                st.session_state.moneyprinter_task_id,
                st.session_state.moneyprinter_base_url,
            )
            st.rerun()

    submit_result = st.session_state.moneyprinter_submit_result
    if submit_result:
        if submit_result.get("success"):
            st.success("Video task submitted to MoneyPrinterTurbo.")
            st.json(submit_result.get("data"))
        else:
            st.error(f"Submit failed: {submit_result.get('error')}")

    task_result = st.session_state.moneyprinter_task_result
    if task_result and "data" in task_result:
        if task_result.get("success"):
            st.info("Latest MoneyPrinterTurbo task response:")
            st.json(task_result.get("data"))
        elif task_result.get("error"):
            st.warning(f"Task query failed: {task_result.get('error')}")


init_state()
inject_css()
render_sidebar()
render_header()

if st.session_state.phase == 0:
    render_input_phase()
elif st.session_state.phase == 1:
    render_profile_generation_phase()
elif st.session_state.phase == 2:
    render_confirm_phase()
elif st.session_state.phase == 3:
    render_plan_phase()
elif st.session_state.phase == 4:
    render_export_phase()





