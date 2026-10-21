"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";
import { LampToggle } from "@/components/ascii/lamp-toggle";
import { roman, UtcClock } from "./hud-effects";
import { Led } from "./led";
import { RockerSwitch } from "./rocker-switch";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/queue", label: "Queue" },
  { href: "/runs", label: "Runs" },
  { href: "/startups", label: "Startups" },
  { href: "/network", label: "Network" },
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
    <header className="sticky top-0 z-40 border-b border-emerald-600/60 bg-white/80 backdrop-blur-md dark:border-emerald-400/40 dark:bg-black/70">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-2.5">
        <Link
          href="/"
          className="flex items-center gap-2.5 leading-none focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-500"
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
          <span className="gilt font-fraktur text-[2.6rem] leading-[0.9] pb-1">
            Cali
          </span>
        </Link>
        <nav aria-label="Main" className="flex flex-wrap gap-x-1 gap-y-1">
          {LINKS.map((l, i) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`group relative px-3 py-1.5 font-display text-[11px] font-semibold uppercase tracking-[0.2em] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500 ${
                  active
                    ? "text-emerald-800 dark:text-emerald-300"
                    : "text-zinc-600 hover:text-emerald-800 dark:text-zinc-400 dark:hover:text-emerald-300"
                }`}
              >
                <span
                  aria-hidden
                  className="mr-1.5 font-hud text-[10px] tracking-widest opacity-60"
                >
                  {roman(i + 1)}
                </span>
                {l.label}
                <span
                  aria-hidden
                  className={`absolute inset-x-3 -bottom-px h-px origin-left bg-current transition-transform duration-300 ${
                    active
                      ? "scale-x-100 shadow-[0_0_8px] shadow-current"
                      : "scale-x-0 group-hover:scale-x-100"
                  }`}
                />
                {active && (
                  <span
                    aria-hidden
                    className="absolute -bottom-[5px] left-1/2 -translate-x-1/2 text-[8px] leading-none"
                  >
                    ◆
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-5">
          <span className="hidden sm:inline">
            <UtcClock />
          </span>
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
