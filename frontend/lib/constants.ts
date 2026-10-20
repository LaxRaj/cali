// Browser-safe constants (lib/data.ts reads files and must stay server-only).

/** Groq free tier, tokens per day for ONE key. Runs record the real multi-key budget in `token_budget`. */
export const TOKEN_BUDGET = 200_000;
