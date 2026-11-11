# livekit-agent-workbench

Developer diagnostics, JWT grant auditing, barge-in latency profiling, and WebRTC/SIP failure triage utilities for real-time LiveKit voice/video agent architectures.

## Modules

- **`livekit_workbench/tokens.py`** — HS256 `AccessToken` builder & `verify_and_audit_token` inspector for `VideoGrant` permissions (`roomJoin`, `roomAdmin`, `roomCreate`, `agent`, `hidden`) with TTL, clock-skew, and least-privilege checks.
- **`livekit_workbench/agent_pipeline.py`** — Deterministic `BargeInController` state machine (`IDLE -> LISTENING -> THINKING -> SPEAKING -> INTERRUPTED`) with TTS frame queue cancellation, `TurnTrace` stage breakdowns (STT, LLM TTFT, TTS TTFA, voice-to-voice latency, interruption stop latency), and `summarize_pipeline_latencies`.
- **`livekit_workbench/diagnostics.py`** — Rule-based WebRTC (`diagnose_webrtc_session`) and SIP telephony trunk (`diagnose_sip_call`) failure classifiers for DTLS errors, UDP firewall drops without TURN/TLS fallback, packet loss, high RTT, SIP 488 codec mismatches, and 403 trunk allowlist errors.
- **`ts/src/roomDiagnostics.ts`** — Zero-dependency TypeScript client utilities (`selectHealthiestCandidate`, `computeReconnectBackoffMs`) for ICE candidate pair scoring and jittered exponential reconnect backoff.

## Running Checks

```bash
# Python suite
pytest -v

# TypeScript typecheck & unit tests
cd ts
npm install --no-package-lock
npm run build
npm test
```
