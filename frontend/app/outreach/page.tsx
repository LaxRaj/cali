import { Tracker } from "@/components/outreach/tracker";
import { readProfiles } from "@/lib/data";

export const metadata = { title: "Outreach — cali" };

export default function OutreachPage() {
  const profiles = readProfiles();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="glow font-display text-5xl uppercase tracking-wider">
          Outreach tracker
        </h1>
        <p className="mt-1 text-xs text-zinc-700 dark:text-zinc-300">
          Every lead you have written to, by stage, with the next follow-up date.
          Events you log here are kept in this browser until you export them.
        </p>
      </div>
      <Tracker profiles={profiles} />
    </div>
  );
}
