"use client";

import { useEffect, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Camera, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { LivenessChallenge, StatusResponse } from "@/lib/schemas";
import { useLiveness } from "@/lib/liveness/useLiveness";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";

export function StepLiveness({
  sessionId,
  personSeed,
  onDone,
}: {
  sessionId: number;
  personSeed: string;
  onDone: (status: StatusResponse) => void;
}) {
  const challenge = useQuery({
    queryKey: ["liveness-challenge", sessionId],
    queryFn: () => api.livenessChallenge(3),
    staleTime: Infinity,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Liveness check</CardTitle>
        <CardDescription>
          We’ll ask you to perform a few quick actions on camera. Video stays on
          your device — only motion measurements are sent.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {challenge.isLoading && (
          <p className="text-sm text-muted-foreground">Preparing challenge…</p>
        )}
        {challenge.isError && (
          <Alert variant="destructive">
            <AlertDescription>
              Couldn’t start the liveness check. Please retry.
            </AlertDescription>
          </Alert>
        )}
        {challenge.data && (
          <LivenessRunner
            sessionId={sessionId}
            personSeed={personSeed}
            challenge={challenge.data}
            onDone={onDone}
          />
        )}
      </CardContent>
    </Card>
  );
}

function LivenessRunner({
  sessionId,
  personSeed,
  challenge,
  onDone,
}: {
  sessionId: number;
  personSeed: string;
  challenge: LivenessChallenge;
  onDone: (status: StatusResponse) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const liveness = useLiveness(videoRef, challenge.sequence);

  const submit = useMutation({
    mutationFn: (frames: typeof liveness.frames) =>
      api.submitBiometrics(
        sessionId,
        challenge.nonce,
        { selfie_ref: "webcam", person_seed: personSeed },
        frames,
      ),
    onSuccess: onDone,
  });

  // When the user finishes the sequence, send the feature timeline once.
  const submitted = useRef(false);
  useEffect(() => {
    if (liveness.status === "done" && !submitted.current) {
      submitted.current = true;
      submit.mutate(liveness.frames);
    }
  }, [liveness.status, liveness.frames, submit]);

  const submitting = submit.isPending;
  const submitError =
    submit.error instanceof ApiError ? submit.error.detail : null;

  return (
    <div className="space-y-4">
      <div className="relative mx-auto aspect-[4/3] w-full max-w-sm overflow-hidden rounded-lg border bg-muted">
        <video
          ref={videoRef}
          playsInline
          muted
          // Mirror the front camera so the preview feels natural.
          className="size-full -scale-x-100 object-cover"
        />
        {liveness.status === "idle" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Camera className="size-10 text-muted-foreground" aria-hidden />
          </div>
        )}
      </div>

      {liveness.status === "running" && (
        <div className="space-y-2">
          <Progress
            value={liveness.progress * 100}
            label="Liveness progress"
          />
          <p
            aria-live="assertive"
            className="text-center text-lg font-medium"
          >
            {liveness.instruction}
          </p>
        </div>
      )}

      {liveness.status === "error" && (
        <Alert variant="destructive">
          <AlertDescription>
            {liveness.error === "camera_permission_denied"
              ? "Camera access was blocked. Enable it in your browser settings and retry."
              : "We couldn’t access your camera. Check it isn’t in use and retry."}
          </AlertDescription>
        </Alert>
      )}

      {submitError && (
        <Alert variant="destructive">
          <AlertDescription>{submitError}</AlertDescription>
        </Alert>
      )}

      {(liveness.status === "idle" || liveness.status === "error") && (
        <Button type="button" className="w-full" onClick={liveness.start}>
          <Camera aria-hidden />
          {liveness.status === "error" ? "Retry camera" : "Start camera"}
        </Button>
      )}
      {liveness.status === "loading" && (
        <Button type="button" className="w-full" disabled>
          <Loader2 className="animate-spin" aria-hidden />
          Loading camera…
        </Button>
      )}
      {(liveness.status === "done" || submitting) && (
        <p
          aria-live="polite"
          className="text-center text-sm text-muted-foreground"
        >
          Checking your result…
        </p>
      )}
    </div>
  );
}
