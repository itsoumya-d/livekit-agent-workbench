"""Voice profile validation and real-time streaming audio quality evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VoiceProfile:
    """Specification of a designed or cloned voice asset."""
    voice_id: str
    language: str
    sample_rate_hz: int = 24000
    target_speed: float = 1.0
    target_pitch_semitones: float = 0.0
    timbre_tags: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.voice_id.strip():
            errors.append("voice_id must not be empty")
        if self.sample_rate_hz not in (16000, 22050, 24000, 44100, 48000):
            errors.append(f"unsupported sample_rate_hz: {self.sample_rate_hz}")
        if not (0.5 <= self.target_speed <= 2.0):
            errors.append(f"target_speed {self.target_speed} outside supported bounds [0.5, 2.0]")
        if not (-12.0 <= self.target_pitch_semitones <= 12.0):
            errors.append("target_pitch_semitones outside bounds [-12.0, 12.0]")
        return errors


@dataclass
class AudioChunk:
    """Streamed PCM audio chunk with timing metadata."""
    chunk_id: int
    timestamp_ms: float
    samples: List[float]  # normalized float samples in [-1.0, 1.0]
    sample_rate_hz: int = 24000


@dataclass
class StreamQualityReport:
    """Summary metrics of a streamed voice playback session."""
    total_chunks: int
    total_samples: int
    duration_seconds: float
    peak_amplitude: float
    is_clipped: bool
    snr_estimate_db: float
    silence_ratio: float
    avg_arrival_jitter_ms: float
    buffer_underrun_risk: bool
    passed_quality_bar: bool


class VoiceQualityEvaluator:
    """Evaluates real-time audio chunk metrics, jitter, and signal integrity."""

    def __init__(self, clip_threshold: float = 0.99, silence_rms_threshold: float = 0.01):
        self.clip_threshold = clip_threshold
        self.silence_rms_threshold = silence_rms_threshold
        self.chunks: List[AudioChunk] = []

    def ingest_chunk(self, chunk: AudioChunk) -> None:
        self.chunks.append(chunk)

    def compute_metrics(self, max_allowed_jitter_ms: float = 25.0) -> StreamQualityReport:
        if not self.chunks:
            return StreamQualityReport(
                total_chunks=0, total_samples=0, duration_seconds=0.0,
                peak_amplitude=0.0, is_clipped=False, snr_estimate_db=0.0,
                silence_ratio=1.0, avg_arrival_jitter_ms=0.0,
                buffer_underrun_risk=True, passed_quality_bar=False,
            )

        all_samples: List[float] = []
        peak_amp = 0.0
        clipped = False
        sample_rate = self.chunks[0].sample_rate_hz

        for chunk in self.chunks:
            for s in chunk.samples:
                abs_s = abs(s)
                if abs_s > peak_amp:
                    peak_amp = abs_s
                if abs_s >= self.clip_threshold:
                    clipped = True
                all_samples.append(s)

        total_samples = len(all_samples)
        duration_s = total_samples / sample_rate if sample_rate > 0 else 0.0

        # Calculate RMS energy and approximate SNR
        sum_sq = sum(s * s for s in all_samples)
        rms = math.sqrt(sum_sq / total_samples) if total_samples > 0 else 0.0

        # Silence estimation across 20ms frames
        frame_size = int(sample_rate * 0.02) or 1
        silent_frames = 0
        total_frames = 0
        for i in range(0, total_samples, frame_size):
            frame = all_samples[i:i + frame_size]
            frame_rms = math.sqrt(sum(s * s for s in frame) / len(frame))
            if frame_rms < self.silence_rms_threshold:
                silent_frames += 1
            total_frames += 1

        silence_ratio = silent_frames / total_frames if total_frames > 0 else 0.0

        # Signal-to-noise ratio estimate
        noise_floor = max(0.0001, self.silence_rms_threshold)
        snr_db = 20.0 * math.log10(max(rms, 0.0001) / noise_floor) if rms > 0 else 0.0

        # Arrival jitter across successive chunks
        jitters: List[float] = []
        for i in range(1, len(self.chunks)):
            interval = self.chunks[i].timestamp_ms - self.chunks[i - 1].timestamp_ms
            expected = (len(self.chunks[i - 1].samples) / sample_rate) * 1000.0
            jitters.append(abs(interval - expected))

        avg_jitter = sum(jitters) / len(jitters) if jitters else 0.0
        underrun_risk = avg_jitter > max_allowed_jitter_ms

        passed = (
            not clipped
            and peak_amp > 0.05
            and silence_ratio < 0.65
            and not underrun_risk
            and snr_db >= 12.0
        )

        return StreamQualityReport(
            total_chunks=len(self.chunks),
            total_samples=total_samples,
            duration_seconds=round(duration_s, 3),
            peak_amplitude=round(peak_amp, 4),
            is_clipped=clipped,
            snr_estimate_db=round(snr_db, 2),
            silence_ratio=round(silence_ratio, 3),
            avg_arrival_jitter_ms=round(avg_jitter, 2),
            buffer_underrun_risk=underrun_risk,
            passed_quality_bar=passed,
        )
