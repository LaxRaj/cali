import { Empty } from "@/components/ascii/art";
import { StartupExplorer } from "@/components/startups/startup-explorer";
import { Panel } from "@/components/ui/panel";
import { readProfiles } from "@/lib/data";

export const metadata = { title: "Startups — cali" };

export default function StartupsPage() {
  const profiles = readProfiles();
  return (
    <div className="space-y-6">
      <h1 className="font-display text-4xl sm:text-6xl">
        Startups
      </h1>
      {profiles.length === 0 ? (
        <Panel title="Profiles" tone="amber">
          <Empty art="computer" title="No startups stored yet">
            Profiles appear after the first run that passes its quality gates.
          </Empty>
        </Panel>
      ) : (
        <StartupExplorer profiles={profiles} />
      )}
    </div>
  );
}
