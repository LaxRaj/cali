"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LampToggle } from "@/components/ascii/lamp-toggle";
import type { RunStatus } from "@/lib/data";
import { UtcClock } from "./hud-effects";
import { Led } from "./led";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/queue", label: "Queue" },
  { href: "/runs", label: "Runs" },
  { href: "/startups", label: "Startups" },
  { href: "/network", label: "Network" },
];

const RUN_LED: Record<RunStatus, { state: "ok" | "fail" | "warn"; label: string }> = {
  passed: { state: "ok", label: "Last run passed" },
  failed: { state: "fail", label: "Last run failed" },
  // a Groq daily-limit stop is not a quality failure: amber, never "failed"
  quota: { state: "warn", label: "Last run stopped at the Groq quota" },
};

export function Nav({ lastRun }: { lastRun: RunStatus | null }) {
  const pathname = usePathname();
  const led = lastRun ? RUN_LED[lastRun] : { state: "idle" as const, label: "No runs yet" };
  return (
    <header className="sticky top-0 z-40 border-b border-zinc-900/15 bg-white/85 backdrop-blur dark:border-zinc-100/15 dark:bg-black/80">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3">
        <Link
          href="/"
          className="flex items-center gap-2.5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-rose-500"
        >
          <span title={led.label}>
            <Led state={led.state} label={led.label} />
          </span>
          <span className="serif text-3xl italic leading-none">cali</span>
        </Link>
        <nav aria-label="Main" className="flex flex-wrap gap-x-5 gap-y-1">
          {LINKS.map((l) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`border-b py-1 text-xs uppercase tracking-[0.14em] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-500 ${
                  active
                    ? "border-rose-500 text-zinc-900 dark:text-zinc-100"
                    : "border-transparent text-zinc-600 hover:border-zinc-900/30 hover:text-zinc-900 dark:text-zinc-400 dark:hover:border-zinc-100/30 dark:hover:text-zinc-100"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-5">
          <span className="text-[11px] sm:text-[13px]">
            <UtcClock />
          </span>
          <LampToggle />
        </div>
      </div>
    </header>
  );
}
