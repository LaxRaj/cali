"""SEC Form D filings: real, dated private-funding events with named officers/directors and amounts.

Free official data (https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=D). SEC's fair-access policy
requires a descriptive User-Agent with a contact email: set CALI_CONTACT_EMAIL (a repo secret in CI). Without it
this source stays off. Many Form D filers are funds / real-estate vehicles, so we filter on entity type, industry
group and name, and the decision layer ranks what is left.
"""

import os
import re
import time
import xml.etree.ElementTree as ET

import feedparser
import httpx

from discovery import Candidate

FEED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=D&company=&dateb=&owner=include&start=0&count=100&output=atom"
MAX_FILINGS = 40  # primary_doc.xml fetches per run (SEC allows 10 req/s; we stay far below)
OPERATING_TYPES = {"Corporation", "Limited Liability Company"}
WANTED_INDUSTRIES = {"Computers", "Telecommunications", "Other Technology", "Other", "Biotechnology"}
FUND_NAME = re.compile(
    r"\b(fund|l\.?p\.?|trust|capital partners|holdings?|dst|series|acquisition|realty|real estate|properties|"
    r"reit|credit|lending|mortgage|equity partners|opportunit(y|ies)|spv|investors?)\b",
    re.I,
)


def user_agent() -> str | None:
    email = os.environ.get("CALI_CONTACT_EMAIL", "").strip()
    return f"cali-scout (startup research) {email}" if email else None


def parse_feed(atom_text: str) -> list[dict]:
    """Form D entries from the 'latest filings' feed -> [{issuer, cik, folder, updated}]."""
    out = []
    for e in feedparser.parse(atom_text).entries:
        m = re.match(r"D(?:/A)? - (.+?) \((\d{10})\) \(Filer\)", e.get("title", ""))
        if not m or "/A" in e.get("title", "").split(" - ")[0]:
            continue  # amendments repeat earlier filings
        link = e.get("link", "")
        out.append({"issuer": m.group(1), "cik": m.group(2), "folder": link.rsplit("/", 1)[0], "updated": e.get("updated", "")})
    return out


def _text(el, path: str) -> str:
    node = el.find(path) if el is not None else None
    return (node.text or "").strip() if node is not None and node.text else ""


def parse_form_d(xml_text: str) -> dict | None:
    """Structured fields of one Form D, or None if it isn't an operating company we care about."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    issuer = root.find("primaryIssuer")
    name = _text(issuer, "entityName")
    etype = _text(issuer, "entityType")
    industry = _text(root, "offeringData/industryGroup/industryGroupType")
    if not name or etype not in OPERATING_TYPES or industry not in WANTED_INDUSTRIES or FUND_NAME.search(name):
        return None
    people = []
    for rp in root.findall("relatedPersonsList/relatedPersonInfo"):
        first, last = _text(rp, "relatedPersonName/firstName"), _text(rp, "relatedPersonName/lastName")
        rels = [r.text.strip() for r in rp.findall("relatedPersonRelationshipList/relationship") if r.text]
        if first or last:
            people.append({"name": f"{first} {last}".strip(), "roles": rels})
    def num(path: str) -> int:
        try:
            return int(float(_text(root, path) or 0))
        except ValueError:
            return 0

    return {
        "issuer": name, "entity_type": etype, "state": _text(issuer, "issuerAddress/stateOrCountryDescription") or _text(issuer, "issuerAddress/stateOrCountry"),
        "city": _text(issuer, "issuerAddress/city").title(), "jurisdiction": _text(issuer, "jurisdictionOfInc").title(),
        "phone": _text(issuer, "issuerPhoneNumber"), "year_inc": _text(issuer, "yearOfInc/value"),
        "recent": _text(issuer, "yearOfInc/withinFiveYears") == "true", "industry": industry,
        "offering": num("offeringData/offeringSalesAmounts/totalOfferingAmount"), "sold": num("offeringData/offeringSalesAmounts/totalAmountSold"),
        "investors": num("offeringData/investors/totalNumberAlreadyInvested"), "first_sale": _text(root, "offeringData/typeOfFiling/dateOfFirstSale/value"),
        "signer": _text(root, "offeringData/signatureBlock/signature/nameOfSigner"), "signer_title": _text(root, "offeringData/signatureBlock/signature/signatureTitle"),
        "people": people,
    }


def _money(n: int) -> str:
    return f"${n / 1e6:.2f}M" if n >= 1_000_000 else f"${n / 1e3:.0f}K" if n else "undisclosed"


def to_candidate(form: dict, filing_url: str, updated: str = "") -> Candidate:
    where = ", ".join(x for x in (form["city"], form["state"]) if x)
    lines = [f"# {form['issuer']} files SEC Form D", "",
             f"{form['issuer']} ({form['entity_type']}, {form['jurisdiction']}) is based in {where or 'the United States'}."
             + (f" Incorporated {form['year_inc']}." if form["year_inc"] else ""),
             f"Industry group: {form['industry']}. Offering: {_money(form['offering'])}; sold so far: {_money(form['sold'])}"
             + (f" to {form['investors']} investors" if form["investors"] else "") + (f" (first sale {form['first_sale']})." if form["first_sale"] else "."), ""]
    if form["people"]:
        lines.append("Executive officers and directors named in the filing:")
        lines += [f"- {p['name']} — {', '.join(p['roles']) or 'related person'}" for p in form["people"]]
    if form["signer"]:
        lines.append(f"Signed by {form['signer']}, {form['signer_title']}.")
    if form["phone"]:
        lines.append(f"Issuer phone listed in the filing: {form['phone']}.")
    return Candidate(
        url=filing_url,
        title=f"{form['issuer']} raises {_money(form['sold'] or form['offering'])} (SEC Form D)",
        snippet=f"{where}; {form['industry']}; {form['investors']} investors; {len(form['people'])} named officers/directors",
        source="edgar", published_at=updated, content="\n".join(lines), company=form["issuer"],
    )


def fetch(client: httpx.Client | None = None, max_filings: int = MAX_FILINGS) -> list[Candidate]:
    ua = user_agent()
    if not ua:
        print("edgar: CALI_CONTACT_EMAIL not set; SEC requires a contact in the User-Agent, skipping", flush=True)
        return []
    client = client or httpx.Client(timeout=20, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"})
    try:
        r = client.get(FEED)
        r.raise_for_status()
        entries = parse_feed(r.text)
    except httpx.HTTPError:
        return []
    out: list[Candidate] = []
    for e in entries[:max_filings]:
        try:
            x = client.get(f"{e['folder']}/primary_doc.xml")
            x.raise_for_status()
        except httpx.HTTPError:
            continue
        form = parse_form_d(x.text)
        if form and form["recent"]:
            out.append((form, to_candidate(form, e["folder"] + "/", e["updated"])))
        time.sleep(0.15)
    return dedupe([c for _, c in out], {id(c): f for f, c in out})


def dedupe(cands: list[Candidate], forms: dict[int, dict]) -> list[Candidate]:
    """A company often files several Form Ds (rounds, amendments); keep the one with the most raised."""
    best: dict[str, Candidate] = {}
    for c in cands:
        key = c.company.strip().lower()
        amount = lambda x: forms[id(x)]["sold"] or forms[id(x)]["offering"]  # noqa: E731
        if key not in best or amount(c) > amount(best[key]):
            best[key] = c
    return list(best.values())


MAX_SITE_CHARS = 6000
MIN_SITE_PROSE = 150  # chars of real prose on the homepage; placeholder/under-construction pages have none


async def materialize(cand: Candidate, search_fn=None, fetch_fn=None) -> str | None:
    """Turn a Form D candidate into extractable content, or None if we can't tell what the company does.

    A filing names the company, officers and amount raised but says nothing about the product, so we find the
    filer's own website, read its homepage, and append it to the filing facts. The homepage must actually mention
    the company (guards against another company with a similar name). Returns the combined Markdown.
    """
    from enrich import company_token, fetch_pages, fold, is_company_host, host_of, origin_of, resolve_website

    fetch_fn = fetch_fn or fetch_pages
    website = resolve_website(cand.company, "", cand.url, "edgar", cand.content, search_fn)
    if not website:
        return None
    try:
        pages = await fetch_fn([website + "/"])
    except Exception:
        return None
    if not pages:
        return None
    home = pages[0]
    final = origin_of(home.url) if is_company_host(host_of(home.url)) else website
    token = company_token(cand.company)
    from decide.decisions import article_text

    if len(article_text(home.markdown, 400)) < MIN_SITE_PROSE:
        return None  # nothing for the extractor to read: skip before spending LLM tokens
    squashed = re.sub(r"[^a-z0-9]", "", fold(home.markdown))  # "Reservoir Co" / "reservoir-co" both match "reservoirco"
    if not home.markdown.strip() or (token and token not in squashed):
        return None
    return (
        f"{cand.content}\n\n## {cand.company} website\n\nWebsite: {final}\n\n{home.markdown.strip()[:MAX_SITE_CHARS]}"
    )
