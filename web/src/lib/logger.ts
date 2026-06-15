/**
 * Minimal client logger that refuses to emit PII.
 *
 * The verification flow handles passport/MRZ data, phone, email and raw camera
 * frames. None of that may reach the console or any sink. `log` accepts only a
 * short event name plus an optional bag of *safe* metadata (ids, step names,
 * counts, booleans) and strips anything that looks like PII as a backstop.
 */
const PII_KEYS = new Set([
  "phone",
  "email",
  "mrz",
  "mrz_line1",
  "mrz_line2",
  "name",
  "given_name",
  "surname",
  "dob",
  "passport",
  "selfie",
  "frames",
  "image",
  "credential",
]);

type SafeValue = string | number | boolean | null | undefined;

function sanitize(meta: Record<string, SafeValue>): Record<string, SafeValue> {
  const out: Record<string, SafeValue> = {};
  for (const [key, value] of Object.entries(meta)) {
    if (PII_KEYS.has(key.toLowerCase())) continue;
    out[key] = value;
  }
  return out;
}

export const log = {
  event(name: string, meta: Record<string, SafeValue> = {}) {
    if (process.env.NODE_ENV !== "production") {
      console.info(`[kyc] ${name}`, sanitize(meta));
    }
  },
  error(name: string, meta: Record<string, SafeValue> = {}) {
    console.error(`[kyc] ${name}`, sanitize(meta));
  },
};
