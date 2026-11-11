import assert from "node:assert/strict";
import test from "node:test";
import { computeReconnectBackoffMs, selectHealthiestCandidate } from "../src/roomDiagnostics.ts";

test("selects lowest RTT active candidate and computes capped exponential backoff", () => {
  const winner = selectHealthiestCandidate([
    { id: "c1", protocol: "udp", candidateType: "host", rttMs: 5, bytesSentDelta: 0 },
    { id: "c2", protocol: "tcp", candidateType: "relay", rttMs: 112, bytesSentDelta: 1024 },
    { id: "c3", protocol: "udp", candidateType: "srflx", rttMs: 28, bytesSentDelta: 2048 },
  ]);
  assert.equal(winner?.id, "c3");
  assert.equal(computeReconnectBackoffMs(0), 250);
  assert.equal(computeReconnectBackoffMs(10), 10_000);
});
