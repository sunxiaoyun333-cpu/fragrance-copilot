import os

from dotenv import dotenv_values


def load_project_env():
    """仅用 .env 中的非空值覆盖当前环境变量。"""
    for key, value in dotenv_values().items():
        if value:
            os.environ[key] = value
