import Link from "next/link";
import { notFound } from "next/navigation";
import { StartupCard } from "@/components/startup-card";
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
  const profile = readProfiles().find((p) => p.slug === slug);
  if (!profile) notFound();
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <p className="text-xs">
        <Link href="/startups" className="underline">
          ← startups
        </Link>
      </p>
      <StartupCard p={profile} full />
    </div>
  );
}
