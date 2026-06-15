# KYC Verification Wizard (Phase 4)

Mobile-first applicant verification flow for the Simple KYC server. Next.js
(App Router) + TypeScript + Tailwind + shadcn-style UI, talking to the existing
`/v1` API.

## Flow

1. **Start** — country (7 markets) + wallet → `POST /v1/onboard`.
2. **Passport** — capture/upload the passport image → `POST /v1/sessions/{id}/passport/image`; the server reads + validates the MRZ and the result shows inline.
3. **Liveness** — fetch a challenge (`GET /v1/liveness/challenge`), run **MediaPipe Tasks `FaceLandmarker`** in the browser, guide the user through the randomized actions with live feedback, and send **only the feature timeline** (`ear`/`yaw`/`mar` per frame) to `POST /v1/sessions/{id}/biometrics`. Raw video never leaves the device.
4. **Result** — approved / in review / rejected, with a clear reason and a retry path.

## Run

```bash
cp .env.example .env.local        # set NEXT_PUBLIC_API_BASE_URL (the API)
npm install
npm run dev                       # http://localhost:3000

npm run typecheck && npm run lint
npm run build
```

The API must allow the web origin (CORS) and, for the liveness step, the page
must be served over HTTPS or localhost (camera access requirement).

### Local end-to-end note

The dev MRZ reader (`KYC_MRZ_READER=text`) reads MRZ **text**, not a photo. For
local testing set `NEXT_PUBLIC_DEV_MRZ=1` to reveal a developer field to paste
the two MRZ lines (generate them from the server's `run_demo`/`mrz_demo`). With a
real OCR backend (`KYC_MRZ_READER=ocr`) the image-capture path works directly.

## Staff review console (`/admin`)

`/admin` is the authenticated staff console: sign in with a staff key
(`X-Admin-Key`, held in `sessionStorage`), then work the **review queue**
(side-by-side signals → approve/reject), view a **metrics dashboard**
(approval/review/reject + dedup/liveness rates, per-country), and read the
**audit log**. It calls the staff-only `/v1/review`, `/v1/audit` and
`/v1/metrics/summary` endpoints. The console is `noindex`.

## Conventions

- **Zod at the boundary** (`src/lib/schemas.ts`) — every API response is parsed;
  `npm run gen:api` snapshots the server's `/openapi.json` to keep them in sync.
- **No PII in logs** — `src/lib/logger.ts` only emits safe metadata and strips
  PII keys; MRZ, frames, phone/email are never logged.
- **Accessibility** — labelled controls, a skip link, `aria-live` step guidance,
  visible focus rings, reduced-motion support, mobile-first layout (WCAG AA aim).

## What's real vs. stubbed

- **Real:** the four-step flow against `/v1`, in-browser MediaPipe liveness with
  feature extraction matching the server's thresholds, Zod-validated API client.
- **To wire for production:** the liveness thresholds (`faceLandmarker.ts`) need
  tuning against real device output; the passport step needs the OCR reader
  backend for real photos; `person_seed` is a reference-API matching simulation
  that real selfie/passport image matching replaces; i18n is EN-only scaffold
  (ES/PT/HI to add).
