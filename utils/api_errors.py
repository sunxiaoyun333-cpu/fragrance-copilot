def normalize_api_error(provider: str, error: Exception) -> str:
    """将底层 API 异常转换为更友好的提示。"""
    message = str(error)
    lowered = message.lower()

    if "invalid_api_key" in lowered or "incorrect api key" in lowered:
        return f"{provider.upper()} API Key 无效，请检查 .env 或系统环境变量中的配置。"

    if "api_key" in lowered and "not set" in lowered:
        return f"{provider.upper()} API Key 未设置，请检查 .env 文件。"

    if "401" in lowered and "unauthorized" in lowered:
        return f"{provider.upper()} 鉴权失败，请确认 API Key 是否正确。"

    if "429" in lowered or "rate limit" in lowered:
        return f"{provider.upper()} 请求过于频繁，请稍后重试。"

    if "does not exist" in lowered and "model" in lowered:
        return (
            f"{provider.upper()} 当前图片模型不可用。请确认 API Key 是否有图片生成权限，"
            "或在 .env 中设置 OPENAI_IMAGE_MODEL=gpt-image-1。"
        )

    if "image_generation_user_error" in lowered:
        return (
            f"{provider.upper()} 图片生成请求失败。通常是模型不可用、账号没有图片权限，"
            "或当前组织未开通对应图片模型。"
        )

    return message
