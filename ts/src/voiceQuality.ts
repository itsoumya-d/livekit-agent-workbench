/**
 * Client-side audio buffer health assessment for streaming voice synthesis playback.
 */

export interface BufferHealthStatus {
  bufferDurationSeconds: number;
  isStarving: boolean;
  isOverflowing: boolean;
  recommendedAction: "play" | "buffer" | "drop";
}

export function assessAudioBufferHealth(
  bufferDurationSeconds: number,
  targetBufferSeconds = 0.2,
  maxBufferSeconds = 2.0
): BufferHealthStatus {
  const isStarving = bufferDurationSeconds < targetBufferSeconds * 0.25;
  const isOverflowing = bufferDurationSeconds > maxBufferSeconds;

  let recommendedAction: "play" | "buffer" | "drop" = "play";
  if (isStarving) {
    recommendedAction = "buffer";
  } else if (isOverflowing) {
    recommendedAction = "drop";
  }

  return {
    bufferDurationSeconds,
    isStarving,
    isOverflowing,
    recommendedAction,
  };
}
