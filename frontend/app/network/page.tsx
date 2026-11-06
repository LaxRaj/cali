import Link from "next/link";
import { Empty } from "@/components/ascii/art";
import { NetworkGraph } from "@/components/charts/network-graph";
import { Panel } from "@/components/ui/panel";
import { Stat } from "@/components/ui/stat";
import { readGraph, readProfiles } from "@/lib/data";
import { humanize } from "@/lib/format";

export const metadata = { title: "Network — cali" };

export default function NetworkPage() {
  const graph = readGraph();
  // graph node ids are lower-cased company names; profiles carry the page slug
  const slugs = Object.fromEntries(readProfiles().map((p) => [p.company_name.trim().toLowerCase(), p.slug]));
  const count = (t: string) => graph.nodes.filter((n) => n.type === t).length;
  const rels = Object.entries(
    graph.edges.reduce<Record<string, number>>((acc, e) => ({ ...acc, [e.rel]: (acc[e.rel] ?? 0) + 1 }), {}),
  ).sort((a, b) => b[1] - a[1]);
  const focusHref = (name: string) => `/network?focus=${encodeURIComponent(name.trim().toLowerCase())}`;

  return (
    <div className="space-y-6">
      <h1 className="font-display text-4xl sm:text-6xl">Connections</h1>
      {graph.nodes.length === 0 ? (
        <Panel title="Network" tone="amber">
          <Empty art="radio" title="No connections mapped yet">
            Founders, investors and their links show up here once a run is stored.
          </Empty>
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Startups" value={count("startup")} tone="emerald" />
            <Stat label="People" value={count("person")} tone="sky" />
            <Stat label="Orgs / investors" value={count("org")} tone="amber" />
            <Stat label="Links" value={graph.edges.length} tone="violet" />
          </div>
          <NetworkGraph graph={graph} slugs={slugs} />
          {(graph.investors?.length ?? 0) > 0 && (
            <Panel title="Investors backing several startups" tone="emerald">
              <ul className="space-y-2">
                {graph.investors?.map((inv) => (
                  <li key={inv.investor}>
                    <Link href={focusHref(inv.investor)} className="font-semibold underline underline-offset-2 hover:no-underline">
                      {inv.investor}
                    </Link>{" "}
                    <span className="tabular-nums text-zinc-600 dark:text-zinc-400">×{inv.count}</span>:{" "}
                    {inv.companies.map((c, i) => (
                      <span key={c}>
                        {i > 0 && ", "}
                        {slugs[c.trim().toLowerCase()] ? (
                          <Link href={`/startups/${slugs[c.trim().toLowerCase()]}`} className="underline underline-offset-2">
                            {c}
                          </Link>
                        ) : (
                          c
                        )}
                      </span>
                    ))}
                    {inv.co_investors.length > 0 && (
                      <p className="text-xs text-zinc-600 dark:text-zinc-400">
                        co-invests with {inv.co_investors.map((c) => `${c.name} (${c.shared})`).join(", ")}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          <Panel title="Link types" tone="violet">
            <ul className="flex flex-wrap gap-x-6 gap-y-1">
              {rels.map(([rel, n]) => (
                <li key={rel}>
                  <Link href={`/network?rel=${encodeURIComponent(rel)}`} className="underline-offset-2 hover:underline">
                    {humanize(rel)}
                  </Link>{" "}
                  <span className="tabular-nums text-zinc-600 dark:text-zinc-400">×{n}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </>
      )}
    </div>
  );
}
