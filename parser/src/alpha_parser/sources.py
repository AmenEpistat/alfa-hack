"""Discovery is separate from ingestion. All fetched pages remain untrusted data."""
import ipaddress
import json
import re
import socket
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
import feedparser
import httpx
import trafilatura
from lxml import html as lhtml
from .config import Settings
from .pdf import pieces
from .schemas import Chunk, Document
from .storage import Store, digest
from .article_metadata import article_metadata, clean_tree

USER_AGENT = "AlphaResearchMVP/0.1"


def canonical(url: str) -> str:
    u = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path or "/", urlencode(sorted(query)), ""))


def public_url(url: str):
    u = urlsplit(url)
    if u.scheme not in {"http", "https"} or not u.hostname or u.username or u.password:
        raise ValueError("a public HTTP(S) URL without credentials is required")
    if u.port not in (None, 80, 443):
        raise ValueError("nonstandard public port blocked")
    addresses = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80))
    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise ValueError("private, local or reserved address blocked")


class Fetcher:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.http_timeout, follow_redirects=False,
                                             headers={"User-Agent": USER_AGENT}, trust_env=False)
        self.count = 0
        self.last = {}
        self.robots = {}

    def close(self):
        self.client.close()

    def raw(self, url, types, *, internal=False, params=None, enforce_robots=False):
        # Redirect destinations are validated individually; retry budget includes all requests.
        for redirect in range(6):
            if not internal:
                public_url(url)
            if enforce_robots:
                self.allowed(url)
            domain = urlsplit(url).netloc
            for attempt in range(3):
                if self.count >= self.settings.max_requests:
                    raise RuntimeError("HTTP request budget exhausted")
                time.sleep(max(0, self.settings.request_delay - (time.monotonic() - self.last.get(domain, 0))))
                self.count += 1
                self.last[domain] = time.monotonic()
                try:
                    with self.client.stream("GET", url, params=params) as r:
                        if r.status_code in (301, 302, 303, 307, 308):
                            url = urljoin(str(r.url), r.headers["location"])
                            params = None
                            break
                        if r.status_code == 429 or r.status_code >= 500:
                            if attempt < 2:
                                time.sleep(.25 * (attempt + 1))
                                continue
                        r.raise_for_status()
                        kind = r.headers.get("content-type", "").split(";")[0].lower()
                        if not any(kind == t or (t.endswith("/*") and kind.startswith(t[:-1])) for t in types):
                            raise ValueError(f"unexpected content type: {kind}")
                        if int(r.headers.get("content-length", 0)) > self.settings.max_response_bytes:
                            raise ValueError("response size limit exceeded")
                        body = bytearray()
                        for block in r.iter_bytes():
                            body.extend(block)
                            if len(body) > self.settings.max_response_bytes:
                                raise ValueError("response size limit exceeded")
                        return bytes(body), str(r.url)
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt == 2:
                        raise
            else:
                raise RuntimeError("request attempts exhausted")
        raise ValueError("too many redirects")

    def allowed(self, url):
        u = urlsplit(url)
        origin = f"{u.scheme}://{u.netloc}"
        if origin not in self.robots:
            parser = RobotFileParser(origin + "/robots.txt")
            try:
                data, _ = self.raw(origin + "/robots.txt", ["text/plain", "text/html", "application/octet-stream"])
                text = data.decode("utf-8", errors="replace")
                directives = re.search(r"(?im)^\s*(?:user-agent|disallow|allow|sitemap|crawl-delay|host|request-rate|clean-param)\s*:", text)
                meaningful = "\n".join(line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
                if "<html" in text.lower() or "<!doctype" in text.lower() or "\x00" in text or (meaningful and not directives):
                    raise ValueError("robots.txt response is not a valid rules file")
                parser.parse(text.splitlines())
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    parser.parse([])
                else:
                    raise ValueError("robots.txt unavailable; collection deferred") from None
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch(USER_AGENT, url):
            raise ValueError("robots.txt disallows collection")
        delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*")
        if delay:
            time.sleep(max(0, delay - (time.monotonic() - self.last.get(u.netloc, 0))))

    def get(self, url, types):
        self.allowed(url)
        data, final = self.raw(url, types, enforce_robots=True)
        if urlsplit(final).netloc != urlsplit(url).netloc or urlsplit(final).path != urlsplit(url).path:
            # Check redirected resource's policy too; raw does not follow unchecked hosts.
            self.allowed(final)
        return data, final


def extract_html(store: Store, body: bytes, final_url: str, *, original_url=None, source_name=None, force=False, fetched_at=None):
    tree = lhtml.fromstring(body)
    cleaned = lhtml.tostring(clean_tree(tree), encoding="unicode")
    extracted = trafilatura.bare_extraction(cleaned, url=final_url, with_metadata=True,
                                        include_comments=False, include_tables=True, favor_precision=True)
    parsed = extracted.as_dict() if extracted else None
    if not parsed or not parsed.get("text", "").strip():
        raise ValueError("empty article extraction; may require browser or manual review")
    text = parsed["text"].strip()
    title, published, updated, date_evidence = article_metadata(tree, parsed)
    target = canonical(final_url)
    links = tree.xpath('//link[contains(translate(@rel,"CANONICAL","canonical"),"canonical")]/@href')
    if links:
        proposed = canonical(urljoin(final_url, links[0]))
        if urlsplit(proposed).hostname == urlsplit(final_url).hostname:
            target = proposed
    warnings = []
    if not published:
        warnings.append("Publication date is unknown; temporal relevance is unverified")
    if len(text) < 200:
        warnings.append("Suspiciously short article")
    chunks = [Chunk(text=part, char_start=a, char_end=b) for a, b, part in pieces(text)]
    doc = Document(source_type="external", source_name=source_name or urlsplit(final_url).hostname,
                   url=target, original_url=original_url or final_url,
                   title=title or target, author=parsed.get("author"),
                   published_at=published, publication_date_evidence=date_evidence,
                   updated_at=updated, language=parsed.get("language"),
                   **({"fetched_at": fetched_at} if fetched_at else {}),
                   content_hash=digest(text), extractor_version=f"trafilatura-{trafilatura.__version__}/alpha-3",
                   config_hash=digest("precision/clean-dialogs/verified-visible-dates/chunk1600/v3"),
                   quality="requires_review" if warnings else "extracted", warnings=warnings,
                   original_path=store.original(body, ".html"))
    return store.save_document("external:" + target, doc, chunks, force=force)


class Sources:
    def __init__(self, store: Store, settings: Settings, registry=None, fetcher=None):
        self.store, self.settings = store, settings
        self.fetcher = fetcher or Fetcher(settings)
        self.registry = json.loads(Path(registry or settings.config_dir / "sources.json").read_text(encoding="utf-8-sig"))["sources"]
        store.sources = self.registry

    def source(self, id_):
        spec = next((s for s in self.registry if s["id"] == id_ and s["enabled"]), None)
        if not spec:
            raise ValueError("source missing or disabled")
        return spec

    def discover(self, id_, limit=8):
        spec = self.source(id_)
        if spec["kind"] == "rss":
            data, final = self.fetcher.get(spec["url"], ["application/rss+xml", "application/atom+xml", "application/xml", "text/xml", "text/plain"])
            feed = feedparser.parse(data)
            if not feed.entries:
                raise ValueError("feed has no usable entries")
            return [{"url": urljoin(final, e.link), "title": e.get("title", ""), "source_id": id_,
                     "candidate_published_at": e.get("published"), "extracted": False} for e in feed.entries[:limit] if e.get("link")]
        if spec["kind"] == "api":
            data, _ = self.fetcher.get(spec["url"], ["application/json"])
            items = json.loads(data)
            if spec.get("items_key"):
                items = items[spec["items_key"]]
            return [{"url": x[spec.get("url_key", "url")], "title": x.get("title", ""), "source_id": id_, "extracted": False} for x in items[:limit]]
        data, final = self.fetcher.get(spec["url"], ["text/html"])
        tree = lhtml.fromstring(data)
        urls = []
        for a in tree.xpath(spec.get("link_xpath", "//main//a[@href]")):
            link = urljoin(final, a.get("href", ""))
            if urlsplit(link).hostname == spec["domain"] and link not in [x["url"] for x in urls]:
                urls.append({"url": link, "title": a.text_content().strip()[:300], "source_id": id_, "extracted": False})
        return urls[:limit]

    def fetch_article(self, url, source_id=None):
        cache = self.store.cache
        if cache is None:
            return self._fetch_article(url, source_id)
        from .cache import code_fingerprint
        here = Path(__file__).parent
        key = {"url": canonical(url), "source_id": source_id, "extractor": trafilatura.__version__,
               "code": code_fingerprint([here / "sources.py", here / "article_metadata.py"]),
               "registry": self.registry}

        def compute():
            result = self._fetch_article(url, source_id)
            if result["document"]["quality"] == "failed":
                raise ValueError("Article extraction failed")
            return self.store.source_bundle(result["document"])
        if getattr(self.store, "refresh_cache", False):
            bundle = compute()
            cache.put("articles", key, bundle, ttl=self.settings.article_cache_ttl)
            hit = False
        else:
            bundle, hit = cache.get_or_compute("articles", key, compute, ttl=self.settings.article_cache_ttl)
        document = self.store.import_source(bundle)
        return {"document": document, "skipped": hit, "cached": hit,
                "chunks": len(bundle["chunks"])}

    def _fetch_article(self, url, source_id=None):
        spec = self.source(source_id) if source_id else None
        body, final = self.fetcher.get(url, ["text/html", "application/xhtml+xml"])
        name = spec["name"] if spec and urlsplit(final).hostname == spec["domain"] else None
        try:
            return extract_html(self.store, body, final, original_url=url, source_name=name)
        except ValueError:
            if not self.settings.browser_fallback:
                raise
            body = self.browser(final)
            return extract_html(self.store, body, final, original_url=url, source_name=name)

    def browser(self, url):
        # Optional import: normal RSS/text PDF paths never need a browser.
        from playwright.sync_api import sync_playwright
        self.fetcher.allowed(url)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT, service_workers="block")

            def guard(route):
                try:
                    public_url(route.request.url)
                    if route.request.resource_type in {"image", "media", "font"}:
                        route.abort()
                    else:
                        if self.fetcher.count >= self.settings.max_requests:
                            raise RuntimeError("request budget")
                        self.fetcher.count += 1
                        route.continue_()
                except Exception:
                    route.abort()
            context.route("**/*", guard)
            try:
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=int(self.settings.http_timeout * 1000))
                body = page.content().encode()
                if len(body) > self.settings.max_response_bytes:
                    raise ValueError("browser DOM size limit exceeded")
                return body
            finally:
                browser.close()

    def collect(self, source_id, limit=3):
        results = []
        for item in self.discover(source_id, limit=min(limit, self.settings.max_pages)):
            try:
                results.append(self.fetch_article(item["url"], source_id))
            except Exception as exc:
                results.append({"url": item["url"], "error": type(exc).__name__, "quality": "failed"})
        return results

    def search_web(self, query, start, end):
        if not self.settings.searxng_url:
            return {"candidates": [], "gap": "SearXNG search API is not configured"}
        # No internal IDs or raw client data may enter an external query.
        if re.search(r"\b(?:U_\d+|F_\d+|group_\w+)\b", query, re.I):
            raise ValueError("internal identifier in external query")
        cache_key = digest(f"searx:{self.settings.searxng_url}:{query}:{start}:{end}:"
                           f"{self.settings.search_cache_ttl}:ru:search-v2")
        cached = None if getattr(self.store, "refresh_cache", False) else self.store.cache_get(cache_key)
        if cached is not None:
            return {**cached, "cached": True}
        if (start is None) != (end is None):
            raise ValueError("provide both dates or neither")
        # before is exclusive in common search engines; include the entire request day.
        before = (date.fromisoformat(str(end)) + timedelta(days=1)).isoformat() if end is not None else None
        dated_query = f"{query} after:{start} before:{before}" if start is not None else query
        data, _ = self.fetcher.raw(self.settings.searxng_url.rstrip("/") + "/search", ["application/json"], internal=True,
                                  params={"q": dated_query, "format": "json", "language": "ru"})
        result = {"candidates": [{"url": r["url"], "title": r.get("title", ""), "extracted": False} for r in json.loads(data).get("results", [])[:8]],
                  "gap": "Search engine date operators are advisory; verify article publication dates"}
        self.store.cache_put(cache_key, result, time.time() + self.settings.search_cache_ttl)
        return result
