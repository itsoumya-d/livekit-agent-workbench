import time
from livekit_workbench import (
    AccessToken,
    AgentState,
    BargeInController,
    IceCandidateStats,
    SipCallTrace,
    VideoGrant,
    diagnose_sip_call,
    diagnose_webrtc_session,
    summarize_pipeline_latencies,
    verify_and_audit_token,
)


def test_access_token_roundtrip_and_audit_warnings():
    tok = AccessToken(
        api_key="devkey",
        api_secret="secret-at-least-32-chars-for-livekit-hs256",
        identity="agent-worker-01",
        name="Voice Concierge",
        ttl_seconds=1800,
        video=VideoGrant(room_join=True, room="support-room-42", agent=True),
        room_config_agents=[{"agentName": "voice-concierge"}],
    )
    jwt = tok.to_jwt(now=1_800_000_000)
    audit = verify_and_audit_token(jwt, "secret-at-least-32-chars-for-livekit-hs256", now=1_800_000_010)
    assert audit.valid_signature is True
    assert audit.expired is False
    assert audit.warnings == []
    assert audit.claims["video"]["room"] == "support-room-42"

    # Bad token missing room name + wrong secret should be flagged cleanly
    bad = AccessToken(api_key="k", api_secret="s", identity="u", video=VideoGrant(room_join=True, room=""))
    bad_audit = verify_and_audit_token(bad.to_jwt(now=1_800_000_000), "wrong", now=1_800_000_000)
    assert bad_audit.valid_signature is False
    assert any("MISSING_ROOM_NAME" in w for w in bad_audit.warnings)


def test_voice_agent_barge_in_and_latency_sla():
    ctl = BargeInController()
    t1 = ctl.on_turn_complete(
        turn_id="turn-1",
        vad_end_ms=1000.0,
        stt_final_ms=1180.0,
        llm_first_token_ms=1490.0,
        tts_first_audio_ms=1670.0,
        tts_frames=16,
    )
    assert t1.voice_to_voice_ms == 670.0
    assert ctl.state == AgentState.SPEAKING

    dropped = ctl.on_user_speech_start(1820.0)
    assert dropped == 16
    assert ctl.state == AgentState.LISTENING
    assert t1.interruption_stop_ms == 8.0

    t2 = ctl.on_turn_complete("turn-2", 2000.0, 2240.0, 2750.0, 3020.0, tts_frames=8)
    summary = summarize_pipeline_latencies([t1, t2], sla_budget_ms=900.0)
    assert summary["turns"] == 2
    assert summary["sla_breaches"] == 1


def test_webrtc_and_sip_diagnostics():
    ice_bad = IceCandidateStats(
        local_type="host",
        remote_type="srflx",
        protocol="udp",
        rtt_ms=340.0,
        packet_loss_pct=7.2,
        dtls_state="failed",
        udp_blocked=True,
    )
    rep = diagnose_webrtc_session(ice_bad)
    assert rep["severity"] == "critical"
    assert len(rep["findings"]) == 4

    sip_bad = SipCallTrace(call_id="sip-99", sip_status=488, codec_offered=["G729"], codec_answered=[], rtp_packets_rx=0)
    srep = diagnose_sip_call(sip_bad)
    assert srep["healthy"] is False
    assert any("CODEC_MISMATCH_488" in x for x in srep["issues"])

    sip_ok = SipCallTrace(call_id="sip-100", sip_status=200, codec_offered=["opus"], codec_answered=["opus"], rtp_packets_rx=420)
    assert diagnose_sip_call(sip_ok)["healthy"] is True
