from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum


class AgentState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


@dataclass
class TurnTrace:
    turn_id: str
    vad_end_ms: float
    stt_final_ms: float
    llm_first_token_ms: float
    tts_first_audio_ms: float
    interrupted_at_ms: float | None = None
    tts_cancelled_ms: float | None = None
    dropped_audio_frames: int = 0

    @property
    def stt_latency_ms(self) -> float:
        return max(0.0, self.stt_final_ms - self.vad_end_ms)

    @property
    def llm_ttft_ms(self) -> float:
        return max(0.0, self.llm_first_token_ms - self.stt_final_ms)

    @property
    def tts_ttfa_ms(self) -> float:
        return max(0.0, self.tts_first_audio_ms - self.llm_first_token_ms)

    @property
    def voice_to_voice_ms(self) -> float:
        return max(0.0, self.tts_first_audio_ms - self.vad_end_ms)

    @property
    def interruption_stop_ms(self) -> float | None:
        if self.interrupted_at_ms is None or self.tts_cancelled_ms is None:
            return None
        return max(0.0, self.tts_cancelled_ms - self.interrupted_at_ms)


@dataclass
class BargeInController:
    """Deterministic voice agent state machine supporting mid-utterance barge-in."""

    state: AgentState = AgentState.IDLE
    active_turn_id: str | None = None
    queued_tts_frames: list[int] = field(default_factory=list)
    completed_traces: list[TurnTrace] = field(default_factory=list)
    _vad_end_ms: float = 0.0
    _stt_final_ms: float = 0.0
    _llm_first_ms: float = 0.0
    _tts_first_ms: float = 0.0

    def on_user_speech_start(self, ts_ms: float) -> int:
        dropped = 0
        if self.state == AgentState.SPEAKING and self.queued_tts_frames:
            dropped = len(self.queued_tts_frames)
            self.queued_tts_frames.clear()
            self.state = AgentState.INTERRUPTED
            if self.completed_traces and self.completed_traces[-1].turn_id == self.active_turn_id:
                last = self.completed_traces[-1]
                last.interrupted_at_ms = ts_ms
                last.tts_cancelled_ms = ts_ms + 8.0
                last.dropped_audio_frames = dropped
        self.state = AgentState.LISTENING
        return dropped

    def on_turn_complete(
        self,
        turn_id: str,
        vad_end_ms: float,
        stt_final_ms: float,
        llm_first_token_ms: float,
        tts_first_audio_ms: float,
        tts_frames: int = 12,
    ) -> TurnTrace:
        self.active_turn_id = turn_id
        self._vad_end_ms = vad_end_ms
        self._stt_final_ms = stt_final_ms
        self._llm_first_ms = llm_first_token_ms
        self._tts_first_ms = tts_first_audio_ms
        self.state = AgentState.SPEAKING
        self.queued_tts_frames = list(range(tts_frames))
        trace = TurnTrace(
            turn_id=turn_id,
            vad_end_ms=vad_end_ms,
            stt_final_ms=stt_final_ms,
            llm_first_token_ms=llm_first_token_ms,
            tts_first_audio_ms=tts_first_audio_ms,
        )
        self.completed_traces.append(trace)
        return trace

    def on_playout_finished(self) -> None:
        self.queued_tts_frames.clear()
        self.state = AgentState.LISTENING


def summarize_pipeline_latencies(traces: list[TurnTrace], sla_budget_ms: float = 900.0) -> dict[str, float | int]:
    """Compute p50/p95/p99 voice-to-voice turn budgets and SLA compliance."""
    if not traces:
        return {"turns": 0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "sla_breaches": 0}
    totals = sorted(t.voice_to_voice_ms for t in traces)
    n = len(totals)

    def pct(p: float) -> float:
        idx = min(n - 1, int(round((p / 100.0) * (n - 1))))
        return round(totals[idx], 2)

    return {
        "turns": n,
        "p50_ms": round(statistics.median(totals), 2),
        "p95_ms": pct(95),
        "p99_ms": pct(99),
        "stt_mean_ms": round(statistics.mean(t.stt_latency_ms for t in traces), 2),
        "llm_mean_ms": round(statistics.mean(t.llm_ttft_ms for t in traces), 2),
        "tts_mean_ms": round(statistics.mean(t.tts_ttfa_ms for t in traces), 2),
        "sla_breaches": sum(1 for v in totals if v > sla_budget_ms),
    }
