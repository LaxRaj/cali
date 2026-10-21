"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LampToggle } from "@/components/ascii/lamp-toggle";
import { UtcClock } from "./hud-effects";
import { Led } from "./led";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/queue", label: "Queue" },
  { href: "/runs", label: "Runs" },
  { href: "/startups", label: "Startups" },
  { href: "/network", label: "Network" },
];

export function Nav({ lastRunPassed }: { lastRunPassed: boolean | null }) {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-zinc-900/15 bg-white/85 backdrop-blur dark:border-zinc-100/15 dark:bg-black/80">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3">
        <Link
          href="/"
          className="flex items-center gap-2.5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-rose-500"
        >
          <Led
            state={
              lastRunPassed === null ? "idle" : lastRunPassed ? "ok" : "fail"
            }
            label={
              lastRunPassed === null
                ? "No runs yet"
                : lastRunPassed
                  ? "Last run passed"
                  : "Last run failed"
            }
          />
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
          <span className="hidden sm:inline">
            <UtcClock />
          </span>
          <LampToggle />
        </div>
      </div>
    </header>
  );
}
