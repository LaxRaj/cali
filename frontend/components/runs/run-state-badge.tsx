import { Led, type LedState } from "@/components/ui/led";
import type { RunStatus } from "@/lib/data";

const BADGE: Record<RunStatus, { led: LedState; text: string; label: string }> = {
  passed: { led: "ok", text: "PASS", label: "passed" },
  failed: { led: "fail", text: "FAIL", label: "failed quality gates" },
  // Groq's daily limit, not a quality problem: amber, not red.
  quota: { led: "warn", text: "QUOTA", label: "stopped by the Groq daily token limit" },
};

export function RunStateBadge({ state }: { state: RunStatus }) {
  const b = BADGE[state];
  return (
    <span className="inline-flex items-center gap-2">
      <Led state={b.led} label={b.label} />
      {b.text}
    </span>
  );
}
