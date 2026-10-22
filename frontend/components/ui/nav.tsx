"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";
import { LampToggle } from "@/components/ascii/lamp-toggle";
import { Led } from "./led";
import { RockerSwitch } from "./rocker-switch";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/queue", label: "Queue" },
  { href: "/outreach", label: "Outreach" },
  { href: "/startups", label: "Startups" },
  { href: "/network", label: "Network" },
  { href: "/runs", label: "Runs" },
];

function subscribe(cb: () => void) {
  const mo = new MutationObserver(cb);
  mo.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-crt"],
  });
  return () => mo.disconnect();
}

export function Nav({ lastRunPassed }: { lastRunPassed: boolean | null }) {
  const pathname = usePathname();
  const crt = useSyncExternalStore(
    subscribe,
    () => document.documentElement.getAttribute("data-crt") !== "off",
    () => true,
  );

  function setCrt(on: boolean) {
    if (on) document.documentElement.removeAttribute("data-crt");
    else document.documentElement.setAttribute("data-crt", "off");
    try {
      localStorage.setItem("cali-crt", on ? "on" : "off");
    } catch {}
  }

  return (
    <header className="border-b-2 border-zinc-900 bg-rose-100 dark:border-emerald-500/60 dark:bg-black">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2">
        <Link
          href="/"
          className="glow flex items-center gap-2 font-display text-3xl leading-none tracking-widest"
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
          cali
        </Link>
        <nav aria-label="Main" className="flex flex-wrap gap-1">
          {LINKS.map((l) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`border-2 px-3 py-0.5 text-xs font-semibold uppercase tracking-wide focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500 ${
                  active
                    ? "border-zinc-900 bg-white shadow-[2px_2px_0_0] shadow-zinc-900 dark:border-emerald-400 dark:bg-emerald-950 dark:shadow-emerald-400/50"
                    : "border-transparent hover:border-zinc-900/40 dark:hover:border-emerald-400/40"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-4">
          <span className="hidden dark:inline-flex">
            <RockerSwitch
              checked={crt}
              onChange={setCrt}
              label="CRT scanlines"
            />
          </span>
          <LampToggle />
        </div>
      </div>
    </header>
  );
}
