/**
 * Typed client for the KYC API. Every response is validated with the Zod
 * schemas so a server contract change is caught at the boundary. No PII is
 * logged here -- request bodies (MRZ, frames) are never passed to `log`.
 */
import { log } from "./logger";
import {
  BiometricSubmission,
  CredentialResponse,
  DocumentSubmission,
  LivenessChallenge,
  LivenessFrame,
  OnboardResponse,
  StatusResponse,
} from "./schemas";
import { z } from "zod";

const BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "network_error");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    log.error("api_error", { path, status: res.status });
    throw new ApiError(res.status, detail);
  }
  return schema.parse(await res.json());
}

export const api = {
  onboard(input: { wallet_pubkey: string; country: string }) {
    return request("/v1/onboard", OnboardResponse, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  submitPassport(sessionId: number, doc: DocumentSubmission) {
    return request(`/v1/sessions/${sessionId}/passport`, StatusResponse, {
      method: "POST",
      body: JSON.stringify(doc),
    });
  },

  async submitPassportImage(sessionId: number, file: Blob, personSeed: string) {
    const form = new FormData();
    form.append("person_seed", personSeed);
    form.append("file", file, "passport");
    let res: Response;
    try {
      // No Content-Type header: the browser sets the multipart boundary.
      res = await fetch(
        `${BASE_URL}/v1/sessions/${sessionId}/passport/image`,
        { method: "POST", body: form },
      );
    } catch {
      throw new ApiError(0, "network_error");
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = (await res.json()) as { detail?: unknown };
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        /* non-JSON */
      }
      log.error("api_error", { path: "passport_image", status: res.status });
      throw new ApiError(res.status, detail);
    }
    return StatusResponse.parse(await res.json());
  },

  livenessChallenge(actions = 3) {
    return request(
      `/v1/liveness/challenge?actions=${actions}`,
      LivenessChallenge,
    );
  },

  submitBiometrics(
    sessionId: number,
    nonce: string,
    sub: BiometricSubmission,
    frames: LivenessFrame[],
  ) {
    return request(
      `/v1/sessions/${sessionId}/biometrics?liveness_nonce=${encodeURIComponent(nonce)}`,
      StatusResponse,
      { method: "POST", body: JSON.stringify({ sub, frames }) },
    );
  },

  sessionStatus(sessionId: number) {
    return request(`/v1/sessions/${sessionId}`, StatusResponse);
  },

  issueCredential(sessionId: number) {
    return request(
      `/v1/sessions/${sessionId}/credential`,
      CredentialResponse,
      { method: "POST" },
    );
  },
};
