"""Public-web evidence collection for local client research.

This module intentionally uses only public HTTP pages. It does not log in,
scrape private profiles, send messages, or perform outbound actions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser
import re
from typing import List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


USER_AGENT = "ClientAcquisitionOS/0.2 (+public-research; local operator tool)"
SEARCH_ENDPOINTS = (
    ("bing_rss", "https://www.bing.com/search?format=rss&q="),
    ("duckduckgo_html", "https://html.duckduckgo.com/html/?q="),
    ("duckduckgo_lite", "https://lite.duckduckgo.com/lite/?q="),
)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    provider: str = "unknown"


@dataclass
class EvidenceItem:
    claim_context: str
    source_url: str
    source_title: str
    snippet: str
    source_type: str = "public_web"


class _SearchParser(HTMLParser):
    """Parse both DuckDuckGo HTML and Lite result markup.

    DDG has changed its result markup over time. Keep the parser deliberately
    permissive so a markup change does not turn into a false ``0 sources``.
    """

    RESULT_LINK_CLASSES = {"result__a", "result-link"}
    SNIPPET_CLASSES = {"result__snippet", "result-snippet"}

    def __init__(self) -> None:
        super().__init__()
        self.results: List[SearchResult] = []
        self._href: Optional[str] = None
        self._title_parts: List[str] = []
        self._snippet_parts: List[str] = []
        self._in_title = False
        self._in_snippet = False
        self._snippet_target: Optional[SearchResult] = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_map = dict(attrs)
        classes = set((attrs_map.get("class") or "").split())

        if tag == "a" and classes & self.RESULT_LINK_CLASSES:
            self._href = attrs_map.get("href")
            self._title_parts = []
            self._in_title = True
            return

        if classes & self.SNIPPET_CLASSES:
            self._snippet_parts = []
            self._snippet_target = self.results[-1] if self.results else None
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
            return

        if self._in_snippet and tag in {"a", "div", "td", "p"}:
            snippet = " ".join(self._snippet_parts).strip()
            if snippet and self._snippet_target is not None:
                self._snippet_target.snippet = snippet
            self._snippet_parts = []
            self._snippet_target = None
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


def _parse_search_html(html: str, max_results: int) -> List[SearchResult]:
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


def _parse_bing_rss(xml_text: str, max_results: int) -> List[SearchResult]:
    root = ET.fromstring(xml_text)
    results: List[SearchResult] = []
    seen = set()
    for item in root.findall(".//item"):
        title = " ".join((item.findtext("title") or "").split())
        url = (item.findtext("link") or "").strip()
        snippet = " ".join((item.findtext("description") or "").split())
        if not title or not url:
            continue
        url = _clean_ddg_url(url)
        host = urlparse(url).netloc.lower()
        if not host or url in seen:
            continue
        seen.add(url)
        results.append(SearchResult(title=title, url=url, snippet=snippet, provider="bing_rss"))
        if len(results) >= max_results:
            break
    return results


def _fetch_search_endpoint(endpoint: str, query: str, timeout: int) -> List[SearchResult]:
    url = endpoint + quote_plus(query)
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        content_type = response.headers.get("Content-Type", "").lower()

    if endpoint.startswith("https://www.bing.com") or "xml" in content_type:
        try:
            return _parse_bing_rss(body, max_results=50)
        except ET.ParseError:
            return []
    return _parse_search_html(body, max_results=50)


_BLOCKED_HOSTS = {
    "maps.google.com",
    "streetviewstudio.maps.google.com",
    "contentpartners.maps.google.com",
}


def _identity_terms(query: str) -> List[str]:
    # Generated queries intentionally quote company/contact identity. Use only
    # those quoted identity terms for prefiltering; search intent terms are
    # useful to the provider but are too brittle for result-level validation.
    quoted = re.findall(r'"([^"]+)"', query.lower())
    return [term.strip() for term in quoted if len(term.strip()) >= 3]


def _is_relevant_result(result: SearchResult, query: str) -> bool:
    host = urlparse(result.url).netloc.lower().split(":", 1)[0]
    if host in _BLOCKED_HOSTS or host.endswith(".googleusercontent.com"):
        return False

    identity_terms = _identity_terms(query)
    if not identity_terms:
        return True

    # Company/contact identity may appear in title, URL, or snippet. Do not
    # require every query token because providers routinely omit intent words
    # from result metadata even when ranking the correct page.
    haystack = " ".join((result.title, result.url, result.snippet)).lower()
    return any(term in haystack for term in identity_terms)


def _filter_relevant_results(results: List[SearchResult], query: str, max_results: int) -> List[SearchResult]:
    filtered: List[SearchResult] = []
    seen = set()
    for result in results:
        if not _is_relevant_result(result, query):
            continue
        if result.url in seen:
            continue
        seen.add(result.url)
        filtered.append(result)
        if len(filtered) >= max_results:
            break
    return filtered


def search_public_web(query: str, max_results: int = 5, timeout: int = 12) -> List[SearchResult]:
    """Search public web results with provider fallback and relevance filtering."""
    errors: List[str] = []
    for provider, endpoint in SEARCH_ENDPOINTS:
        try:
            results = _fetch_search_endpoint(endpoint, query, timeout)
            results = [
                SearchResult(r.title, r.url, r.snippet, provider)
                for r in results
            ]
            relevant = _filter_relevant_results(results, query, max_results)
            if relevant:
                return relevant
            errors.append(f"{provider}: response had no relevant parseable results")
        except Exception as exc:
            errors.append(f"{provider}: {exc}")

    detail = "; ".join(errors)
    raise RuntimeError(f"public search unavailable for query {query!r}: {detail}")


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
            for item in search_public_web(query, max_results=8):
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
