"""First-party enrichment: company contacts and people's public profile links.

POLICY (see CLAUDE.md): only information a company or person has *published themselves* on pages we can
legitimately crawl (robots.txt respected), or a public profile URL whose handle matches the person's name.
We never guess or permute email addresses, never verify addresses, never collect personal phone numbers from
third parties, never scrape behind logins or LinkedIn itself, and never use paid enrichment APIs.
Everything is deterministic (regex / HTML parsing); the LLM is only used to read an About/Team page for people.
Every stored value carries the URL it came from.
"""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import phonenumbers
from bs4 import BeautifulSoup

import ats
from models import Contact, ContactItem, Edge, Extraction, Person
from signals import make_signal

# --- constants -------------------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
OBFUSCATED_RE = re.compile(
    r"([A-Za-z0-9._%+\-]+)\s*[\[\(\{]\s*at\s*[\]\)\}]\s*([A-Za-z0-9\-]+(?:\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*[A-Za-z0-9\-]+)+)", re.I
)
JUNK_EMAIL_DOMAINS = {"example.com", "domain.com", "email.com", "yourdomain.com", "sentry.io", "wixpress.com", "godaddy.com"}
JUNK_EMAIL_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js", ".woff", ".woff2")
JUNK_LOCALS = {"noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster", "abuse", "webmaster"}
KIND_BY_LOCAL = {
    "info": "general", "hello": "general", "hi": "general", "contact": "general", "team": "general",
    "office": "general", "mail": "general", "enquiries": "general", "inquiries": "general",
    "sales": "sales", "partnerships": "sales", "partners": "sales", "business": "sales", "bd": "sales",
    "press": "press", "media": "press", "pr": "press", "support": "support", "help": "support",
    "careers": "other", "jobs": "other", "legal": "other", "privacy": "other", "security": "other",
}
KIND_ORDER = {"general": 0, "sales": 1, "press": 2, "support": 3, "person": 4, "other": 5}

# Hosts that are never a startup's own website.
NOT_COMPANY_HOSTS = {
    "techcrunch.com", "businesswire.com", "prnewswire.com", "globenewswire.com", "crunchbase.com", "news.crunchbase.com",
    "ycombinator.com", "news.ycombinator.com", "linkedin.com", "twitter.com", "x.com", "github.com", "facebook.com",
    "instagram.com", "youtube.com", "medium.com", "substack.com", "wikipedia.org", "reddit.com", "google.com",
    "apple.com", "sec.gov", "play.google.com", "apps.apple.com", "producthunt.com", "finsmes.com", "eu-startups.com", "tech.eu",
    "sifted.eu", "betakit.com", "e27.co", "techfundingnews.com", "bloomberg.com", "reuters.com", "forbes.com",
    "venturebeat.com", "theverge.com", "wired.com", "t.co", "bit.ly", "pitchbook.com", "tracxn.com", "angel.co",
    "wellfound.com", "notion.so", "docs.google.com", "calendly.com", "typeform.com", "forms.gle",
}
TEAM_ONLY = re.compile(r"/(team|people|leadership|founders|who-we-are)/?$", re.I)
CONTACT_ONLY = re.compile(r"/contact(-us)?/?$", re.I)
LEADERSHIP = re.compile(r"leadership|our team|meet the team|founders?\b|chief executive|\bCEO\b", re.I)
TEAM_PATH = re.compile(r"/(contact|contact-us|about|about-us|team|company|people|leadership|founders|who-we-are)/?$", re.I)
PERSON_HOSTS = {"linkedin.com": "linkedin", "twitter.com": "twitter", "x.com": "twitter", "github.com": "github"}
TWITTER_RESERVED = {"share", "intent", "home", "i", "search", "hashtag", "login", "signup", "explore", "settings", "tos", "privacy"}
GITHUB_RESERVED = {"features", "about", "pricing", "login", "join", "marketplace", "sponsors", "topics", "orgs", "apps", "enterprise", "security"}
MAX_EMAILS, MAX_PHONES, MAX_PAGES = 5, 3, 5


# --- helpers ---------------------------------------------------------------------------------------


def fold(text: str) -> str:
    """Lowercase ASCII-folded text."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def host_of(url: str) -> str:
    return re.sub(r"^www\.", "", urlparse(url).netloc.lower())


def base_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "ac", "gov"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def origin_of(url: str) -> str:
    p = urlparse(url if "//" in url else f"https://{url}")
    return f"{p.scheme or 'https'}://{p.netloc}"


def is_company_host(host: str) -> bool:
    return bool(host) and not any(host == h or host.endswith("." + h) for h in NOT_COMPANY_HOSTS)


def company_token(name: str) -> str:
    """Distinctive lowercase token of the company name, for matching hosts/handles."""
    toks = [t for t in re.findall(r"[a-z0-9]+", fold(name)) if t not in {"the", "inc", "labs", "ai", "co", "hq"}]
    return max(toks, key=len) if toks else ""


# --- page parsing ----------------------------------------------------------------------------------


@dataclass
class PageFacts:
    url: str
    emails: list[tuple[str, str]] = field(default_factory=list)  # (address, kind)
    phones: list[str] = field(default_factory=list)
    anchors: list[tuple[str, str]] = field(default_factory=list)  # (absolute href, text)
    jsonld: list[dict] = field(default_factory=list)


def classify_email(addr: str) -> str:
    return KIND_BY_LOCAL.get(addr.split("@")[0].lower(), "person")


def _valid_email(addr: str) -> bool:
    a = addr.lower().strip(".")
    if a.endswith(JUNK_EMAIL_SUFFIX) or "@" not in a:
        return False
    local, domain = a.rsplit("@", 1)
    return local not in JUNK_LOCALS and domain not in JUNK_EMAIL_DOMAINS and "." in domain and len(local) <= 64


def _jsonld_objects(soup: BeautifulSoup) -> list[dict]:
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (ValueError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                out.append(o)
                stack.extend(v for v in o.values() if isinstance(v, (dict, list)))
            elif isinstance(o, list):
                stack.extend(o)
    return out


def parse_page(url: str, html: str) -> PageFacts:
    soup = BeautifulSoup(html or "", "html.parser")
    facts = PageFacts(url=url, jsonld=_jsonld_objects(soup))
    emails: dict[str, str] = {}
    phones: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if _valid_email(addr):
                emails.setdefault(addr.lower(), classify_email(addr))
        elif href.lower().startswith("tel:"):
            phones.append(href[4:].strip())
        elif href.startswith(("http://", "https://", "/")):
            facts.anchors.append((urljoin(url, href), text))

    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    text = soup.get_text(" ", strip=True)
    for m in EMAIL_RE.findall(text):
        if _valid_email(m):
            emails.setdefault(m.lower(), classify_email(m))
    for m in OBFUSCATED_RE.finditer(text):  # "name [at] company [dot] com"
        domain = re.sub(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", ".", m.group(2), flags=re.I)
        addr = f"{m.group(1)}@{domain}"
        if _valid_email(addr):
            emails.setdefault(addr.lower(), classify_email(addr))

    for region in (None, "US"):
        for match in phonenumbers.PhoneNumberMatcher(text, region):
            phones.append(phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164))

    facts.emails = list(emails.items())
    facts.phones = phones
    return facts


def _norm_phone(raw: str) -> str:
    """E.164 when parseable and valid, else ''."""
    for region in (None, "US"):
        try:
            n = phonenumbers.parse(raw, region)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(n):
            return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)
    return ""


# --- socials & people links ------------------------------------------------------------------------


def classify_social(url: str) -> tuple[str, str, str] | None:
    """-> (platform, 'company'|'user', canonical url) for linkedin/twitter/github profile URLs, else None."""
    p = urlparse(url)
    host = re.sub(r"^www\.", "", p.netloc.lower())
    segs = [s for s in p.path.split("/") if s]
    if host.endswith("linkedin.com") and len(segs) >= 2:
        if segs[0] == "company":
            return "linkedin", "company", f"https://www.linkedin.com/company/{segs[1]}"
        if segs[0] == "in":
            return "linkedin", "user", f"https://www.linkedin.com/in/{segs[1]}"
    if host in ("twitter.com", "x.com") and segs and segs[0].lower() not in TWITTER_RESERVED and len(segs) <= 2:
        return "twitter", "user", f"https://x.com/{segs[0]}"
    if host == "github.com" and segs and segs[0].lower() not in GITHUB_RESERVED and len(segs) == 1:
        return "github", "user", f"https://github.com/{segs[0]}"
    return None


def name_matches_slug(name: str, slug: str) -> bool:
    """Does a profile handle/slug plausibly belong to this person? (first+last, or initial+last)."""
    toks = re.findall(r"[a-z]+", fold(name))
    if len(toks) < 2:
        return False
    first, last = toks[0], toks[-1]
    s = re.sub(r"[^a-z]", "", fold(slug))
    return (first in s and last in s) or (first[0] + last in s) or (len(last) >= 4 and s.startswith(first[0]) and last in s)


def _text_matches_name(name: str, text: str) -> bool:
    toks = re.findall(r"[a-z]+", fold(name))
    t = fold(text)
    return len(toks) >= 2 and toks[0] in t and toks[-1] in t


def match_person_links(person: Person, pages: list[PageFacts], company: str = "") -> dict[str, tuple[str, str]]:
    """platform -> (url, page it was found on), from anchors on the company's own pages."""
    found: dict[str, tuple[str, str]] = {}
    for pg in pages:
        for href, text in pg.anchors:
            soc = classify_social(href)
            if not soc or soc[1] != "user" or soc[0] in found:
                continue
            slug = urlparse(soc[2]).path.rstrip("/").split("/")[-1]
            if name_matches_slug(person.name, slug) or _text_matches_name(person.name, text):
                found[soc[0]] = (soc[2], pg.url)
    return found


def search_person_links(person: Person, company: str, search_fn, platforms=("linkedin", "github", "twitter")) -> dict[str, tuple[str, str]]:
    """Public search-engine hits (we only read result URLs/titles, never the platforms). Handle must match the name."""
    queries = {
        "linkedin": f'"{person.name}" "{company}" site:linkedin.com/in',
        "github": f'"{person.name}" "{company}" site:github.com',
        "twitter": f'"{person.name}" "{company}" site:x.com',
    }
    found: dict[str, tuple[str, str]] = {}
    for plat in platforms:
        try:
            results = search_fn(queries[plat])
        except Exception:
            continue
        for r in results:
            soc = classify_social(r.get("href", ""))
            if not soc or soc[0] != plat or soc[1] != "user":
                continue
            slug = urlparse(soc[2]).path.rstrip("/").split("/")[-1]
            title_ok = _text_matches_name(person.name, r.get("title", "")) and company_token(company) in fold(
                r.get("title", "") + " " + r.get("body", "")
            )
            if name_matches_slug(person.name, slug) or (plat == "linkedin" and title_ok):
                found[plat] = (soc[2], "search")
                break
    return found


# --- website discovery -----------------------------------------------------------------------------


def resolve_website(company: str, llm_website: str, source_url: str, source: str, markdown: str, search_fn=None) -> str:
    """The company's own origin, or ''. Priority: LLM-stated (validated) > page link > the page itself > search."""
    token = company_token(company)

    def ok(url: str) -> bool:
        return url.startswith(("http://", "https://")) and is_company_host(host_of(url))

    if llm_website and ok(llm_website if "//" in llm_website else f"https://{llm_website}"):
        w = llm_website if "//" in llm_website else f"https://{llm_website}"
        if llm_website.lower() in markdown.lower() or (token and token in host_of(w)):
            return origin_of(w)
    if token:
        for url in re.findall(r"\]\((https?://[^)\s]+)\)|(?<![\w/])(https?://[^\s)\]>]+)", markdown):
            u = url[0] or url[1]
            if ok(u) and token in host_of(u).replace("-", ""):
                return origin_of(u)
    if source in ("hn", "web", "hiring") and ok(source_url):  # the page we crawled is the product's own site
        return origin_of(source_url)
    if search_fn and token:
        try:
            for r in search_fn(f'"{company}" official website'):
                if ok(r.get("href", "")) and token in host_of(r["href"]).replace("-", ""):
                    return origin_of(r["href"])
        except Exception:
            pass
    return ""


def pick_pages(origin: str, home: PageFacts | None) -> list[str]:
    """Homepage plus up to 4 contact/about/team pages (discovered from homepage links, else common paths)."""
    urls = [origin + "/"]
    host = host_of(origin)
    if home:
        for href, _ in home.anchors:
            if host_of(href) == host and TEAM_PATH.search(urlparse(href).path) and href not in urls:
                urls.append(href.split("#")[0])
    if len(urls) == 1:
        urls += [f"{origin}/contact", f"{origin}/about", f"{origin}/team"]
    return list(dict.fromkeys(urls))[:MAX_PAGES]


# --- assembling the contact record -----------------------------------------------------------------


def build_contact(origin: str, pages: list[PageFacts], company: str = "") -> Contact:
    emails: dict[str, ContactItem] = {}
    phones: dict[str, ContactItem] = {}
    socials: dict[str, str] = {}
    contact_page = ""
    token = company_token(company) or company_token(base_domain(host_of(origin)).split(".")[0])
    for pg in pages:
        if re.search(r"/contact", urlparse(pg.url).path, re.I) and not contact_page:
            contact_page = pg.url
        for addr, kind in pg.emails:
            emails.setdefault(addr, ContactItem(value=addr, kind=kind, source_url=pg.url))
        for raw in pg.phones:
            e164 = _norm_phone(raw)
            if e164:
                phones.setdefault(e164, ContactItem(value=e164, kind="main", source_url=pg.url))
        for href, _ in pg.anchors:
            soc = classify_social(href)
            if not soc or soc[0] in socials:
                continue
            handle = fold(urlparse(soc[2]).path.rstrip("/").split("/")[-1]).replace("-", "").replace("_", "")
            # a x.com/github.com link is the *company's* only if its handle looks like the company name
            if soc[1] == "company" or (token and token in handle):
                socials[soc[0]] = soc[2]
        for o in pg.jsonld:  # Organization markup: the company's own declared contact details
            t = o.get("@type")
            types = t if isinstance(t, list) else [t]
            if not any(isinstance(x, str) and x in {"Organization", "Corporation", "LocalBusiness", "ProfessionalService", "SoftwareApplication", "Brand"} for x in types):
                continue
            if isinstance(o.get("email"), str) and _valid_email(o["email"].replace("mailto:", "")):
                a = o["email"].replace("mailto:", "").strip().lower()
                emails.setdefault(a, ContactItem(value=a, kind=classify_email(a), source_url=pg.url))
            if isinstance(o.get("telephone"), str) and (e := _norm_phone(o["telephone"])):
                phones.setdefault(e, ContactItem(value=e, kind="main", source_url=pg.url))
            for sa in o.get("sameAs", []) if isinstance(o.get("sameAs"), list) else []:
                soc = classify_social(sa) if isinstance(sa, str) else None
                if soc and soc[0] not in socials:  # sameAs is the company's own declaration
                    socials[soc[0]] = soc[2]
    ranked = sorted(emails.values(), key=lambda c: (KIND_ORDER.get(c.kind, 9), c.value))
    return Contact(
        product_access=product_access(pages, origin),
        website=origin,
        emails=ranked[:MAX_EMAILS],
        phones=list(phones.values())[:MAX_PHONES],
        socials=socials,
        contact_page=contact_page,
        pages_crawled=[p.url for p in pages],
        enriched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="ok",
    )


PRODUCT_LINK = re.compile(r"^\s*(sign ?up|get started|try( it| for free| now)?|start (free|building|now)|free trial|demo|playground|docs|documentation|pricing|open app|launch app)\b", re.I)


def product_access(pages: list[PageFacts], origin: str, limit: int = 4) -> list[dict[str, str]]:
    """Links on the company's own pages that let you try or read the product (the 'use it first' step)."""
    out: dict[str, dict[str, str]] = {}
    for pg in pages[:2]:
        for href, text in pg.anchors:
            label = (text or "").strip()
            if label and len(label) <= 30 and PRODUCT_LINK.match(label) and href.startswith("http") and not classify_social(href):
                out.setdefault(href.split("#")[0], {"label": label, "url": href.split("#")[0]})
    return list(out.values())[:limit]


def post_emails(text: str, source_url: str) -> list[ContactItem]:
    """Addresses a hiring post itself publishes (the company chose to put them there)."""
    out: dict[str, ContactItem] = {}
    for a in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text or ""):
        a = a.lower().strip(".")
        if _valid_email(a):
            out.setdefault(a, ContactItem(value=a, kind=classify_email(a), source_url=source_url))
    return list(out.values())


async def open_role_signals(facts: list[PageFacts], jobs_fn, notes: list[str]) -> list[dict]:
    """Open roles the company itself publishes (its Greenhouse/Lever/Ashby board or JobPosting markup)."""
    jobs: list[dict] = []
    source, url = "jobposting_markup", facts[0].url if facts else ""
    for pg in facts:
        jobs += ats.jsonld_jobs(pg.jsonld, pg.url)
    if jobs_fn:
        board = ats.detect_board([href for pg in facts for href, _ in pg.anchors])
        if board:
            try:
                fetched = await asyncio.to_thread(jobs_fn, *board)
            except Exception as e:
                fetched = []
                notes.append(f"job board failed: {e}")
            if fetched:
                jobs, source, url = fetched, board[0], f"https://{ {'greenhouse': 'boards.greenhouse.io', 'lever': 'jobs.lever.co', 'ashby': 'jobs.ashbyhq.com'}[board[0]] }/{board[1]}"
    if not jobs:
        return []
    notes.append(f"{len(jobs)} open roles ({source})")
    newest = max((j.get("posted_at") or "" for j in jobs), default="")
    return [make_signal("hiring", source, url, [j["title"] for j in jobs], newest)]


def jsonld_people(pages: list[PageFacts], company: str) -> list[Person]:
    """Founders/employees the company declares in its own schema.org markup (no LLM; source page recorded)."""
    out: dict[str, Person] = {}
    for pg in pages:
        for o in pg.jsonld:
            if o.get("@type") != "Person" and "Person" not in (o.get("@type") if isinstance(o.get("@type"), list) else []):
                continue
            name = o.get("name")
            if not isinstance(name, str) or len(name.split()) < 2 or len(name) > 60:
                continue
            links = {}
            for u in ([o.get("url")] if isinstance(o.get("url"), str) else []) + (o.get("sameAs") if isinstance(o.get("sameAs"), list) else []):
                soc = classify_social(u) if isinstance(u, str) else None
                if soc and soc[1] == "user" and soc[0] in ("linkedin", "twitter", "github"):
                    links.setdefault(soc[0], soc[2])
            role = o.get("jobTitle") if isinstance(o.get("jobTitle"), str) else ""
            out.setdefault(fold(name), Person(name=name.strip(), role=role, org=company, evidence="schema.org Person markup",
                                              link_source=pg.url, **links))
    return list(out.values())


def jsonld_hq(pages: list[PageFacts]) -> str:
    for pg in pages:
        for o in pg.jsonld:
            addr = o.get("address")
            if isinstance(addr, dict) and addr.get("addressLocality"):
                country = addr.get("addressCountry")
                country = country.get("name") if isinstance(country, dict) else country
                return ", ".join(x for x in (addr["addressLocality"], country) if isinstance(x, str) and x)
    return ""


# --- people merging --------------------------------------------------------------------------------


def merge_people(base: list[Person], extra: list[Person]) -> list[Person]:
    """Add people from the team page; fill missing role/org/links on existing ones (by folded name)."""
    out = {fold(p.name): p for p in base}
    for p in extra:
        k = fold(p.name)
        if k not in out:
            out[k] = p
        else:
            cur = out[k]
            out[k] = cur.model_copy(update={f: getattr(p, f) for f in ("role", "org", "linkedin", "twitter", "github", "homepage") if not getattr(cur, f) and getattr(p, f)})
    return list(out.values())


def merge_edges(base: list[Edge], extra: list[Edge]) -> list[Edge]:
    seen = {(fold(e.src), e.rel, fold(e.dst)) for e in base}
    return base + [e for e in extra if (fold(e.src), e.rel, fold(e.dst)) not in seen]


def apply_person_links(people: list[Person], pages: list[PageFacts], company: str, search_fn=None, budget: list[int] | None = None) -> list[Person]:
    """Attach profile links: first from the company's own pages, then (budgeted) public search for leaders."""
    out = []
    for p in sorted(people, key=lambda x: not re.search(r"found|ceo|cto", x.role or "", re.I)):  # founders get the search budget first
        links = match_person_links(p, pages, company)
        leader = re.search(r"founder|ceo|cto|chief|co-?found|head of|president", p.role or "", re.I)
        if search_fn and leader and budget is not None and budget[0] > 0:
            missing = tuple(x for x in ("linkedin",) if x not in links and not getattr(p, x))  # 1 query per leader
            for plat in missing:
                if budget[0] <= 0:
                    break
                budget[0] -= 1
                links.update(search_person_links(p, company, search_fn, platforms=(plat,)))
        upd = {plat: url for plat, (url, _) in links.items() if not getattr(p, plat)}
        if upd:
            src = next(iter(links.values()))[1]
            upd["link_source"] = p.link_source or src
        out.append(p.model_copy(update=upd) if upd else p)
    return out


def team_markdown(pages: list[tuple[str, str]], limit: int = 9000) -> str:
    """About/Team page markdown (url, markdown) for a people-extraction pass.

    Team and leadership pages come first, then about; contact pages are left out (their emails are parsed
    separately and their forms would use up the window the extractor reads). Same-site nav links are reduced
    to their text, and a long page starts at its first leadership heading, so names are not cut off."""
    def rank(url: str) -> int:
        path = urlparse(url).path
        return 0 if TEAM_ONLY.search(path) else 1

    chosen = [(u, md) for u, md in pages if md and TEAM_PATH.search(urlparse(u).path) and not CONTACT_ONLY.search(urlparse(u).path)]
    parts = []
    for url, md in sorted(chosen, key=lambda p: rank(p[0])):
        host = re.escape(host_of(url))
        md = re.sub(rf"\[([^\]]*)\]\(https?://(?:www\.)?{host}[^)]*\)", r"\1", md)
        if len(md) > limit and (m := LEADERSHIP.search(md)) and m.start() > 300:
            md = md[max(0, m.start() - 200):]
        parts.append(md)
    return "\n\n".join(parts)[:limit]


def extraction_with_people(ex: Extraction, people: list[Person], edges: list[Edge]) -> Extraction:
    return tidy(ex.model_copy(update={"people": people, "edges": edges}))


# --- crawling + orchestration ----------------------------------------------------------------------

import asyncio  # noqa: E402

from quality import filter_edges, filter_people, tidy  # noqa: E402


@dataclass
class Fetched:
    url: str
    html: str
    markdown: str


async def fetch_pages(urls: list[str]) -> list[Fetched]:
    """Crawl pages politely (robots.txt respected). Failures are skipped."""
    from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

    cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, check_robots_txt=True, page_timeout=20000)
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(urls, config=cfg)
    out = []
    for r in results:
        if r.success and r.html:
            md = r.markdown.raw_markdown if r.markdown else ""
            out.append(Fetched(url=r.redirected_url or r.url, html=r.html, markdown=md))
    return out


@dataclass
class EnrichResult:
    extraction: Extraction
    contact: Contact
    notes: list[str] = field(default_factory=list)
    signals: list[dict] = field(default_factory=list)  # open-role signals found on the company's own job board


async def enrich_startup(
    ex: Extraction,
    source: str,
    markdown: str,
    *,
    search_fn=None,
    fetch_fn=fetch_pages,
    extract_fn=None,
    search_budget: list[int] | None = None,
    team_budget: list[int] | None = None,
    github_fn=None,
    jobs_fn=None,
) -> EnrichResult:
    """Find the company's site, collect published contacts + socials, read its team page, link people."""
    s = ex.startup
    notes: list[str] = []
    website = resolve_website(s.company_name, s.website, s.source_url, source, markdown, search_fn)
    people, edges = list(ex.people), list(ex.edges)

    if not website:
        people = apply_person_links(people, [], s.company_name, search_fn, search_budget)
        return EnrichResult(
            extraction_with_people(ex, people, edges),
            Contact(status="no_website", enriched_at=datetime.now(timezone.utc).isoformat(timespec="seconds")),
            ["no website found"],
        )

    fetched: list[Fetched] = []
    try:
        fetched = await fetch_fn([website + "/"])
        home = parse_page(fetched[0].url, fetched[0].html) if fetched else None
        if fetched and is_company_host(host_of(fetched[0].url)):
            website = origin_of(fetched[0].url)  # follow redirects (e.g. a rebrand) so contacts and site agree
        extra = [u for u in pick_pages(website, home) if u != website + "/"]
        if extra:
            fetched += await fetch_fn(extra)
    except Exception as e:
        notes.append(f"crawl error: {e}")
    facts = [parse_page(f.url, f.html) for f in fetched]
    if not facts:
        return EnrichResult(
            extraction_with_people(ex, apply_person_links(people, [], s.company_name, search_fn, search_budget), edges),
            Contact(website=website, status="crawl_failed", enriched_at=datetime.now(timezone.utc).isoformat(timespec="seconds")),
            notes + ["crawl failed"],
        )

    contact = build_contact(website, facts, s.company_name)
    updates = {"website": website}
    if not s.hq and (hq := jsonld_hq(facts)):
        updates["hq"] = hq

    # People/connections from the company's own About/Team page (grounded against that page).
    if declared := jsonld_people(facts, s.company_name):
        people = merge_people(people, declared)
        notes.append(f"structured data: {len(declared)} people")
    tmd = team_markdown([(f.url, f.markdown) for f in fetched])
    known_leader = any(
        len(p.name.split()) > 1 and re.search(r"found|ceo|cto|chief", p.role or "", re.I)
        for p in tidy(extraction_with_people(ex, people, edges)).people
    )
    # the LLM team pass pays off only when we lack a named leader or have a thin team (otherwise it returns nothing new)
    if re.search(r"[A-Z][a-z]+ [A-Z][a-zA-Z'’-]+", tmd) and extract_fn and (not known_leader or len(people) < 3) and (team_budget is None or team_budget[0] > 0):
        if team_budget is not None:
            team_budget[0] -= 1
        try:
            tex = extract_fn(tmd)
            new_people = [p.model_copy(update={"org": p.org or s.company_name, "link_source": ""}) for p in filter_people(tex.people, tmd)]
            notes.append(f"team llm: {len(tex.people)} people proposed, {len(new_people)} grounded")
            new_edges = filter_edges(tex.edges, tmd)
            before = (len(people), len(edges))
            people, edges = merge_people(people, new_people), merge_edges(edges, new_edges)
            notes.append(f"team page: +{len(people) - before[0]} people, +{len(edges) - before[1]} edges")
        except Exception as e:
            notes.append(f"team extraction failed: {e}")

    people = apply_person_links(people, facts, s.company_name, search_fn, search_budget)
    if github_fn:  # public profile fields people published themselves (blog, X handle)
        try:
            people = await asyncio.to_thread(github_fn, people)
        except Exception as e:
            notes.append(f"github enrichment failed: {e}")
    new_ex = extraction_with_people(ex.model_copy(update={"startup": s.model_copy(update=updates)}), people, edges)
    return EnrichResult(new_ex, contact, notes, await open_role_signals(facts, jobs_fn, notes))
