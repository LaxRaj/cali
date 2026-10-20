import { StartupCard } from "@/components/startup-card";
import { readBrief, readQuality } from "@/lib/brief";

export default function Page() {
  const brief = readBrief();
  const quality = readQuality();

  if (!brief) {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 py-16 text-zinc-600 dark:text-zinc-400">
        No brief found. Run the backend scout to generate{" "}
        <code className="font-mono text-zinc-800 dark:text-zinc-200">
          backend/data/daily_brief.json
        </code>
        .
      </main>
    );
  }

  const findings = [...brief.findings].sort(
    (a, b) => Number(b.is_relevant) - Number(a.is_relevant),
  );
  const relevant = findings.filter((f) => f.is_relevant).length;
  const generated = new Date(brief.generated_at).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-12">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Daily scout
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          {relevant} relevant of {findings.length} startups · generated{" "}
          {generated} UTC
        </p>
        {quality && (
          <p className="mt-1 text-xs text-zinc-500">
            Quality: {quality.valid}/{quality.relevant} valid · {quality.people}{" "}
            people · {quality.edges} connections · sources{" "}
            {Object.entries(quality.sources)
              .map(([k, v]) => `${k} ${v}`)
              .join(", ")}
          </p>
        )}
      </header>
      <div className="space-y-4">
        {findings.map((f) => (
          <StartupCard key={f.source_url} f={f} />
        ))}
      </div>
    </main>
  );
}
