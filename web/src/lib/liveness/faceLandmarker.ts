/**
 * MediaPipe Tasks FaceLandmarker setup + feature extraction.
 *
 * Landmark extraction runs entirely in the browser (WASM): raw video never
 * leaves the device. Each frame is reduced to three scalars the server's
 * liveness detector understands -- `ear` (eye aspect ratio), `yaw` (head turn,
 * degrees) and `mar` (mouth aspect ratio). Only that feature timeline is sent
 * to the API.
 *
 * Thresholds mirror app/services/liveness.py so the on-device guidance matches
 * how the server will score the timeline. They are starting points; tune
 * against real device output (camera, lighting) before launch.
 */
import type {
  FaceLandmarker,
  FaceLandmarkerResult,
} from "@mediapipe/tasks-vision";

const WASM_BASE =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

// Kept in sync with services/liveness.py.
export const THRESHOLDS = {
  EAR_OPEN: 0.25,
  EAR_CLOSED: 0.18,
  YAW_TURN: 20.0,
  MAR_SMILE: 0.55,
} as const;

export type Features = { ear: number; yaw: number; mar: number };

export async function createFaceLandmarker(): Promise<FaceLandmarker> {
  // Loaded lazily (browser-only WASM); never evaluated during SSR/build.
  const { FaceLandmarker, FilesetResolver } = await import(
    "@mediapipe/tasks-vision"
  );
  const fileset = await FilesetResolver.forVisionTasks(WASM_BASE);
  return FaceLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
    runningMode: "VIDEO",
    numFaces: 1,
    outputFacialTransformationMatrixes: true,
  });
}

type Point = { x: number; y: number; z: number };

function dist(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function eyeAspectRatio(lm: Point[], idx: number[]): number {
  const [p1, p2, p3, p4, p5, p6] = idx.map((i) => lm[i]);
  const horizontal = dist(p1, p4) || 1e-6;
  return (dist(p2, p6) + dist(p3, p5)) / (2 * horizontal);
}

// MediaPipe Face Mesh landmark indices.
const LEFT_EYE = [33, 160, 158, 133, 153, 144];
const RIGHT_EYE = [362, 385, 387, 263, 373, 380];
const MOUTH_TOP = 13;
const MOUTH_BOTTOM = 14;
const MOUTH_LEFT = 61;
const MOUTH_RIGHT = 291;

/** Reduce one FaceLandmarker result to the {ear, yaw, mar} the server scores. */
export function extractFeatures(result: FaceLandmarkerResult): Features | null {
  const lm = result.faceLandmarks?.[0] as Point[] | undefined;
  if (!lm || lm.length < 468) return null;

  const ear =
    (eyeAspectRatio(lm, LEFT_EYE) + eyeAspectRatio(lm, RIGHT_EYE)) / 2;

  const mouthVertical = dist(lm[MOUTH_TOP], lm[MOUTH_BOTTOM]);
  const mouthHorizontal = dist(lm[MOUTH_LEFT], lm[MOUTH_RIGHT]) || 1e-6;
  const mar = mouthVertical / mouthHorizontal;

  // Yaw from the 4x4 facial transformation matrix (column-major). Front cameras
  // are mirrored, so the sign convention may need flipping per deployment.
  const matrix = result.facialTransformationMatrixes?.[0]?.data;
  let yaw = 0;
  if (matrix && matrix.length === 16) {
    yaw = (Math.atan2(matrix[8], matrix[10]) * 180) / Math.PI;
  }

  return {
    ear: round(ear),
    yaw: round(yaw),
    mar: round(mar),
  };
}

function round(n: number): number {
  return Math.round(n * 1000) / 1000;
}
