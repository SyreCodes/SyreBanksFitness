"""Redis configuration shared by authentication, readiness, and background jobs."""

import ssl
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry


def redis_tls_options(url: str, *, production: bool = False) -> dict[str, Any]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise ValueError("REDIS_URL must be a redis:// or rediss:// connection URL")
    if production and parsed.scheme != "rediss":
        raise ValueError("Production REDIS_URL must use rediss:// with TLS")
    if parsed.scheme != "rediss":
        return {}

    # URL parameters override client options in both redis-py and Celery.
    # Reject insecure overrides before either client receives the URL.
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "ssl_cert_reqs" and value != "required":
            raise ValueError("REDIS_URL ssl_cert_reqs must be required")
        if key == "ssl_check_hostname" and value.lower() not in {"true", "yes", "1"}:
            raise ValueError("REDIS_URL must enable TLS hostname verification")
    return {"ssl_cert_reqs": ssl.CERT_REQUIRED, "ssl_check_hostname": True}


def redis_client(url: str, *, production: bool = False) -> Redis:
    return Redis.from_url(
        url,
        **redis_tls_options(url, production=production),
        socket_connect_timeout=2,
        socket_timeout=2,
        retry=Retry(NoBackoff(), 0),
    )
