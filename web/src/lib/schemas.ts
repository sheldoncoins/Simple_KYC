/**
 * Zod schemas mirroring the FastAPI request/response models (app/schemas.py).
 *
 * Hand-authored for now and kept in lockstep with the API; `npm run gen:api`
 * documents regenerating these from the server's /openapi.json so client and
 * server cannot drift. Responses are parsed through these schemas so a contract
 * change surfaces immediately instead of as an undefined-field bug.
 */
import { z } from "zod";

export const OnboardRequest = z.object({
  wallet_pubkey: z.string().min(8).max(128),
  country: z.string().length(2),
  phone: z.string().optional(),
  email: z.string().optional(),
  device_fingerprint: z.string().optional(),
});
export type OnboardRequest = z.infer<typeof OnboardRequest>;

export const OnboardResponse = z.object({
  session_id: z.number().int(),
  status: z.string(),
  accepted_id_types: z.array(z.string()),
  notes: z.string(),
});
export type OnboardResponse = z.infer<typeof OnboardResponse>;

export const DocumentSubmission = z.object({
  id_type: z.string().default("passport"),
  mrz_line1: z.string(),
  mrz_line2: z.string(),
  person_seed: z.string(),
});
export type DocumentSubmission = z.infer<typeof DocumentSubmission>;

export const BiometricSubmission = z.object({
  selfie_ref: z.string(),
  person_seed: z.string(),
  // Base64 JPEG selfie frame captured during liveness (for real face match).
  selfie_b64: z.string().optional(),
});
export type BiometricSubmission = z.infer<typeof BiometricSubmission>;

export const StatusResponse = z.object({
  session_id: z.number().int(),
  status: z.string(),
  decision: z.string().nullable(),
  risk_score: z.number().nullable(),
  reject_reason: z.string().nullable(),
  signals: z.record(z.string(), z.unknown()),
});
export type StatusResponse = z.infer<typeof StatusResponse>;

export const LivenessChallenge = z.object({
  nonce: z.string(),
  sequence: z.array(z.string()),
  ttl_seconds: z.number().int(),
});
export type LivenessChallenge = z.infer<typeof LivenessChallenge>;

export const CredentialResponse = z.object({
  credential: z.string(),
  expires_in: z.number().int(),
  identity_hash: z.string(),
  limit_remaining_usdc: z.number(),
});
export type CredentialResponse = z.infer<typeof CredentialResponse>;

/** A single liveness feature frame; only derived features, never pixels. */
export const LivenessFrame = z.record(z.string(), z.number());
export type LivenessFrame = z.infer<typeof LivenessFrame>;

// --- Admin / review console -------------------------------------------------

export const ReviewListItem = z.object({
  item_id: z.number().int(),
  session_id: z.number().int(),
  reason: z.string(),
  payload: z.record(z.string(), z.unknown()),
  country: z.string().nullable(),
  status: z.string(),
  decision: z.string().nullable(),
  risk_score: z.number().nullable(),
  signals: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});
export type ReviewListItem = z.infer<typeof ReviewListItem>;

export const AuditEntry = z.object({
  id: z.number().int(),
  actor: z.string(),
  action: z.string(),
  subject: z.string().nullable(),
  detail: z.string().nullable(),
  created_at: z.string(),
});
export type AuditEntry = z.infer<typeof AuditEntry>;

export const MetricsSummary = z.object({
  total_sessions: z.number().int(),
  decided: z.number().int(),
  decisions: z.record(z.string(), z.number()),
  rates: z.record(z.string(), z.number()),
  dedup_hit_rate: z.number(),
  liveness_pass_rate: z.number(),
  per_country: z.record(z.string(), z.record(z.string(), z.number())),
});
export type MetricsSummary = z.infer<typeof MetricsSummary>;
