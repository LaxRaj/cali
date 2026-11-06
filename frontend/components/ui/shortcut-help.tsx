"use client";

export function ShortcutHelp({
  open,
  onClose,
  keys,
}: {
  open: boolean;
  onClose: () => void;
  keys: [string, string][];
}) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-label="Keyboard shortcuts"
      className="fixed bottom-4 right-4 z-50 w-72 border border-zinc-900/40 bg-white p-3 text-xs shadow-lg dark:border-zinc-100/40 dark:bg-black"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="font-semibold uppercase tracking-widest">Shortcuts</span>
        <button type="button" onClick={onClose} className="underline" aria-label="Close shortcuts">
          esc
        </button>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        {keys.map(([k, what]) => (
          <div key={k} className="contents">
            <dt>
              <kbd className="border border-zinc-900/30 px-1 dark:border-zinc-100/30">{k}</kbd>
            </dt>
            <dd className="text-zinc-700 dark:text-zinc-300">{what}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
