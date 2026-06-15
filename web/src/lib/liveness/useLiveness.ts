"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FaceLandmarker } from "@mediapipe/tasks-vision";
import {
  createFaceLandmarker,
  extractFeatures,
  THRESHOLDS,
  type Features,
} from "./faceLandmarker";
import { log } from "@/lib/logger";

export type LivenessStatus = "idle" | "loading" | "running" | "done" | "error";

const INSTRUCTIONS: Record<string, string> = {
  blink: "Blink your eyes",
  turn_left: "Slowly turn your head to the left",
  turn_right: "Slowly turn your head to the right",
  smile: "Smile with your mouth open",
};

export interface LivenessState {
  status: LivenessStatus;
  /** The action the user should perform right now. */
  currentAction: string | null;
  instruction: string;
  /** 0..1 across the whole sequence. */
  progress: number;
  /** Derived feature timeline to send to the server. */
  frames: Features[];
  error: string | null;
}

/**
 * Drives the camera + FaceLandmarker through a challenge sequence. Detection
 * here mirrors the server (app/services/liveness.py) so the guidance matches
 * scoring; the server remains the source of truth.
 */
export function useLiveness(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  sequence: string[],
) {
  const [state, setState] = useState<LivenessState>({
    status: "idle",
    currentAction: sequence[0] ?? null,
    instruction: INSTRUCTIONS[sequence[0]] ?? "",
    progress: 0,
    frames: [],
    error: null,
  });

  const landmarkerRef = useRef<FaceLandmarker | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const framesRef = useRef<Features[]>([]);
  const stepRef = useRef(0);
  const eyeClosedRef = useRef(false);
  const lastVideoTimeRef = useRef(-1);

  const cleanup = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    landmarkerRef.current?.close();
    landmarkerRef.current = null;
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const advance = useCallback(() => {
    eyeClosedRef.current = false;
    const next = stepRef.current + 1;
    stepRef.current = next;
    if (next >= sequence.length) {
      cleanup();
      setState((s) => ({
        ...s,
        status: "done",
        currentAction: null,
        instruction: "All done — checking…",
        progress: 1,
        frames: framesRef.current,
      }));
      return;
    }
    setState((s) => ({
      ...s,
      currentAction: sequence[next],
      instruction: INSTRUCTIONS[sequence[next]] ?? "",
      progress: next / sequence.length,
    }));
  }, [sequence, cleanup]);

  const detectCurrent = useCallback(
    (f: Features) => {
      const action = sequence[stepRef.current];
      switch (action) {
        case "blink":
          if (f.ear <= THRESHOLDS.EAR_CLOSED) eyeClosedRef.current = true;
          else if (eyeClosedRef.current && f.ear >= THRESHOLDS.EAR_OPEN)
            advance();
          break;
        case "turn_left":
          if (f.yaw <= -THRESHOLDS.YAW_TURN) advance();
          break;
        case "turn_right":
          if (f.yaw >= THRESHOLDS.YAW_TURN) advance();
          break;
        case "smile":
          if (f.mar >= THRESHOLDS.MAR_SMILE) advance();
          break;
      }
    },
    [sequence, advance],
  );

  const loop = useCallback(() => {
    const video = videoRef.current;
    const landmarker = landmarkerRef.current;
    if (!video || !landmarker) return;
    if (video.currentTime !== lastVideoTimeRef.current) {
      lastVideoTimeRef.current = video.currentTime;
      const result = landmarker.detectForVideo(video, performance.now());
      const features = extractFeatures(result);
      if (features) {
        framesRef.current.push(features);
        detectCurrent(features);
      }
    }
    if (stepRef.current < sequence.length) {
      rafRef.current = requestAnimationFrame(loop);
    }
  }, [videoRef, detectCurrent, sequence.length]);

  const start = useCallback(async () => {
    setState((s) => ({ ...s, status: "loading", error: null }));
    framesRef.current = [];
    stepRef.current = 0;
    eyeClosedRef.current = false;
    lastVideoTimeRef.current = -1;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 640, height: 480 },
        audio: false,
      });
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) throw new Error("no_video_element");
      video.srcObject = stream;
      await video.play();
      landmarkerRef.current = await createFaceLandmarker();
      setState((s) => ({
        ...s,
        status: "running",
        currentAction: sequence[0] ?? null,
        instruction: INSTRUCTIONS[sequence[0]] ?? "",
        progress: 0,
      }));
      log.event("liveness_started", { actions: sequence.length });
      rafRef.current = requestAnimationFrame(loop);
    } catch (e) {
      cleanup();
      const reason =
        e instanceof DOMException && e.name === "NotAllowedError"
          ? "camera_permission_denied"
          : "camera_unavailable";
      log.error("liveness_error", { reason });
      setState((s) => ({ ...s, status: "error", error: reason }));
    }
  }, [videoRef, sequence, loop, cleanup]);

  return { ...state, start, reset: cleanup };
}
