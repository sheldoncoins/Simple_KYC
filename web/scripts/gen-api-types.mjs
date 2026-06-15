#!/usr/bin/env node
/**
 * Snapshot the API's OpenAPI schema so the hand-authored Zod schemas in
 * src/lib/schemas.ts can be diffed against the server and kept in sync.
 *
 *   npm run gen:api            # uses NEXT_PUBLIC_API_BASE_URL or localhost:8000
 *
 * For full Zod codegen, point a generator (e.g. openapi-zod-client) at the
 * written openapi.json; this script keeps the dependency-free baseline.
 */
import { writeFile } from "node:fs/promises";

const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

const res = await fetch(`${base}/openapi.json`);
if (!res.ok) {
  console.error(`Failed to fetch ${base}/openapi.json: ${res.status}`);
  process.exit(1);
}
const spec = await res.json();
await writeFile("src/lib/openapi.json", JSON.stringify(spec, null, 2));
console.log(
  `Wrote src/lib/openapi.json (${Object.keys(spec.paths ?? {}).length} paths). ` +
    "Reconcile src/lib/schemas.ts against it.",
);
