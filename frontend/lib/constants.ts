// Browser-safe constants (lib/data.ts reads files and must stay server-only).

/** Groq free tier, tokens per day for ONE key. Runs record the real multi-key budget in `token_budget`. */
export const TOKEN_BUDGET = 200_000;

/** Run telemetry was added at this moment. Scout executions before it (5 on 2026-10-20) left no run record. */
export const RECORDS_START = "2026-10-20T03:15:00Z";
