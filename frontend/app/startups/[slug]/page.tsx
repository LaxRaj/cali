import Link from "next/link";
import { notFound } from "next/navigation";
import { LeadPanel } from "@/components/outreach/lead-panel";
import { StartupCard } from "@/components/startup-card";
import { Trackbacks } from "@/components/startups/trackbacks";
import { readProfiles } from "@/lib/data";

export function generateStaticParams() {
  const profiles = readProfiles();
  return profiles.length
    ? profiles.map((p) => ({ slug: p.slug }))
    : [{ slug: "none" }];
}

export default async function StartupPage({
  params,
}: PageProps<"/startups/[slug]">) {
  const { slug } = await params;
  const profiles = readProfiles();
  const at = profiles.findIndex((p) => p.slug === slug);
  const profile = profiles[at];
  if (!profile) notFound();
  const prev = profiles[at - 1];
  const next = profiles[at + 1];
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <nav
        aria-label="Lead navigation"
        className="flex flex-wrap items-center justify-between gap-2 text-xs"
      >
        <Link href="/startups" className="underline">
          ← startups
        </Link>
        <span className="flex gap-4">
          {prev && (
            <Link
              href={`/startups/${prev.slug}`}
              rel="prev"
              className="underline"
            >
              ◀ {prev.company_name}
            </Link>
          )}
          {next && (
            <Link
              href={`/startups/${next.slug}`}
              rel="next"
              className="underline"
            >
              {next.company_name} ▶
            </Link>
          )}
        </span>
      </nav>
      <LeadPanel profile={profile} />
      <StartupCard p={profile} full />
      <Trackbacks rows={profile.trackbacks ?? []} />
    </div>
  );
}
