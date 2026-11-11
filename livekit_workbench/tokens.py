import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(seg: str) -> bytes:
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)


@dataclass(frozen=True)
class VideoGrant:
    """LiveKit-compatible room and SIP access grants."""

    room_join: bool = False
    room: str = ""
    can_publish: bool = True
    can_subscribe: bool = True
    can_publish_data: bool = True
    room_admin: bool = False
    room_create: bool = False
    agent: bool = False
    hidden: bool = False

    def to_claims(self) -> dict[str, Any]:
        claims: dict[str, Any] = {}
        if self.room_join:
            claims["roomJoin"] = True
        if self.room:
            claims["room"] = self.room
        claims["canPublish"] = self.can_publish
        claims["canSubscribe"] = self.can_subscribe
        claims["canPublishData"] = self.can_publish_data
        if self.room_admin:
            claims["roomAdmin"] = True
        if self.room_create:
            claims["roomCreate"] = True
        if self.agent:
            claims["agent"] = True
        if self.hidden:
            claims["hidden"] = True
        return claims


@dataclass
class AccessToken:
    """Mints HS256 JWT tokens compatible with LiveKit SFU & Agents workers."""

    api_key: str
    api_secret: str
    identity: str
    name: str = ""
    ttl_seconds: int = 3600
    video: VideoGrant = field(default_factory=VideoGrant)
    room_config_agents: list[dict[str, str]] = field(default_factory=list)
    metadata: str = ""

    def to_jwt(self, now: int | None = None) -> str:
        ts = int(time.time()) if now is None else int(now)
        header = {"alg": "HS256", "typ": "JWT"}
        payload: dict[str, Any] = {
            "iss": self.api_key,
            "sub": self.identity,
            "nbf": ts - 5,
            "iat": ts,
            "exp": ts + self.ttl_seconds,
            "video": self.video.to_claims(),
        }
        if self.name:
            payload["name"] = self.name
        if self.metadata:
            payload["metadata"] = self.metadata
        if self.room_config_agents:
            payload["roomConfig"] = {"agents": self.room_config_agents}

        signing_input = f"{_b64u(json.dumps(header, separators=(',', ':')).encode())}.{_b64u(json.dumps(payload, separators=(',', ':')).encode())}"
        sig = hmac.new(self.api_secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
        return f"{signing_input}.{_b64u(sig)}"


@dataclass(frozen=True)
class TokenAuditResult:
    valid_signature: bool
    expired: bool
    clock_skew_risk: bool
    warnings: list[str]
    claims: dict[str, Any]


def verify_and_audit_token(token: str, api_secret: str, now: int | None = None) -> TokenAuditResult:
    """Verify HS256 signature and surface common DevSuccess deployment bugs."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format: expected 3 segments")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected_sig = hmac.new(api_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _b64u_decode(parts[2])
    valid_sig = hmac.compare_digest(expected_sig, actual_sig)

    claims = json.loads(_b64u_decode(parts[1]).decode("utf-8"))
    ts = int(time.time()) if now is None else int(now)
    exp = int(claims.get("exp", 0))
    nbf = int(claims.get("nbf", 0))
    expired = ts >= exp
    clock_skew_risk = nbf > ts
    warnings: list[str] = []

    video = claims.get("video") or {}
    if not video.get("roomJoin"):
        warnings.append("MISSING_ROOM_JOIN: token cannot join a room without video.roomJoin=true")
    if video.get("roomJoin") and not video.get("room"):
        warnings.append("MISSING_ROOM_NAME: roomJoin=true requires non-empty video.room")
    if clock_skew_risk:
        warnings.append(f"CLOCK_SKEW: nbf ({nbf}) > current time ({ts}); client clock drift may cause 401")
    if exp - ts > 86400:
        warnings.append("LONG_TTL: token TTL exceeds 24h; shorten TTL for production client participants")
    if video.get("roomAdmin") and not video.get("agent"):
        warnings.append("OVERPRIVILEGED_CLIENT: non-agent participant holds roomAdmin grant")

    return TokenAuditResult(
        valid_signature=valid_sig,
        expired=expired,
        clock_skew_risk=clock_skew_risk,
        warnings=warnings,
        claims=claims,
    )
