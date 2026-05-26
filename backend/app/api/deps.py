import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """单一 API key 鉴权。

    C.4：受 settings.require_api_key 开关控制。
    - False (default)：跳过校验，适合本地/内网/dev 环境
    - True：强制 X-API-Key header 匹配 settings.api_key
    """
    if not settings.require_api_key:
        return
    if not settings.api_key:
        # 配置错误：开启了校验但 api_key 为空
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="require_api_key enabled but api_key not configured",
        )
    # 用 compare_digest 而非 ==，避免 timing side-channel 推断 key
    if not secrets.compare_digest(x_api_key or "", settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-API-Key",
        )
