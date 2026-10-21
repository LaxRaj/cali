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
        <h1 className="font-display text-6xl">
          Action queue
        </h1>
        <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
          What to do next with each lead and how urgently. Record results with{" "}
          <code>
            uv run python outcomes.py mark &lt;company&gt;
            contacted|replied|passed
          </code>
          .
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
