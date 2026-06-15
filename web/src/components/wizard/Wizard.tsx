"use client";

import { useState } from "react";
import type { StatusResponse } from "@/lib/schemas";
import { Stepper } from "./Stepper";
import { StepStart } from "./StepStart";
import { StepPassport } from "./StepPassport";
import { StepLiveness } from "./StepLiveness";
import { StepResult } from "./StepResult";

/** A random per-session "person" handle. The reference API simulates 1:1 face
 * matching with a shared seed across passport + selfie; real image-based
 * matching replaces this. It is not PII and never logged. */
function newPersonSeed(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

interface State {
  step: number;
  sessionId: number | null;
  personSeed: string;
  result: StatusResponse | null;
  /** Bumped on every retry so the liveness step remounts and pulls a fresh,
   * single-use challenge instead of replaying a consumed nonce. */
  attempt: number;
}

const INITIAL: State = {
  step: 0,
  sessionId: null,
  personSeed: "",
  result: null,
  attempt: 0,
};

export function Wizard() {
  const [state, setState] = useState<State>(INITIAL);

  // Full reset: brand-new session (used only when there's nothing to salvage).
  function restart() {
    setState(INITIAL);
  }

  // In-session retry: jump back to the failed stage, keeping the same session
  // and person handle so the user only redoes what failed.
  function retryStep(step: number) {
    setState((s) => ({ ...s, step, result: null, attempt: s.attempt + 1 }));
  }

  return (
    <main id="main" className="safe-bottom mx-auto w-full max-w-md px-4 pb-10 pt-6">
      <h1 className="text-center text-2xl font-bold tracking-tight">
        <span className="text-brand-gradient">Verify your identity</span>
      </h1>
      <p className="mb-6 mt-1 text-center text-sm text-muted-foreground">
        Quick, secure, and private — about a minute.
      </p>
      <Stepper current={state.step} />

      {state.step === 0 && (
        <StepStart
          onDone={(sessionId) =>
            setState((s) => ({
              ...s,
              sessionId,
              personSeed: newPersonSeed(),
              step: 1,
            }))
          }
        />
      )}

      {state.step === 1 && state.sessionId !== null && (
        <StepPassport
          sessionId={state.sessionId}
          personSeed={state.personSeed}
          onDone={() => setState((s) => ({ ...s, step: 2 }))}
        />
      )}

      {state.step === 2 && state.sessionId !== null && (
        <StepLiveness
          key={state.attempt}
          sessionId={state.sessionId}
          personSeed={state.personSeed}
          attempt={state.attempt}
          onDone={(result) => setState((s) => ({ ...s, result, step: 3 }))}
        />
      )}

      {state.step === 3 && state.sessionId !== null && state.result && (
        <StepResult
          sessionId={state.sessionId}
          status={state.result}
          onRetryStep={retryStep}
          onRestart={restart}
        />
      )}
    </main>
  );
}
