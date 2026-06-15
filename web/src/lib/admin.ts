/**
 * Staff (admin console) API client. Every request carries the staff key in the
 * `X-Admin-Key` header and every response is Zod-validated. The key is supplied
 * by the caller (held in session state) and is never logged.
 */
import { ApiError, BASE_URL } from "./api";
import { log } from "./logger";
import {
  AuditEntry,
  MetricsSummary,
  ReviewListItem,
  StatusResponse,
} from "./schemas";
import { z } from "zod";

async function adminRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  key: string,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Key": key,
        ...(init?.headers ?? {}),
      },
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
      /* non-JSON */
    }
    log.error("admin_api_error", { path, status: res.status });
    throw new ApiError(res.status, detail);
  }
  return schema.parse(await res.json());
}

export const adminApi = {
  reviewQueue(key: string) {
    return adminRequest("/v1/review", z.array(ReviewListItem), key);
  },
  resolveReview(
    key: string,
    itemId: number,
    resolution: "approve" | "reject",
    reviewer: string,
  ) {
    return adminRequest(`/v1/review/${itemId}`, StatusResponse, key, {
      method: "POST",
      body: JSON.stringify({ resolution, reviewer }),
    });
  },
  auditLog(key: string, limit = 50) {
    return adminRequest(`/v1/audit?limit=${limit}`, z.array(AuditEntry), key);
  },
  metrics(key: string) {
    return adminRequest("/v1/metrics/summary", MetricsSummary, key);
  },
};
