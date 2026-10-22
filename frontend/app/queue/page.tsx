import { Empty } from "@/components/ascii/art";
import { QueueView } from "@/components/queue/queue-view";
import { Panel } from "@/components/ui/panel";
import { readProfiles } from "@/lib/data";

export const metadata = { title: "Queue — cali" };

export default function QueuePage() {
  const profiles = readProfiles();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="glow font-display text-5xl uppercase tracking-wider">
          Action queue
        </h1>
        <p className="mt-1 text-xs text-zinc-700 dark:text-zinc-300">
          What to do next with each lead. Log a send, a reply or a pass right
          here and the lead moves to the right bucket; follow-ups come due 7
          days after each touch.
        </p>
      </div>
      {profiles.length === 0 ? (
        <Panel title="Queue" tone="amber">
          <Empty art="computer" title="No leads yet">
            The queue fills after the first run that passes its quality gates.
          </Empty>
        </Panel>
      ) : (
        <QueueView profiles={profiles} />
      )}
    </div>
  );
}
