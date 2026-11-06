"""Deterministic website technology fingerprints (like PredictLeads/BuiltWith technographics, but free and local).

Reads only the HTML of pages enrichment already crawled from the company's own site (robots.txt respected): script /
link URLs, meta generator tags and a few inline markers. No extra requests, no LLM. Results describe the *website*
("site_tech"), which is a hint about the team's stack, not the product's stack, so they are kept separate.
"""

import re

# (label, category, regex over the raw HTML)
FINGERPRINTS: list[tuple[str, str, re.Pattern]] = [
    (label, cat, re.compile(rx, re.I))
    for label, cat, rx in [
        ("Next.js", "framework", r"/_next/static/|__NEXT_DATA__"),
        ("Nuxt", "framework", r"/_nuxt/|__NUXT__"),
        ("Gatsby", "framework", r"___gatsby|/page-data/app-data\.json"),
        ("Remix", "framework", r"__remixContext"),
        ("SvelteKit", "framework", r"__sveltekit|/_app/immutable/"),
        ("Astro", "framework", r"astro-island|/_astro/"),
        ("Angular", "framework", r"ng-version="),
        ("Vue", "framework", r"data-v-[0-9a-f]{8}|vue(\.runtime)?(\.min)?\.js"),
        ("React", "framework", r"react-dom|data-reactroot|__NEXT_DATA__"),
        ("WordPress", "cms", r"/wp-content/|/wp-includes/|<meta[^>]+generator[^>]+wordpress"),
        ("Webflow", "cms", r"webflow\.(js|com)|data-wf-page"),
        ("Framer", "cms", r"framerusercontent\.com|<meta[^>]+generator[^>]+framer"),
        ("Squarespace", "cms", r"static\d?\.squarespace\.com"),
        ("Wix", "cms", r"static\.wixstatic\.com|<meta[^>]+generator[^>]+wix"),
        ("Ghost", "cms", r"<meta[^>]+generator[^>]+ghost"),
        ("HubSpot", "marketing", r"js\.hs-scripts\.com|js\.hsforms\.net|hs-analytics"),
        ("Intercom", "support", r"widget\.intercom\.io|intercomSettings"),
        ("Crisp", "support", r"client\.crisp\.chat"),
        ("Zendesk", "support", r"static\.zdassets\.com"),
        ("Segment", "analytics", r"cdn\.segment\.com"),
        ("PostHog", "analytics", r"posthog(\.min)?\.js|i\.posthog\.com|us\.posthog\.com|eu\.posthog\.com"),
        ("Google Analytics", "analytics", r"googletagmanager\.com/gtag|google-analytics\.com"),
        ("Plausible", "analytics", r"plausible\.io/js"),
        ("Mixpanel", "analytics", r"cdn\.mxpnl\.com|mixpanel"),
        ("Amplitude", "analytics", r"cdn\.amplitude\.com"),
        ("Hotjar", "analytics", r"static\.hotjar\.com"),
        ("Stripe", "payments", r"js\.stripe\.com"),
        ("Paddle", "payments", r"cdn\.paddle\.com"),
        ("Clerk", "auth", r"clerk\.(accounts\.dev|com)|__clerk"),
        ("Auth0", "auth", r"cdn\.auth0\.com|auth0\.com/js"),
        ("Supabase", "backend", r"supabase\.co"),
        ("Firebase", "backend", r"firebaseapp\.com|gstatic\.com/firebasejs"),
        ("Vercel", "hosting", r"/_vercel/|vercel-insights|va\.vercel-scripts\.com"),
        ("Netlify", "hosting", r"netlify(\.app|-identity)"),
        ("Cloudflare", "hosting", r"cdnjs\.cloudflare\.com|/cdn-cgi/|challenges\.cloudflare\.com"),
        ("Calendly", "scheduling", r"assets\.calendly\.com|calendly\.com/"),
        ("Cal.com", "scheduling", r"cal\.com/embed|app\.cal\.com"),
        ("Greenhouse", "hiring", r"boards\.greenhouse\.io|job-boards\.greenhouse\.io"),
        ("Lever", "hiring", r"jobs\.lever\.co"),
        ("Ashby", "hiring", r"jobs\.ashbyhq\.com"),
    ]
]


def detect(htmls: list[str]) -> list[dict]:
    """[{"name", "category"}] seen on any of the pages, in fingerprint order (frameworks first)."""
    blob = "\n".join(h for h in htmls if h)[:2_000_000]
    seen: dict[str, dict] = {}
    for label, cat, rx in FINGERPRINTS:
        if label not in seen and rx.search(blob):
            seen[label] = {"name": label, "category": cat}
    if "Next.js" in seen or "Remix" in seen or "Gatsby" in seen:
        seen.setdefault("React", {"name": "React", "category": "framework"})
    return list(seen.values())
