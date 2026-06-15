"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
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
  manual_review_rejected: "A reviewer could not approve this verification.",
};

export function StepResult({
  sessionId,
  status,
  onRetry,
}: {
  sessionId: number;
  status: StatusResponse;
  onRetry: () => void;
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
      <Card>
        <CardHeader className="items-center text-center">
          <CheckCircle2 className="size-12 text-success" aria-hidden />
          <CardTitle>You’re verified</CardTitle>
          <CardDescription>
            Your identity is confirmed and your limit is ready.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          {credential.data && (
            <p className="text-sm text-muted-foreground">
              Remaining limit:{" "}
              <span className="font-medium text-foreground">
                ${credential.data.limit_remaining_usdc.toFixed(2)} USDC
              </span>
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  if (inReview) {
    return (
      <Card>
        <CardHeader className="items-center text-center">
          <Clock className="size-12 text-muted-foreground" aria-hidden />
          <CardTitle>In review</CardTitle>
          <CardDescription>
            Your verification needs a quick manual review. We’ll update you
            shortly — no action needed.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="items-center text-center">
        <XCircle className="size-12 text-destructive" aria-hidden />
        <CardTitle>Verification didn’t pass</CardTitle>
        <CardDescription>
          {(status.reject_reason && REASONS[status.reject_reason]) ??
            "We couldn’t complete your verification."}
        </CardDescription>
      </CardHeader>
      <CardFooter>
        <Button type="button" className="w-full" onClick={onRetry}>
          Try again
        </Button>
      </CardFooter>
    </Card>
  );
}
