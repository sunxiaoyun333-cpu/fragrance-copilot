import time


def retry_call(fn, attempts: int = 3, delay_seconds: float = 2.0):
    """对外部 API 调用做轻量重试。"""
    last_error = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(delay_seconds * (attempt + 1))
    raise last_error
