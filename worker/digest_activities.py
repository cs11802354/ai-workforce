"""Activities for the daily learning digest.

Three stages: pull candidate articles from a handful of legitimate public
feeds/APIs (no scraping — everything here is an official RSS feed or a
sanctioned public API), have the model pick and summarize a ~30-minute read
out of them, then email the result via Resend.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from temporalio import activity

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
DIGEST_RECIPIENT_EMAIL = os.environ.get("DIGEST_RECIPIENT_EMAIL", "")

GOOGLE_NEWS_QUERIES = [
    "artificial intelligence",
    "machine learning",
    "large language models",
    "software engineering",
    "distributed systems",
]

MAX_PER_SOURCE = 12


class Article(dict):
    """title, url, source, summary — plain dict subclass so it survives
    Temporal's JSON payload conversion without a custom codec."""


@activity.defn
async def fetch_articles_activity() -> list[dict]:
    articles: list[dict] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        for query in GOOGLE_NEWS_QUERIES:
            articles.extend(await _fetch_google_news(client, query))
        articles.extend(await _fetch_hacker_news(client))
        articles.extend(await _fetch_arxiv(client))

    # De-dupe by URL — the same story often shows up under multiple queries.
    seen: set[str] = set()
    deduped = []
    for a in articles:
        if a["url"] in seen:
            continue
        seen.add(a["url"])
        deduped.append(a)
    return deduped


async def _fetch_google_news(client: httpx.AsyncClient, query: str) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={quote(query)}+when:1d&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        activity.logger.warning("google news fetch failed for %r: %s", query, exc)
        return []

    root = ET.fromstring(resp.text)
    out = []
    for item in root.findall("./channel/item")[:MAX_PER_SOURCE]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source_el = item.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else "Google News"
        if title and link:
            out.append({"title": title, "url": link, "source": source, "summary": ""})
    return out


async def _fetch_hacker_news(client: httpx.AsyncClient) -> list[dict]:
    try:
        resp = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={"tags": "front_page", "hitsPerPage": MAX_PER_SOURCE},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        activity.logger.warning("hacker news fetch failed: %s", exc)
        return []

    out = []
    for hit in resp.json().get("hits", []):
        title = hit.get("title")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        if title:
            out.append({"title": title, "url": url, "source": "Hacker News", "summary": ""})
    return out


async def _fetch_arxiv(client: httpx.AsyncClient) -> list[dict]:
    try:
        resp = await client.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL",
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": MAX_PER_SOURCE,
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        activity.logger.warning("arxiv fetch failed: %s", exc)
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)
    out = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", namespaces=ns) or "").strip().replace("\n", " ")
        link = ""
        for link_el in entry.findall("atom:link", ns):
            if link_el.get("rel") == "alternate" or link_el.get("type") == "text/html":
                link = link_el.get("href", "")
                break
        summary = (entry.findtext("atom:summary", namespaces=ns) or "").strip().replace("\n", " ")
        if title and link:
            out.append({"title": title, "url": link, "source": "arXiv", "summary": summary[:400]})
    return out


DIGEST_SYSTEM_PROMPT = """You curate a daily personal learning digest for a reader whose \
background is AI/ML and software engineering (they build agentic systems, work with LLMs, \
Temporal workflows, and distributed systems).

From the candidate articles you're given, select the ones that are genuinely interesting or \
useful to that reader — favor substance (new research, real engineering write-ups, notable \
releases) over hype or duplicate coverage of the same story. Select enough to fill roughly a \
30-minute read: usually 8-14 items, fewer if the candidates are thin.

Output a single self-contained HTML fragment (no <html>/<head>/<body> tags, just the content), \
using this shape per item:

<h2>Title, linked with &lt;a href="url"&gt;</h2>
<p>Source name</p>
<p>2-3 sentence summary of why it matters, in your own words based on the title/summary given \
— do not invent details you weren't given.</p>

Group loosely by theme if it helps (e.g. "Research", "Engineering", "Industry"), each theme as \
an <h1>. Do not include items that aren't in the candidate list. Do not fabricate URLs."""


@activity.defn
async def summarize_digest_activity(articles: list[dict]) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    candidates = "\n".join(
        f"- {a['title']} ({a['source']}) — {a['url']}" + (f"\n  {a['summary']}" if a["summary"] else "")
        for a in articles
    )

    response = await client.messages.create(
        model="claude-opus-5",
        max_tokens=8000,
        system=DIGEST_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Candidate articles:\n\n{candidates}"}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


@activity.defn
async def send_digest_email_activity(html_body: str) -> str:
    if not RESEND_API_KEY or not DIGEST_RECIPIENT_EMAIL:
        activity.logger.warning(
            "digest email not sent: RESEND_API_KEY or DIGEST_RECIPIENT_EMAIL not configured"
        )
        return "not_configured"

    date_str = datetime.now(timezone.utc).astimezone().strftime("%A, %B %d")
    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [DIGEST_RECIPIENT_EMAIL],
        "subject": f"Daily digest — {date_str}",
        "html": f"<div style=\"font-family: system-ui, sans-serif; max-width: 700px; margin: 0 auto;\">{html_body}</div>",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        )
    resp.raise_for_status()
    return "sent"
