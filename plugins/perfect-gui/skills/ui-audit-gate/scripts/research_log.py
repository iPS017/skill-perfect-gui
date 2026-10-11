#!/usr/bin/env python3
"""Web research log and reference records for a run.

Subcommands:
  query       --text "..." --tool WebSearch [--urls U1 U2 ...] [--force]
  visit       --url U --tool WebFetch [--failed "reason"]
  unavailable --cause "..."
  ref         --json '{...}'      (reference record, see reference/research-protocol.md)
  list

A reference with access_status 'accessed' or 'revalidated' is refused if its URL appears in no
query or visit of the run: never cite a source you have not seen.
"""
import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from _common import now_iso, read_json, write_json

REQUIRED_REF_FIELDS = ["title", "url", "author_organization", "access_status", "source_rank", "question", "transfer_limits"]
STATUSES = {"accessed", "revalidated", "memory_not_revalidated", "unreachable"}
SENSITIVE_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "email address"),
    (re.compile(r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0)\b", re.I), "local host"),
    (re.compile(r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b"), "private IP address"),
    (re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"), "string that looks like a token"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|xox[bap])[-_][A-Za-z0-9]{10,}"), "likely secret"),
]


def paths(run):
    run = Path(run)
    return run / "research" / "log.json", run / "research" / "references.json"


def normalize(url):
    parsed = urlparse(url.strip())
    return f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}" + (f"?{parsed.query}" if parsed.query else "")


def visited_urls(log):
    urls = {}
    for entry in log:
        if entry.get("type") == "visit" and not entry.get("failed") and entry.get("url"):
            urls[normalize(entry["url"])] = entry["at"]
    return urls


def is_private_host(url):
    host = urlparse(url).hostname or ""
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return host in ("localhost",) or host.endswith(".local") or host.endswith(".internal")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run")
    sub = parser.add_subparsers(dest="command", required=True)
    q = sub.add_parser("query")
    q.add_argument("--text", required=True)
    q.add_argument("--tool", default="WebSearch")
    q.add_argument("--urls", nargs="*", default=[])
    q.add_argument("--results-count", type=int)
    q.add_argument("--force", action="store_true")
    v = sub.add_parser("visit")
    v.add_argument("--url", required=True)
    v.add_argument("--tool", default="WebFetch")
    v.add_argument("--failed")
    u = sub.add_parser("unavailable")
    u.add_argument("--cause", required=True)
    r = sub.add_parser("ref")
    r.add_argument("--json", required=True)
    sub.add_parser("list")
    args = parser.parse_args()

    log_path, refs_path = paths(args.run)
    log = read_json(log_path, []) or []
    refs = read_json(refs_path, []) or []

    if args.command == "query":
        hits = [label for pattern, label in SENSITIVE_PATTERNS if pattern.search(args.text)]
        if hits and not args.force:
            print(json.dumps({"status": "refused", "reason": "potentially sensitive query", "detected": hits,
                              "hint": "Rephrase by describing the interface pattern, without product data. Use --force only after checking."}, ensure_ascii=False, indent=2))
            sys.exit(1)
        log.append({"type": "query", "at": now_iso(), "text": args.text, "tool": args.tool, "urls": args.urls, "results_count": args.results_count})
        write_json(log_path, log)
        print(json.dumps({"status": "ok", "logged": "query", "entries": len(log)}, ensure_ascii=False))
    elif args.command == "visit":
        if is_private_host(args.url):
            print(json.dumps({"status": "refused", "reason": "local or private URL: this is not a Web reference"}, ensure_ascii=False))
            sys.exit(1)
        log.append({"type": "visit", "at": now_iso(), "url": args.url, "tool": args.tool, "failed": args.failed})
        write_json(log_path, log)
        print(json.dumps({"status": "ok", "logged": "visit", "entries": len(log)}, ensure_ascii=False))
    elif args.command == "unavailable":
        log.append({"type": "unavailable", "at": now_iso(), "cause": args.cause})
        write_json(log_path, log)
        print(json.dumps({"status": "ok", "logged": "unavailable", "consequence": "research.status = not_done; decision capped at VALIDATED_TESTED_SCOPE"}, ensure_ascii=False))
    elif args.command == "ref":
        ref = json.loads(args.json)
        missing = [f for f in REQUIRED_REF_FIELDS if f not in ref or ref[f] in (None, "")]
        if missing:
            print(json.dumps({"status": "refused", "reason": "missing fields", "missing": missing}, ensure_ascii=False))
            sys.exit(1)
        if ref["access_status"] not in STATUSES:
            print(json.dumps({"status": "refused", "reason": f"access_status must be one of {sorted(STATUSES)}"}, ensure_ascii=False))
            sys.exit(1)
        seen = visited_urls(log)
        if ref["access_status"] in ("accessed", "revalidated"):
            when = seen.get(normalize(ref["url"]))
            if not when:
                print(json.dumps({"status": "refused", "reason": "URL not traced as visited in this run: open the page and record it with `visit` first (a URL seen only in search results does not count as accessed)"}, ensure_ascii=False))
                sys.exit(1)
            ref["accessed_at"] = when
        ref.setdefault("published_or_updated", None)
        ref.setdefault("key_points", [])
        ref.setdefault("used_for", [])
        existing = next((x for x in refs if normalize(x["url"]) == normalize(ref["url"])), None)
        if existing:
            ref["id"] = existing["id"]
            refs = [ref if x is existing else x for x in refs]
        else:
            ref["id"] = f"REF-{len(refs) + 1:03d}"
            refs.append(ref)
        write_json(refs_path, refs)
        cache_path = Path(args.run).parent / "research-cache.json"
        cache = read_json(cache_path, []) or []
        if ref["access_status"] in ("accessed", "revalidated"):
            cache = [c for c in cache if normalize(c["url"]) != normalize(ref["url"])] + [{k: ref[k] for k in ref if k != "used_for"}]
            write_json(cache_path, cache)
        print(json.dumps({"status": "ok", "id": ref["id"], "accessed_at": ref.get("accessed_at")}, ensure_ascii=False))
    else:
        print(json.dumps({"log": log, "references": refs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
