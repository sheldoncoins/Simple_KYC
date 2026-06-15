"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, Clock, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import type { StatusResponse } from "@/lib/schemas";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const REASONS: Record<string, string> = {
  liveness_failed: "We couldn’t confirm a live person on camera.",
  face_mismatch_selfie_vs_passport:
    "Your selfie didn’t match the passport photo.",
  passport_mrz_invalid: "The passport could not be validated.",
  duplicate_identity: "This identity is already verified with another account.",
  too_many_attempts: "You’ve reached the maximum number of attempts.",
  manual_review_rejected: "A reviewer could not approve this verification.",
};

/** Which wizard step a failure can be retried from, in the same session. A
 * reason absent here is terminal — retrying the same input won't change the
 * outcome (a true duplicate), or the session is locked out. */
const RETRY_STEP: Record<string, number> = {
  liveness_failed: 2,
  face_mismatch_selfie_vs_passport: 2,
  passport_mrz_invalid: 1,
};

export function StepResult({
  sessionId,
  status,
  onRetryStep,
  onRestart,
}: {
  sessionId: number;
  status: StatusResponse;
  onRetryStep: (step: number) => void;
  onRestart: () => void;
}) {
  const decision = status.decision;
  const approved = decision === "approve" || status.status === "approved";
  const inReview =
    decision === "review" || status.status === "pending_review";

  // Only fetch a credential once approved; the API returns the remaining limit.
  const credential = useQuery({
    queryKey: ["credential", sessionId],
    queryFn: () => api.issueCredential(sessionId),
    enabled: approved,
    retry: false,
  });

  if (approved) {
    return (
      <Card className="overflow-hidden animate-in fade-in-50 zoom-in-95">
        <CardHeader className="items-center text-center">
          <span className="mb-1 flex size-20 items-center justify-center rounded-full bg-success/10 animate-glow">
            <span className="flex size-14 items-center justify-center rounded-full bg-success text-success-foreground animate-pop-in">
              <Check className="size-8" strokeWidth={3} aria-hidden />
            </span>
          </span>
          <CardTitle className="text-2xl">You’re verified 🎉</CardTitle>
          <CardDescription>
            Your identity is confirmed and your limit is ready.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          {credential.data && (
            <div className="rounded-xl border bg-muted/50 p-4">
              <p className="text-xs text-muted-foreground">Remaining limit</p>
              <p className="text-2xl font-bold text-brand-gradient">
                ${credential.data.limit_remaining_usdc.toFixed(2)}{" "}
                <span className="text-base font-semibold">USDC</span>
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  if (inReview) {
    return (
      <Card className="animate-in fade-in-50 zoom-in-95">
        <CardHeader className="items-center text-center">
          <span className="mb-1 flex size-16 items-center justify-center rounded-full bg-muted animate-pop-in">
            <Clock className="size-8 text-muted-foreground" aria-hidden />
          </span>
          <CardTitle>In review</CardTitle>
          <CardDescription>
            Your verification needs a quick manual review. We’ll update you
            shortly — no action needed.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const reason = status.reject_reason ?? "";
  const retryStep = RETRY_STEP[reason];

  return (
    <Card className="animate-in fade-in-50 zoom-in-95">
      <CardHeader className="items-center text-center">
        <span className="mb-1 flex size-16 items-center justify-center rounded-full bg-destructive/10 animate-pop-in">
          <XCircle className="size-8 text-destructive" aria-hidden />
        </span>
        <CardTitle>Verification didn’t pass</CardTitle>
        <CardDescription>
          {REASONS[reason] ?? "We couldn’t complete your verification."}
          {retryStep !== undefined && (
            <>
              {" "}
              {retryStep === 1
                ? "Re-upload a clear photo of the passport page and try again."
                : "Find good lighting, keep your whole face in frame, and try again."}
            </>
          )}
        </CardDescription>
      </CardHeader>
      <CardFooter>
        {retryStep !== undefined ? (
          // Retryable: go back to just the failed stage, same session.
          <Button
            type="button"
            className="w-full"
            onClick={() => onRetryStep(retryStep)}
          >
            Try again
          </Button>
        ) : (
          // Terminal (e.g. a true duplicate, or out of attempts): only a fresh
          // start is possible.
          <Button
            type="button"
            variant="secondary"
            className="w-full"
            onClick={onRestart}
          >
            Start over
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
