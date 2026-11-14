"""Single-owner, administratively provisioned sessions; no public registration."""

import hashlib
import hmac
import re
import secrets
import time

from saham_signal.config import Settings


def session_cookie(config: Settings, *, now: int | None = None) -> str:
    if not config.session_secret or not config.pilot_account_id:
        raise ValueError("Session provisioning requires a secret and pilot account")
    expires = (int(time.time()) if now is None else now) + config.session_ttl_seconds
    payload = f"v1.{expires}.{secrets.token_hex(32)}"
    return payload + "." + signature(config, payload)


def signature(config: Settings, payload: str) -> str:
    assert config.session_secret is not None
    message = f"{config.app_mode}\n{config.pilot_account_id}\n{payload}"
    return hmac.new(
        config.session_secret.get_secret_value().encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def valid_session(config: Settings, cookie: str | None, *, now: int | None = None) -> bool:
    if not cookie or len(cookie) > 256:
        return False
    if config.session_secret:
        if not re.fullmatch(r"v1\.[0-9]{1,12}\.[a-f0-9]{64}\.[a-f0-9]{64}", cookie):
            return False
        payload, supplied = cookie.rsplit(".", 1)
        current = int(time.time()) if now is None else now
        expires = int(payload.split(".")[1])
        return current < expires <= current + config.session_ttl_seconds and hmac.compare_digest(
            signature(config, payload), supplied
        )
    expected = config.market_fixture_token
    return bool(
        not config.deployment_tls_required
        and config.app_mode == "research"
        and expected
        and hmac.compare_digest(cookie.encode(), expected.get_secret_value().encode())
    )


def main() -> None:
    from saham_signal.config import load_settings

    # Intentional credential export to the administrator; never redirect to logs.
    config = load_settings()
    print(
        f"saham_session={session_cookie(config)}; Path=/; HttpOnly; SameSite=Strict; "
        f"Max-Age={config.session_ttl_seconds}"
        + ("; Secure" if config.deployment_tls_required else "")
    )


if __name__ == "__main__":
    main()
