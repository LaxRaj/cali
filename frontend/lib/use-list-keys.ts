"use client";

import { useEffect, useState } from "react";

export type ListKeyHandlers = {
  /** o / Enter on the active row */
  onOpen?: (index: number) => void;
  /** Extra single-key actions on the active row, e.g. { e: email, c: copy }. */
  actions?: Record<string, (index: number) => void>;
  /** "/" focuses this element (the search box). */
  searchRef?: React.RefObject<HTMLInputElement | null>;
};

function typing(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

/**
 * Keyboard triage for a list (Harmonic/Superhuman style): j/k or arrows move, o/Enter opens, extra letters act on the
 * active row, "/" jumps to search, "?" toggles the help panel, Esc closes it. Rows carry data-row={index}.
 */
export function useListKeys(count: number, h: ListKeyHandlers = {}) {
  const [active, setActive] = useState(-1);
  const [help, setHelp] = useState(false);
  const current = count === 0 ? -1 : Math.min(active, count - 1);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (typing(e.target)) {
        if (e.key === "Escape") (e.target as HTMLElement).blur();
        return;
      }
      const move = (to: number) => {
        e.preventDefault();
        const i = Math.max(0, Math.min(count - 1, to));
        setActive(i);
        const row = document.querySelector(`[data-row="${i}"]`) as HTMLElement | null;
        row?.scrollIntoView?.({ block: "nearest" });
      };
      if (e.key === "?") {
        e.preventDefault();
        setHelp((x) => !x);
      } else if (e.key === "Escape") setHelp(false);
      else if (count === 0) return;
      else if (e.key === "j" || e.key === "ArrowDown") move(current + 1);
      else if (e.key === "k" || e.key === "ArrowUp") move(current < 0 ? 0 : current - 1);
      else if (e.key === "/" && h.searchRef?.current) {
        e.preventDefault();
        h.searchRef.current.focus();
      } else if ((e.key === "o" || e.key === "Enter") && current >= 0 && h.onOpen) {
        e.preventDefault();
        h.onOpen(current);
      } else if (current >= 0 && h.actions?.[e.key]) {
        e.preventDefault();
        h.actions[e.key](current);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [count, current, h]);

  return { active: current, setActive, help, setHelp };
}
