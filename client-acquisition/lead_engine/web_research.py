"""Public-web evidence collection for local client research.

This module intentionally uses only public HTTP pages. It does not log in,
scrape private profiles, send messages, or perform outbound actions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser
import re
from typing import Iterable, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "ClientAcquisitionOS/0.1 (+public-research; local operator tool)"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass
class EvidenceItem:
    claim_context: str
    source_url: str
    source_title: str
    snippet: str
    source_type: str = "public_web"


class _SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: List[SearchResult] = []
        self._href: Optional[str] = None
        self._title_parts: List[str] = []
        self._snippet_parts: List[str] = []
        self._in_title = False
        self._in_snippet = False

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_map = dict(attrs)
        classes = set((attrs_map.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._href = attrs_map.get("href")
            self._title_parts = []
            self._in_title = True
        elif tag in {"a", "div"} and "result__snippet" in classes:
            self._snippet_parts = []
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            if self._href:
                self.results.append(
                    SearchResult(
                        title=" ".join(self._title_parts).strip(),
                        url=self._href,
                    )
                )
            self._href = None
            self._in_title = False
        elif tag in {"a", "div"} and self._in_snippet:
            if self.results and self._snippet_parts:
                self.results[-1].snippet = " ".join(self._snippet_parts).strip()
            self._in_snippet = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        if self._in_snippet:
            self._snippet_parts.append(text)


def _clean_ddg_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            return unquote(target)
    return url


def search_public_web(query: str, max_results: int = 5, timeout: int = 12) -> List[SearchResult]:
    """Search DuckDuckGo's public HTML endpoint without an API key."""
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
    parser = _SearchParser()
    parser.feed(html)
    results: List[SearchResult] = []
    seen = set()
    for result in parser.results:
        clean = _clean_ddg_url(result.url)
        host = urlparse(clean).netloc.lower()
        if not host or clean in seen:
            continue
        seen.add(clean)
        result.url = clean
        results.append(result)
        if len(results) >= max_results:
            break
    return results


class _PageTextParser(HTMLParser):
    BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "article", "section", "br"}
    IGNORE_TAGS = {"script", "style", "noscript", "svg", "nav", "footer"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.IGNORE_TAGS:
            self._ignored += 1
        elif self._ignored == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.IGNORE_TAGS and self._ignored:
            self._ignored -= 1
        elif self._ignored == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored == 0:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)


def fetch_public_page(url: str, max_chars: int = 9000, timeout: int = 12) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return ""
        raw = response.read(1_500_000).decode("utf-8", errors="replace")
    parser = _PageTextParser()
    parser.feed(raw)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(parser.parts)).strip()
    return text[:max_chars]


def build_queries(company: str, contact: Optional[str] = None) -> List[str]:
    queries = [
        f'"{company}" ecommerce operations',
        f'"{company}" Shopify Unicommerce',
        f'"{company}" hiring operations manager',
        f'"{company}" inventory fulfilment RTO',
        f'"{company}" careers',
    ]
    if contact:
        queries.append(f'"{contact}" "{company}"')
    return queries


def research_company(company: str, contact: Optional[str] = None, max_sources: int = 8) -> dict:
    """Collect public evidence and return a serializable research bundle."""
    results: List[SearchResult] = []
    seen_urls = set()
    errors: List[str] = []

    for query in build_queries(company, contact):
        try:
            for item in search_public_web(query, max_results=4):
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    results.append(item)
                if len(results) >= max_sources:
                    break
        except Exception as exc:
            errors.append(f"search failed for {query!r}: {exc}")
        if len(results) >= max_sources:
            break

    evidence: List[EvidenceItem] = []
    pages = []
    for result in results:
        try:
            text = fetch_public_page(result.url)
        except Exception as exc:
            errors.append(f"fetch failed for {result.url}: {exc}")
            text = ""
        if text:
            pages.append({"title": result.title, "url": result.url, "text": text})
            evidence.append(
                EvidenceItem(
                    claim_context=f"Public page discovered for {company}",
                    source_url=result.url,
                    source_title=result.title,
                    snippet=text[:2500],
                )
            )
        elif result.snippet:
            evidence.append(
                EvidenceItem(
                    claim_context=f"Search result mentioning {company}",
                    source_url=result.url,
                    source_title=result.title,
                    snippet=result.snippet,
                )
            )

    return {
        "company": company,
        "contact": contact,
        "queries": build_queries(company, contact),
        "sources_found": len(results),
        "sources_fetched": len(pages),
        "evidence": [asdict(item) for item in evidence],
        "pages": pages,
        "errors": errors,
    }
