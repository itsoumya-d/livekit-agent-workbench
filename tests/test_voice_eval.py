"""Unit tests for voice profile validation and streaming audio quality evaluation."""

import math
from livekit_workbench.voice_eval import AudioChunk, VoiceProfile, VoiceQualityEvaluator


def test_voice_profile_validation():
    valid = VoiceProfile(
        voice_id="clarity-narrator-en",
        language="en-US",
        sample_rate_hz=24000,
        target_speed=1.05,
        target_pitch_semitones=0.5,
        timbre_tags=["warm", "authoritative"],
    )
    assert valid.validate() == []

    invalid = VoiceProfile(
        voice_id="",
        language="en-US",
        sample_rate_hz=12345,
        target_speed=3.0,
        target_pitch_semitones=-15.0,
    )
    errs = invalid.validate()
    assert len(errs) == 4
    assert any("voice_id" in e for e in errs)
    assert any("sample_rate_hz" in e for e in errs)


def test_clean_audio_stream_passes_quality():
    evaluator = VoiceQualityEvaluator()
    sr = 24000
    chunk_samples = 480  # 20ms at 24kHz

    # Generate 5 chunks of a clean 440Hz sine wave
    for i in range(5):
        samples = [
            0.4 * math.sin(2 * math.pi * 440.0 * (i * chunk_samples + j) / sr)
            for j in range(chunk_samples)
        ]
        evaluator.ingest_chunk(AudioChunk(
            chunk_id=i,
            timestamp_ms=float(i * 20),
            samples=samples,
            sample_rate_hz=sr,
        ))

    report = evaluator.compute_metrics(max_allowed_jitter_ms=10.0)
    assert report.total_chunks == 5
    assert report.total_samples == 2400
    assert report.duration_seconds == 0.1
    assert not report.is_clipped
    assert report.avg_arrival_jitter_ms == 0.0
    assert not report.buffer_underrun_risk
    assert report.passed_quality_bar


def test_clipped_audio_stream_fails_quality():
    evaluator = VoiceQualityEvaluator()
    samples = [1.0 if i % 2 == 0 else -1.0 for i in range(480)]
    evaluator.ingest_chunk(AudioChunk(
        chunk_id=0,
        timestamp_ms=0.0,
        samples=samples,
        sample_rate_hz=24000,
    ))

    report = evaluator.compute_metrics()
    assert report.is_clipped
    assert not report.passed_quality_bar


def test_high_jitter_flags_underrun_risk():
    evaluator = VoiceQualityEvaluator()
    sr = 24000
    chunk_samples = 480  # expected interval: 20ms

    # Deliver chunk 0 at t=0ms, chunk 1 at t=120ms (100ms jitter)
    evaluator.ingest_chunk(AudioChunk(0, 0.0, [0.2] * chunk_samples, sr))
    evaluator.ingest_chunk(AudioChunk(1, 120.0, [0.2] * chunk_samples, sr))

    report = evaluator.compute_metrics(max_allowed_jitter_ms=25.0)
    assert report.avg_arrival_jitter_ms == 100.0
    assert report.buffer_underrun_risk
    assert not report.passed_quality_bar
