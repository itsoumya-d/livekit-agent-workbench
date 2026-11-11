from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class IceCandidateStats:
    local_type: Literal["host", "srflx", "prflx", "relay"]
    remote_type: Literal["host", "srflx", "prflx", "relay"]
    protocol: Literal["udp", "tcp"]
    rtt_ms: float
    packet_loss_pct: float
    dtls_state: Literal["connected", "connecting", "failed", "closed"]
    udp_blocked: bool = False


@dataclass(frozen=True)
class SipCallTrace:
    call_id: str
    sip_status: int
    codec_offered: list[str]
    codec_answered: list[str]
    rtp_packets_rx: int
    dtmf_mode: str = "rfc2833"


def diagnose_webrtc_session(stats: IceCandidateStats) -> dict[str, object]:
    """Identify production WebRTC media/ICE failures and actionable remediations."""
    findings: list[str] = []
    severity = "healthy"

    if stats.dtls_state == "failed":
        severity = "critical"
        findings.append("DTLS_HANDSHAKE_FAILED: check UDP port range 50000-60000 / firewall inspection")
    if stats.udp_blocked and stats.local_type != "relay":
        severity = "critical"
        findings.append("UDP_BLOCKED_NO_TURN_RELAY: enable TURN/TLS on TCP/443 fallback")
    if stats.packet_loss_pct >= 5.0:
        severity = "degraded" if severity == "healthy" else severity
        findings.append(f"HIGH_PACKET_LOSS ({stats.packet_loss_pct:.1f}%): enable RED/Opus DTX and check Wi-Fi/TURN hops")
    if stats.rtt_ms >= 280.0:
        severity = "degraded" if severity == "healthy" else severity
        findings.append(f"ELEVATED_RTT ({stats.rtt_ms:.0f}ms): route participant to nearest LiveKit Cloud edge region")

    return {
        "severity": severity,
        "path": f"{stats.local_type}->{stats.remote_type}/{stats.protocol}",
        "findings": findings,
    }


def diagnose_sip_call(trace: SipCallTrace) -> dict[str, object]:
    """Triage common SIP telephony trunk failures in voice AI deployments."""
    issues: list[str] = []
    if trace.sip_status == 488:
        issues.append("CODEC_MISMATCH_488: offer PCMU (G.711u) / PCMA / opus=111 on LiveKit SIP trunk")
    elif trace.sip_status == 403:
        issues.append("SIP_AUTH_403: verify inbound trunk IP allowlist & username/password digest")
    elif trace.sip_status == 486:
        issues.append("CALLEE_BUSY_486: trigger exponential retry or voicemail fallback agent")
    elif trace.sip_status >= 500:
        issues.append(f"UPSTREAM_TRUNK_5XX ({trace.sip_status}): failover to secondary SIP carrier")

    if trace.sip_status == 200 and trace.rtp_packets_rx == 0:
        issues.append("ONE_WAY_OR_SILENT_AUDIO: 200 OK received with zero RTP frames; verify NAT SDP c= IP and symmetric RTP")

    return {
        "call_id": trace.call_id,
        "healthy": len(issues) == 0,
        "issues": issues,
    }
