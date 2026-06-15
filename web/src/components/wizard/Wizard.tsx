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
}

const INITIAL: State = {
  step: 0,
  sessionId: null,
  personSeed: "",
  result: null,
};

export function Wizard() {
  const [state, setState] = useState<State>(INITIAL);

  function restart() {
    setState(INITIAL);
  }

  return (
    <main id="main" className="mx-auto w-full max-w-md px-4 py-8">
      <h1 className="mb-6 text-center text-2xl font-bold">Verify your identity</h1>
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
          sessionId={state.sessionId}
          personSeed={state.personSeed}
          onDone={(result) => setState((s) => ({ ...s, result, step: 3 }))}
        />
      )}

      {state.step === 3 && state.sessionId !== null && state.result && (
        <StepResult
          sessionId={state.sessionId}
          status={state.result}
          onRetry={restart}
        />
      )}
    </main>
  );
}
