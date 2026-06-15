"use client";

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { FileText, ImageIcon, Loader2, UploadCloud } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { pdfFirstPageToJpeg } from "@/lib/pdf";
import { log } from "@/lib/logger";
import type { StatusResponse } from "@/lib/schemas";
import { cn } from "@/lib/utils";
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
import { PrivacyNote } from "@/components/ui/privacy-note";
import { PassportExample } from "./PassportExample";

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
  const [blob, setBlob] = useState<Blob | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [converting, setConverting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [mrz, setMrz] = useState("");

  async function accept(file: File) {
    setLocalError(null);
    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    const isImage = file.type.startsWith("image/");
    if (!isPdf && !isImage) {
      setLocalError("Please choose an image (JPG/PNG) or a PDF.");
      return;
    }
    try {
      let out: Blob = file;
      if (isPdf) {
        setConverting(true);
        out = await pdfFirstPageToJpeg(file); // render page 1 in-browser
      }
      if (preview) URL.revokeObjectURL(preview);
      setBlob(out);
      setFileName(file.name);
      setPreview(URL.createObjectURL(out));
    } catch {
      setLocalError("We couldn’t read that file. Try a clear photo or PDF of the page.");
    } finally {
      setConverting(false);
    }
  }

  const checkResult = (res: StatusResponse) => {
    const valid = res.signals?.mrz_valid;
    log.event("passport_submitted", { mrz_valid: Boolean(valid) });
    if (valid) onDone();
  };

  const imageMutation = useMutation({
    mutationFn: async () => {
      if (!blob) throw new ApiError(0, "no_file_selected");
      return api.submitPassportImage(sessionId, blob, personSeed);
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
    <Card className="animate-in fade-in-50 slide-in-from-bottom-2">
      <CardHeader>
        <CardTitle>Passport</CardTitle>
        <CardDescription>
          Add the photo page of your passport. We read the machine-readable zone
          (MRZ) and check it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <PassportExample />

        <input
          ref={fileRef}
          type="file"
          accept="image/*,application/pdf"
          className="sr-only"
          aria-label="Passport image or PDF"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void accept(f);
          }}
        />

        {/* Drag-and-drop zone */}
        <div
          role="button"
          tabIndex={0}
          aria-label="Drag and drop your passport image or PDF, or click to choose a file"
          onClick={() => fileRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") fileRef.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) void accept(f);
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            dragging ? "border-primary bg-primary/5" : "border-input hover:bg-accent/40",
          )}
        >
          {converting ? (
            <>
              <Loader2 className="size-7 animate-spin text-primary" aria-hidden />
              <span className="text-sm">Converting PDF…</span>
            </>
          ) : preview ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview}
                alt="Selected passport preview"
                className="max-h-36 rounded-md border object-contain"
              />
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                {fileName?.toLowerCase().endsWith(".pdf") ? (
                  <FileText className="size-3.5" aria-hidden />
                ) : (
                  <ImageIcon className="size-3.5" aria-hidden />
                )}
                {fileName} · tap to change
              </span>
            </>
          ) : (
            <>
              <UploadCloud className="size-8 text-muted-foreground" aria-hidden />
              <span className="text-sm font-medium">
                Drag &amp; drop, or tap to upload
              </span>
              <span className="text-xs text-muted-foreground">
                JPG, PNG or PDF · or use your camera
              </span>
            </>
          )}
        </div>

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

        {localError && (
          <Alert variant="destructive">
            <AlertDescription>{localError}</AlertDescription>
          </Alert>
        )}
        {mrzInvalid && (
          <Alert variant="destructive">
            <AlertDescription>
              We couldn’t read a valid MRZ. Make sure the whole page is in frame,
              well lit, and try again.
            </AlertDescription>
          </Alert>
        )}
        {apiError && (
          <Alert variant="destructive">
            <AlertDescription>{apiError}</AlertDescription>
          </Alert>
        )}

        <PrivacyNote>
          Your passport is encrypted, used only to verify you, and deleted after a
          short retention window — only an anonymous template is kept.
        </PrivacyNote>
      </CardContent>
      <CardFooter>
        <Button
          type="button"
          className="w-full"
          disabled={pending || converting || !blob}
          onClick={() => imageMutation.mutate()}
        >
          {pending && <Loader2 className="animate-spin" aria-hidden />}
          Read passport
        </Button>
      </CardFooter>
    </Card>
  );
}
