from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


USER_AGENT = "research-workbench-ai-cad-discovery/1.0 (+https://github.com/Fasuiker)"
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_doi(value: str) -> str:
    raw = clean_text(value).lower()
    raw = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", raw)
    raw = re.sub(r"^doi:\s*", "", raw)
    return raw.rstrip(".,;)")


def normalize_arxiv_id(value: str) -> str:
    raw = clean_text(value)
    raw = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", raw, flags=re.I)
    raw = re.sub(r"\.pdf$", "", raw, flags=re.I)
    raw = re.sub(r"v\d+$", "", raw, flags=re.I)
    return raw


def normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def stable_id(candidate: dict[str, Any]) -> str:
    doi = normalize_doi(candidate.get("doi", ""))
    if doi:
        return f"doi:{doi}"
    arxiv_id = normalize_arxiv_id(candidate.get("arxiv_id", ""))
    if arxiv_id:
        return f"arxiv:{arxiv_id.lower()}"
    openalex_id = clean_text(candidate.get("openalex_id", "")).rsplit("/", 1)[-1]
    if openalex_id:
        return f"openalex:{openalex_id.lower()}"
    identity = "|".join(
        [
            normalized_title(candidate.get("title", "")),
            clean_text((candidate.get("authors") or [""])[0] if isinstance(candidate.get("authors"), list) else candidate.get("authors", "")).lower(),
            str(candidate.get("year") or ""),
        ]
    )
    return "title:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def parse_date(value: Any) -> str:
    raw = clean_text(value)
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    return "-".join(match.groups()) if match else ""


def arxiv_date(arxiv_id: str) -> str:
    match = re.match(r"^(\d{2})(\d{2})\.\d+", normalize_arxiv_id(arxiv_id))
    if not match:
        return ""
    yy, mm = int(match.group(1)), int(match.group(2))
    year = 2000 + yy if yy < 91 else 1900 + yy
    return f"{year:04d}-{mm:02d}-01"


def in_range(value: str, start: date, end: date) -> bool:
    parsed = parse_date(value)
    if not parsed:
        return False
    day = date.fromisoformat(parsed)
    return start <= day <= end


def request_bytes(url: str, *, attempts: int = 3, timeout: int = 35) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/atom+xml, text/plain;q=0.8"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"request failed: {url}: {last_error}")


def request_json(url: str) -> dict[str, Any]:
    return json.loads(request_bytes(url).decode("utf-8"))


def relevance(candidate: dict[str, Any], config: dict[str, Any]) -> tuple[int, list[str]]:
    title = clean_text(candidate.get("title")).lower()
    abstract = clean_text(candidate.get("abstract")).lower()
    haystack = f"{title} {abstract}"
    negative = [word for word in config.get("negative_keywords", []) if clean_text(word).lower() in haystack]
    if negative:
        return -10, [f"排除：{word}" for word in negative[:3]]

    strong_cad = bool(re.search(r"\bcad(?:/cam)?\b|\bb-?rep\b|computer-aided design|boundary representation|sketch extrusion|constructive solid geometry", haystack))
    parametric_design = "parametric" in haystack and any(
        signal in haystack
        for signal in ["geometric", "geometry", "solid model", "3d model", "product design", "engineering design", "manufactur", "fabricat"]
    )
    if not (strong_cad or parametric_design):
        return 0, []

    ai_terms = ["neural", "machine learning", "deep learning", "diffusion", "transformer", "language model", "artificial intelligence", "ai/ml", "agent", "generative"]
    ai_signal = any(term in haystack for term in ai_terms)
    curated = any("awesome" in clean_text(name).lower() for name in candidate.get("source_names", []))
    if not (ai_signal or curated):
        return 0, []

    score = 4 if strong_cad else 3
    reasons: list[str] = []
    for word in config.get("domain_boost_keywords", []):
        term = clean_text(word).lower()
        if term and term in title:
            score += 4
            reasons.append(f"标题命中 {word}")
        elif term and term in abstract:
            score += 2
            reasons.append(f"摘要命中 {word}")
    for word in config.get("keywords", []):
        term = clean_text(word).lower()
        if not term or any(term == clean_text(x).lower() for x in config.get("domain_boost_keywords", [])):
            continue
        if term in title:
            score += 2
            reasons.append(f"标题命中 {word}")
        elif term in abstract:
            score += 1
            reasons.append(f"摘要命中 {word}")
    if ai_signal:
        score += 2
    return score, list(dict.fromkeys(reasons))[:8]


def suggested_category(candidate: dict[str, Any]) -> str:
    text = f"{candidate.get('title', '')} {candidate.get('abstract', '')}".lower()
    rules = [
        ("Surveys & Roadmaps", ["survey", "review", "roadmap", "taxonomy"]),
        ("LLM, VLM & CAD Agents", ["language model", "llm", "vlm", "agent"]),
        ("CAD Editing, Constraints & Verification", ["editing", "constraint", "verification", "repair"]),
        ("CAD Reconstruction & Reverse Engineering", ["reconstruction", "reverse engineering", "point cloud to cad", "image-to-cad"]),
        ("CAD Representations & Understanding", ["representation", "segmentation", "recognition", "understanding", "retrieval"]),
        ("Datasets, Benchmarks & Evaluation", ["dataset", "benchmark", "evaluation", "metric"]),
        ("Open-source Systems & Tools", ["system", "toolkit", "plugin", "platform"]),
    ]
    for label, terms in rules:
        if any(term in text for term in terms):
            return label
    return "CAD Generation"


def canonical_candidate(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    authors = row.get("authors") or []
    if isinstance(authors, str):
        authors = [clean_text(x) for x in re.split(r";|\band\b", authors) if clean_text(x)]
    published_at = parse_date(row.get("published_at"))
    score, reasons = relevance(row, config)
    candidate = {
        "stable_id": "",
        "title": clean_text(row.get("title")) or "Untitled",
        "authors": authors,
        "abstract": clean_text(row.get("abstract")),
        "year": int(published_at[:4]) if published_at else row.get("year"),
        "published_at": published_at or None,
        "venue": clean_text(row.get("venue")),
        "doi": normalize_doi(row.get("doi", "")),
        "arxiv_id": normalize_arxiv_id(row.get("arxiv_id", "")),
        "openalex_id": clean_text(row.get("openalex_id")),
        "source_url": clean_text(row.get("source_url")),
        "pdf_url": clean_text(row.get("pdf_url")),
        "oa_status": clean_text(row.get("oa_status")),
        "license": clean_text(row.get("license")),
        "suggested_category": clean_text(row.get("suggested_category")) or suggested_category(row),
        "matched_terms": reasons,
        "source_names": list(dict.fromkeys(row.get("source_names") or [])),
        "relevance_score": score,
        "discovered_at": clean_text(row.get("discovered_at")) or utcnow().isoformat(),
    }
    candidate["stable_id"] = stable_id(candidate)
    return candidate


def merge_candidates(rows: Iterable[dict[str, Any]], config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config = config or {"keywords": [], "domain_boost_keywords": [], "negative_keywords": [], "relevance_threshold": 0}
    merged: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = canonical_candidate(raw, config) if "stable_id" not in raw else dict(raw)
        key = row.get("stable_id") or stable_id(row)
        row["stable_id"] = key
        current = merged.get(key)
        if current is None:
            merged[key] = row
            continue
        for field in ["title", "abstract", "venue", "doi", "arxiv_id", "openalex_id", "source_url", "pdf_url", "oa_status", "license", "published_at"]:
            if len(clean_text(row.get(field))) > len(clean_text(current.get(field))):
                current[field] = row.get(field)
        if len(row.get("authors") or []) > len(current.get("authors") or []):
            current["authors"] = row.get("authors")
        current["source_names"] = list(dict.fromkeys((current.get("source_names") or []) + (row.get("source_names") or [])))
        current["matched_terms"] = list(dict.fromkeys((current.get("matched_terms") or []) + (row.get("matched_terms") or [])))[:8]
        current["relevance_score"] = max(int(current.get("relevance_score") or 0), int(row.get("relevance_score") or 0))
    return sorted(merged.values(), key=lambda row: (row.get("published_at") or "", row.get("relevance_score") or 0, row.get("title") or ""), reverse=True)


def discover_arxiv(config: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    categories = [f"cat:{category}" for category in config.get("arxiv_categories", [])]
    cad_terms = ['all:CAD', 'all:"computer-aided design"', 'all:"B-Rep"', 'all:"boundary representation"', 'all:"parametric design"']
    ai_terms = ['all:neural', 'all:"machine learning"', 'all:generative', 'all:diffusion', 'all:transformer', 'all:"language model"', 'all:agent']
    date_range = f"submittedDate:[{start:%Y%m%d}0000 TO {end:%Y%m%d}2359]"
    query = f"({' OR '.join(cad_terms)}) AND ({' OR '.join(ai_terms)}) AND ({' OR '.join(categories)}) AND {date_range}"
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": min(int(config.get("max_results_per_source", 300)), 500),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    root = ET.fromstring(request_bytes("https://export.arxiv.org/api/query?" + params))
    rows: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        links = entry.findall("atom:link", ARXIV_NS)
        source_url = next((link.attrib.get("href", "") for link in links if link.attrib.get("rel") == "alternate"), "")
        pdf_url = next((link.attrib.get("href", "") for link in links if link.attrib.get("type") == "application/pdf"), "")
        arxiv_id = normalize_arxiv_id(entry.findtext("atom:id", default="", namespaces=ARXIV_NS))
        doi = entry.findtext("arxiv:doi", default="", namespaces=ARXIV_NS)
        rows.append(
            {
                "title": entry.findtext("atom:title", default="", namespaces=ARXIV_NS),
                "authors": [clean_text(a.findtext("atom:name", default="", namespaces=ARXIV_NS)) for a in entry.findall("atom:author", ARXIV_NS)],
                "abstract": entry.findtext("atom:summary", default="", namespaces=ARXIV_NS),
                "published_at": entry.findtext("atom:published", default="", namespaces=ARXIV_NS),
                "venue": "arXiv",
                "doi": doi,
                "arxiv_id": arxiv_id,
                "source_url": source_url or f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": pdf_url or f"https://arxiv.org/pdf/{arxiv_id}",
                "oa_status": "green",
                "license": "arXiv",
                "source_names": ["arXiv"],
            }
        )
    return rows


def inverted_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    slots: dict[int, str] = {}
    for word, positions in index.items():
        for position in positions:
            slots[int(position)] = word
    return " ".join(slots[i] for i in sorted(slots))


def discover_openalex(config: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    api_key = os.getenv("OPENALEX_API_KEY", "").strip()
    for query in config.get("openalex_queries", []):
        params: dict[str, Any] = {
            "search": query,
            "filter": f"from_publication_date:{start.isoformat()},to_publication_date:{end.isoformat()}",
            "per-page": min(int(config.get("max_results_per_source", 300)), 100),
        }
        if api_key:
            params["api_key"] = api_key
        data = request_json("https://api.openalex.org/works?" + urllib.parse.urlencode(params))
        for work in data.get("results", []):
            primary = work.get("primary_location") or {}
            best = work.get("best_oa_location") or {}
            oa = work.get("open_access") or {}
            authors = [clean_text((item.get("author") or {}).get("display_name")) for item in work.get("authorships", [])]
            rows.append(
                {
                    "title": work.get("display_name"),
                    "authors": authors,
                    "abstract": inverted_abstract(work.get("abstract_inverted_index")),
                    "published_at": work.get("publication_date"),
                    "venue": clean_text((primary.get("source") or {}).get("display_name")),
                    "doi": work.get("doi"),
                    "openalex_id": work.get("id"),
                    "source_url": primary.get("landing_page_url") or work.get("doi") or work.get("id"),
                    "pdf_url": best.get("pdf_url") or "",
                    "oa_status": oa.get("oa_status") or ("open" if oa.get("is_oa") else "closed"),
                    "license": best.get("license") or "",
                    "source_names": ["OpenAlex"],
                }
            )
        time.sleep(0.15)
    return rows


def crossref_date(item: dict[str, Any]) -> str:
    for key in ["published-online", "published-print", "published", "issued", "created"]:
        parts = ((item.get(key) or {}).get("date-parts") or [[]])[0]
        if parts:
            values = [int(x) for x in parts]
            return f"{values[0]:04d}-{values[1] if len(values) > 1 else 1:02d}-{values[2] if len(values) > 2 else 1:02d}"
    return ""


def discover_crossref(config: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mailto = os.getenv("CROSSREF_MAILTO", "").strip()
    for query in config.get("crossref_queries", []):
        params: dict[str, Any] = {
            "query.bibliographic": query,
            "filter": f"from-pub-date:{start.isoformat()},until-pub-date:{end.isoformat()}",
            "rows": min(int(config.get("max_results_per_source", 300)), 100),
            "sort": "published",
            "order": "desc",
        }
        if mailto:
            params["mailto"] = mailto
        data = request_json("https://api.crossref.org/works?" + urllib.parse.urlencode(params))
        for item in (data.get("message") or {}).get("items", []):
            licenses = item.get("license") or []
            license_url = clean_text(licenses[0].get("URL") if licenses else "")
            links = item.get("link") or []
            pdf = ""
            if "creativecommons.org" in license_url.lower() or "publicdomain" in license_url.lower():
                pdf = next((clean_text(link.get("URL")) for link in links if "pdf" in clean_text(link.get("content-type")).lower()), "")
            title = clean_text((item.get("title") or [""])[0])
            authors = [clean_text(" ".join(filter(None, [a.get("given"), a.get("family")]))) for a in item.get("author", [])]
            doi = normalize_doi(item.get("DOI", ""))
            rows.append(
                {
                    "title": title,
                    "authors": authors,
                    "abstract": re.sub(r"<[^>]+>", " ", clean_text(item.get("abstract"))),
                    "published_at": crossref_date(item),
                    "venue": clean_text((item.get("container-title") or [""])[0]),
                    "doi": doi,
                    "source_url": clean_text(item.get("URL")) or (f"https://doi.org/{doi}" if doi else ""),
                    "pdf_url": pdf,
                    "oa_status": "open" if pdf else "unknown",
                    "license": license_url,
                    "source_names": ["Crossref"],
                }
            )
        time.sleep(0.15)
    return rows


LINK_RE = re.compile(r"\[([^\]]{3,500})\]\((https?://[^)\s]+)\)")


def discover_upstreams(config: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_name, readme_url in (config.get("upstream_readmes") or {}).items():
        markdown = request_bytes(readme_url).decode("utf-8", errors="replace")
        for title, url in LINK_RE.findall(markdown):
            arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d+(?:v\d+)?)", url, flags=re.I)
            doi_match = re.search(r"(?:doi\.org/|doi:)(10\.\d{4,9}/[^\s)]+)", url, flags=re.I)
            arxiv_id = normalize_arxiv_id(arxiv_match.group(1)) if arxiv_match else ""
            published = arxiv_date(arxiv_id)
            if published and not in_range(published, start, end):
                continue
            if not published:
                continue
            rows.append(
                {
                    "title": re.sub(r"[*_`]", "", title),
                    "authors": [],
                    "abstract": "",
                    "published_at": published,
                    "venue": "",
                    "doi": normalize_doi(doi_match.group(1)) if doi_match else "",
                    "arxiv_id": arxiv_id,
                    "source_url": url,
                    "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
                    "oa_status": "green" if arxiv_id else "unknown",
                    "license": "arXiv" if arxiv_id else "",
                    "source_names": [source_name],
                }
            )
    return rows


def run(config: dict[str, Any], start: date, end: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []
    health: dict[str, Any] = {}
    sources = [
        ("arxiv", discover_arxiv),
        ("openalex", discover_openalex),
        ("crossref", discover_crossref),
        ("upstream_awesome", discover_upstreams),
    ]
    enabled_sources = set(config.get("sources") or [name for name, _ in sources])
    for name, discoverer in sources:
        if name not in enabled_sources:
            health[name] = {"ok": True, "count": 0, "skipped": True, "seconds": 0}
            continue
        started = time.monotonic()
        try:
            rows = discoverer(config, start, end)
            all_rows.extend(rows)
            health[name] = {"ok": True, "count": len(rows), "seconds": round(time.monotonic() - started, 2)}
        except Exception as exc:  # one source must not erase the whole daily feed
            health[name] = {"ok": False, "count": 0, "error": clean_text(exc)[:500], "seconds": round(time.monotonic() - started, 2)}
    merged = merge_candidates(all_rows, config)
    threshold = int(config.get("relevance_threshold", 4))
    return [row for row in merged if int(row.get("relevance_score") or 0) >= threshold], health


def write_feed(output: Path, archive_dir: Path | None, config: dict[str, Any], start: date, end: date, candidates: list[dict[str, Any]], health: dict[str, Any]) -> None:
    generated_at = utcnow().isoformat()
    payload = {
        "schema_version": 1,
        "profile": config.get("profile", "ai-cad"),
        "generated_at": generated_at,
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "count": len(candidates),
        "source_health": health,
        "public_profile": {
            "keywords": config.get("keywords", []),
            "negative_keywords": config.get("negative_keywords", []),
            "arxiv_categories": config.get("arxiv_categories", []),
            "sources": config.get("sources", []),
            "collection_window_days": int(config.get("daily_search_days", 3)),
        },
        "candidates": candidates,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "profile": payload["profile"],
        "generated_at": generated_at,
        "latest": output.as_posix(),
        "count": len(candidates),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "range": payload["range"],
    }
    (output.parent / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if archive_dir:
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{end.isoformat()}.json"
        archive_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cutoff = end - timedelta(days=90)
        for old in archive_dir.glob("????-??-??.json"):
            try:
                if date.fromisoformat(old.stem) < cutoff:
                    old.unlink()
            except ValueError:
                continue


def cli() -> int:
    parser = argparse.ArgumentParser(description="Discover AI+CAD candidate papers from public scholarly metadata")
    parser.add_argument("--config", default="config/ai-cad.json")
    parser.add_argument("--output", default="data/latest.json")
    parser.add_argument("--archive-dir", default="data/archive")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--search-days", type=int)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    end = date.fromisoformat(args.to_date) if args.to_date else utcnow().date()
    days = args.search_days or int(config.get("daily_search_days", 3))
    start = date.fromisoformat(args.from_date) if args.from_date else end - timedelta(days=max(1, days) - 1)
    if start > end:
        parser.error("from-date must not be later than to-date")

    candidates, health = run(config, start, end)
    write_feed(Path(args.output), Path(args.archive_dir) if args.archive_dir else None, config, start, end, candidates, health)
    print(json.dumps({"from": start.isoformat(), "to": end.isoformat(), "count": len(candidates), "source_health": health}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
