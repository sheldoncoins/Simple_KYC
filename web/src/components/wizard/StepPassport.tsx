"use client";

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Upload } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { log } from "@/lib/logger";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";

const DEV_MRZ = process.env.NEXT_PUBLIC_DEV_MRZ === "1";

export function StepPassport({
  sessionId,
  personSeed,
  onDone,
}: {
  sessionId: number;
  personSeed: string;
  onDone: () => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [mrz, setMrz] = useState("");

  const checkResult = (res: StatusResponse) => {
    const valid = res.signals?.mrz_valid;
    log.event("passport_submitted", { mrz_valid: Boolean(valid) });
    if (valid) onDone();
  };

  const imageMutation = useMutation({
    mutationFn: async () => {
      const file = fileRef.current?.files?.[0];
      if (!file) throw new ApiError(0, "no_file_selected");
      return api.submitPassportImage(sessionId, file, personSeed);
    },
    onSuccess: checkResult,
  });

  const mrzMutation = useMutation({
    mutationFn: async () => {
      const [line1 = "", line2 = ""] = mrz.split("\n");
      return api.submitPassport(sessionId, {
        id_type: "passport",
        mrz_line1: line1.trim(),
        mrz_line2: line2.trim(),
        person_seed: personSeed,
      });
    },
    onSuccess: checkResult,
  });

  const pending = imageMutation.isPending || mrzMutation.isPending;
  const result = imageMutation.data ?? mrzMutation.data;
  const apiError =
    imageMutation.error instanceof ApiError
      ? imageMutation.error.detail
      : mrzMutation.error instanceof ApiError
        ? mrzMutation.error.detail
        : null;
  const mrzInvalid = result && !result.signals?.mrz_valid;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Passport</CardTitle>
        <CardDescription>
          Capture or upload the photo page of your passport. We read the
          machine-readable zone (MRZ) and check it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          aria-label="Passport image"
          onChange={(e) => setFileName(e.target.files?.[0]?.name ?? null)}
        />
        <Button
          type="button"
          variant="outline"
          className="h-28 w-full flex-col border-dashed"
          onClick={() => fileRef.current?.click()}
        >
          <Upload aria-hidden />
          <span>{fileName ? "Change image" : "Capture or upload passport"}</span>
          {fileName && (
            <span className="text-xs text-muted-foreground">{fileName}</span>
          )}
        </Button>

        {DEV_MRZ && (
          <div className="space-y-1.5 rounded-md border border-dashed p-3">
            <Label htmlFor="mrz">Developer: MRZ lines (two lines)</Label>
            <textarea
              id="mrz"
              value={mrz}
              onChange={(e) => setMrz(e.target.value)}
              rows={2}
              spellCheck={false}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={pending || !mrz.trim()}
              onClick={() => mrzMutation.mutate()}
            >
              Submit MRZ
            </Button>
          </div>
        )}

        {mrzInvalid && (
          <Alert variant="destructive">
            <AlertDescription>
              We couldn’t read a valid MRZ. Make sure the whole passport page is
              in frame, well lit, and try again.
            </AlertDescription>
          </Alert>
        )}
        {apiError && (
          <Alert variant="destructive">
            <AlertDescription>{apiError}</AlertDescription>
          </Alert>
        )}
      </CardContent>
      <CardFooter>
        <Button
          type="button"
          className="w-full"
          disabled={pending || !fileName}
          onClick={() => imageMutation.mutate()}
        >
          {pending && <Loader2 className="animate-spin" aria-hidden />}
          Read passport
        </Button>
      </CardFooter>
    </Card>
  );
}
