import test from "node:test";
import assert from "node:assert/strict";
import { assessAudioBufferHealth } from "../src/voiceQuality.ts";

test("identifies buffer starving when under minimum threshold", () => {
  const status = assessAudioBufferHealth(0.02, 0.2, 2.0);
  assert.equal(status.isStarving, true);
  assert.equal(status.recommendedAction, "buffer");
});

test("identifies healthy buffer state ready for playback", () => {
  const status = assessAudioBufferHealth(0.3, 0.2, 2.0);
  assert.equal(status.isStarving, false);
  assert.equal(status.isOverflowing, false);
  assert.equal(status.recommendedAction, "play");
});

test("identifies buffer overflow requiring frame dropping", () => {
  const status = assessAudioBufferHealth(2.5, 0.2, 2.0);
  assert.equal(status.isOverflowing, true);
  assert.equal(status.recommendedAction, "drop");
});
