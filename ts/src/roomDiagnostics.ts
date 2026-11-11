export interface CandidatePairSample {
  id: string;
  protocol: "udp" | "tcp";
  candidateType: "host" | "srflx" | "relay";
  rttMs: number;
  bytesSentDelta: number;
}

export function selectHealthiestCandidate(samples: CandidatePairSample[]): CandidatePairSample | null {
  const active = samples.filter((s) => s.bytesSentDelta > 0);
  if (active.length === 0) return null;
  const priorityRank: Record<CandidatePairSample["candidateType"], number> = {
    host: 0,
    srflx: 1,
    relay: 2,
  };
  return [...active].sort((a, b) => a.rttMs - b.rttMs || priorityRank[a.candidateType] - priorityRank[b.candidateType])[0];
}

export function computeReconnectBackoffMs(attempt: number, baseMs = 250, maxMs = 10_000): number {
  const clamped = Math.max(0, attempt);
  const exp = baseMs * 2 ** clamped;
  return Math.min(maxMs, exp);
}
