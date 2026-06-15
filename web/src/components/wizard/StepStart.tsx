"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { COUNTRIES } from "@/lib/countries";
import { OnboardRequest } from "@/lib/schemas";
import { log } from "@/lib/logger";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { PrivacyNote } from "@/components/ui/privacy-note";

export function StepStart({
  onDone,
}: {
  onDone: (sessionId: number, country: string) => void;
}) {
  const [country, setCountry] = useState("");
  const [wallet, setWallet] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.onboard({ wallet_pubkey: wallet, country }),
    onSuccess: (res) => {
      log.event("onboarded", { session_id: res.session_id });
      onDone(res.session_id, country);
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = OnboardRequest.safeParse({ wallet_pubkey: wallet, country });
    if (!parsed.success) {
      setFieldError("Enter a 2-letter country and a wallet address (8–128 chars).");
      return;
    }
    setFieldError(null);
    mutation.mutate();
  }

  const error =
    fieldError ??
    (mutation.error instanceof ApiError ? mutation.error.detail : null);

  return (
    <Card className="animate-in fade-in-50 slide-in-from-bottom-2">
      <CardHeader>
        <CardTitle>Start verification</CardTitle>
        <CardDescription>
          Choose your country and connect the wallet you’ll verify.
        </CardDescription>
      </CardHeader>
      <form onSubmit={submit} noValidate>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="country">Country</Label>
            <select
              id="country"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              required
              className="flex h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <option value="" disabled>
                Select a country
              </option>
              {COUNTRIES.map((c) => (
                <option key={c.iso} value={c.iso}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wallet">Wallet address</Label>
            <Input
              id="wallet"
              value={wallet}
              onChange={(e) => setWallet(e.target.value)}
              autoComplete="off"
              placeholder="0x…"
              aria-describedby={error ? "start-error" : undefined}
              required
            />
          </div>
          {error && (
            <Alert variant="destructive" id="start-error">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <PrivacyNote>
            We verify you once and keep no raw documents — your passport and
            selfie are deleted after a short window; only an anonymous,
            non-reversible template remains.
          </PrivacyNote>
        </CardContent>
        <CardFooter>
          <Button type="submit" disabled={mutation.isPending} className="w-full">
            {mutation.isPending && <Loader2 className="animate-spin" aria-hidden />}
            Continue
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
