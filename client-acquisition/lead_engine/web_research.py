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


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 ClientAcquisitionOS/0.3"
SEARCH_ENDPOINTS = (
    "https://www.bing.com/search?format=rss&q=",
    "https://html.duckduckgo.com/html/?q=",
    "https://lite.duckduckgo.com/lite/?q=",
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
    """Parse both DuckDuckGo HTML and Lite result markup."""

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
                self.results.append(SearchResult(title=" ".join(self._title_parts).strip(), url=self._href))
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


def _clean_redirect_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            return unquote(target)
    return url


def _clean_ddg_url(url: str) -> str:
    return _clean_redirect_url(url)


def _parse_search_html(html: str, max_results: int, provider: str = "duckduckgo") -> List[SearchResult]:
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
        result.provider = provider
        results.append(result)
        if len(results) >= max_results:
            break
    return results


def _parse_bing_rss(xml_text: str, max_results: int) -> List[SearchResult]:
    """Parse Bing RSS without external dependencies."""
    results: List[SearchResult] = []
    seen = set()
    item_blocks = re.findall(r"<item>(.*?)</item>", xml_text, flags=re.IGNORECASE | re.DOTALL)
    for block in item_blocks:
        title_match = re.search(r"<title>(.*?)</title>", block, flags=re.IGNORECASE | re.DOTALL)
        link_match = re.search(r"<link>(.*?)</link>", block, flags=re.IGNORECASE | re.DOTALL)
        desc_match = re.search(r"<description>(.*?)</description>", block, flags=re.IGNORECASE | re.DOTALL)
        if not title_match or not link_match:
            continue
        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
        url = re.sub(r"<[^>]+>", "", link_match.group(1)).strip()
        snippet = ""
        if desc_match:
            snippet = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()
        url = _clean_redirect_url(url)
        if not urlparse(url).netloc or url in seen:
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
        content_type = (response.headers.get("Content-Type") or "").lower()
        body = response.read().decode("utf-8", errors="replace")

    if "rss" in endpoint or "format=rss" in endpoint or "application/rss+xml" in content_type or body.lstrip().startswith("<?xml"):
        return _parse_bing_rss(body, max_results=20)
    return _parse_search_html(body, max_results=20, provider="duckduckgo")


def search_public_web(query: str, max_results: int = 5, timeout: int = 12) -> List[SearchResult]:
    """Search public web results without an API key, trying multiple providers."""
    errors: List[str] = []
    for endpoint in SEARCH_ENDPOINTS:
        provider = "bing_rss" if "bing.com" in endpoint else "duckduckgo"
        try:
            results = _fetch_search_endpoint(endpoint, query, timeout)
            if results:
                return results[:max_results]
            errors.append(f"{provider}: HTTP response contained no parseable results")
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
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
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
            evidence.append(EvidenceItem(claim_context=f"Public page discovered for {company}", source_url=result.url, source_title=result.title, snippet=text[:2500]))
        elif result.snippet:
            evidence.append(EvidenceItem(claim_context=f"Search result mentioning {company}", source_url=result.url, source_title=result.title, snippet=result.snippet))

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
