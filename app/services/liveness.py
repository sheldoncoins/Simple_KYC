"""Self-built liveness -- active challenge-response. No external vendor.

How it works, end to end:
  1. issue_challenge() returns a single-use nonce + a RANDOMLY ORDERED sequence
     of actions the user must perform on camera (e.g. ["turn_left", "blink"]).
  2. The client records a short clip and (client- or server-side) runs MediaPipe
     Face Mesh / dlib to turn each frame into a few scalar features:
        ear   eye aspect ratio        (blink: dips then recovers)
        yaw   head yaw degrees        (turn_left negative / turn_right positive)
        mar   mouth aspect ratio      (smile: sustained increase)
     `features_from_landmarks` documents that mapping; it is the ONLY part that
     needs the open-source model, and the model is self-hosted (not a SaaS).
  3. verify_response() interprets the feature timeline into detected actions and
     checks they match the issued sequence, in order, within the TTL.

Why this defeats the cheap attacks:
  * Static photo -> no blink/turn/smile signal -> fails.
  * Pre-recorded replay -> the action sequence is randomized per session and the
    nonce is single-use, so a stored clip won't match the next challenge.
What it does NOT defend against: high-quality deepfakes / 3D masks. That is the
gap where paid passive-liveness vendors still lead; acceptable at a $100 limit
combined with the 1:N dedup gate.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

CHALLENGE_TTL_SECONDS = 60
_ACTIONS = ("blink", "turn_left", "turn_right", "smile")

# Detection thresholds (would be tuned against real MediaPipe output).
_EAR_OPEN, _EAR_CLOSED = 0.25, 0.18
_YAW_TURN = 20.0
_MAR_SMILE = 0.55


@dataclass
class Challenge:
    nonce: str
    sequence: list[str]
    issued_at: float


@dataclass
class LivenessResult:
    is_live: bool
    score: float
    detected: list[str]
    reasons: list[str] = field(default_factory=list)


# Reference store; use Redis with TTL in production.
_CHALLENGES: dict[str, Challenge] = {}


def reset() -> None:
    _CHALLENGES.clear()


def issue_challenge(n_actions: int = 2) -> Challenge:
    seq = list(_ACTIONS)
    secrets.SystemRandom().shuffle(seq)
    ch = Challenge(nonce=secrets.token_urlsafe(16),
                   sequence=seq[:n_actions], issued_at=time.time())
    _CHALLENGES[ch.nonce] = ch
    return ch


def features_from_landmarks(landmarks: dict) -> dict:
    """Production seam: map MediaPipe Face Mesh landmarks -> scalar features.

    ear = mean eye aspect ratio over both eyes (vertical/horizontal eye lid
          distances), yaw/pitch from the 3x3 head-pose solve, mar = mouth
          aspect ratio. Pass-through here so callers/tests can supply features
          directly; replace the body with the landmark math when MediaPipe is
          wired in.
    """
    return {k: landmarks.get(k, 0.0) for k in ("ear", "yaw", "mar")}


def _detect(frames: list[dict]) -> list[str]:
    """Interpret a feature timeline into an ordered list of detected actions."""
    detected: list[str] = []
    eye_closed = False
    for f in frames:
        ear = f.get("ear", _EAR_OPEN)
        yaw = f.get("yaw", 0.0)
        mar = f.get("mar", 0.0)
        # Blink = a closed->open transition.
        if ear <= _EAR_CLOSED:
            eye_closed = True
        elif eye_closed and ear >= _EAR_OPEN:
            eye_closed = False
            detected.append("blink")
        if yaw <= -_YAW_TURN and (not detected or detected[-1] != "turn_left"):
            detected.append("turn_left")
        if yaw >= _YAW_TURN and (not detected or detected[-1] != "turn_right"):
            detected.append("turn_right")
        if mar >= _MAR_SMILE and (not detected or detected[-1] != "smile"):
            detected.append("smile")
    return detected


def _matches_in_order(expected: list[str], detected: list[str]) -> bool:
    it = iter(detected)
    return all(any(d == e for d in it) for e in expected)


def verify_response(nonce: str, frames: list[dict]) -> LivenessResult:
    ch = _CHALLENGES.pop(nonce, None)  # single-use: consume the nonce
    if ch is None:
        return LivenessResult(False, 0.0, [], ["unknown_or_reused_nonce"])
    if time.time() - ch.issued_at > CHALLENGE_TTL_SECONDS:
        return LivenessResult(False, 0.0, [], ["challenge_expired"])

    detected = _detect(frames)
    matched = sum(1 for a in ch.sequence if a in detected)
    completeness = matched / len(ch.sequence)
    order_ok = _matches_in_order(ch.sequence, detected)

    score = completeness * (1.0 if order_ok else 0.6)
    reasons: list[str] = []
    if completeness < 1.0:
        reasons.append("missing_actions")
    if not order_ok:
        reasons.append("wrong_order")

    from app.config import LIVENESS_MIN_SCORE
    return LivenessResult(
        is_live=score >= LIVENESS_MIN_SCORE and order_ok,
        score=round(score, 4), detected=detected, reasons=reasons,
    )
