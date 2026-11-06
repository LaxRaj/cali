import { Empty } from "@/components/ascii/art";
import { RetroLink } from "@/components/ui/retro-button";

export default function NotFound() {
  return (
    <div className="space-y-4">
      <h1 className="font-display text-4xl sm:text-6xl">Not found</h1>
      <Empty art="floppy" title="Nothing at this address">
        The run or startup may be older than the current data, or its name changed. Startups and runs are rebuilt from
        backend/data on every build.
      </Empty>
      <div className="flex gap-2">
        <RetroLink href="/" tone="emerald">
          Overview
        </RetroLink>
        <RetroLink href="/startups" tone="sky">
          Startups
        </RetroLink>
        <RetroLink href="/runs" tone="violet">
          Runs
        </RetroLink>
      </div>
    </div>
  );
}
