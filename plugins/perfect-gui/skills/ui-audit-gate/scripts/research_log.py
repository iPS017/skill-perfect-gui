#!/usr/bin/env python3
"""Journal de recherche Web et fiches de référence d'un run.

Sous-commandes :
  query       --text "..." --tool WebSearch [--urls U1 U2 ...] [--force]
  visit       --url U --tool WebFetch [--failed "raison"]
  unavailable --cause "..."
  ref         --json '{...}'      (fiche de référence, voir reference/research-protocol.md)
  list

Une référence 'consultee' ou 'revalidee' est refusée si son URL n'apparaît dans aucune requête
ni visite du run : on ne cite pas une source qu'on n'a pas vue.
"""
import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from _common import now_iso, read_json, write_json

REQUIRED_REF_FIELDS = ["titre", "url", "auteur_organisme", "statut_consultation", "rang_source", "question_etudiee", "limites_transposition"]
STATUSES = {"consultee", "revalidee", "memoire_non_revalidee", "inaccessible"}
SENSITIVE_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "adresse e-mail"),
    (re.compile(r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0)\b", re.I), "hôte local"),
    (re.compile(r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b"), "adresse IP privée"),
    (re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"), "chaîne qui ressemble à un jeton"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|xox[bap])[-_][A-Za-z0-9]{10,}"), "secret probable"),
]


def paths(run):
    run = Path(run)
    return run / "research" / "log.json", run / "research" / "references.json"


def normalize(url):
    parsed = urlparse(url.strip())
    return f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}" + (f"?{parsed.query}" if parsed.query else "")


def logged_urls(log):
    urls = {}
    for entry in log:
        for url in entry.get("urls", []) + ([entry["url"]] if entry.get("url") else []):
            if entry.get("type") == "visit" and entry.get("failed"):
                continue
            urls.setdefault(normalize(url), entry["at"])
            if entry.get("type") == "visit":
                urls[normalize(url)] = entry["at"]
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
            print(json.dumps({"status": "refused", "reason": "requête potentiellement sensible", "detected": hits,
                              "hint": "Reformuler en décrivant le motif d'interface, sans donnée du produit. --force seulement après vérification."}, ensure_ascii=False, indent=2))
            sys.exit(1)
        log.append({"type": "query", "at": now_iso(), "text": args.text, "tool": args.tool, "urls": args.urls, "results_count": args.results_count})
        write_json(log_path, log)
        print(json.dumps({"status": "ok", "logged": "query", "entries": len(log)}, ensure_ascii=False))
    elif args.command == "visit":
        if is_private_host(args.url):
            print(json.dumps({"status": "refused", "reason": "URL locale ou privée : ce n'est pas une référence Web"}, ensure_ascii=False))
            sys.exit(1)
        log.append({"type": "visit", "at": now_iso(), "url": args.url, "tool": args.tool, "failed": args.failed})
        write_json(log_path, log)
        print(json.dumps({"status": "ok", "logged": "visit", "entries": len(log)}, ensure_ascii=False))
    elif args.command == "unavailable":
        log.append({"type": "unavailable", "at": now_iso(), "cause": args.cause})
        write_json(log_path, log)
        print(json.dumps({"status": "ok", "logged": "unavailable", "consequence": "recherche.statut = non_realisee ; décision plafonnée à VALIDEE_PERIMETRE_TESTE"}, ensure_ascii=False))
    elif args.command == "ref":
        ref = json.loads(args.json)
        missing = [f for f in REQUIRED_REF_FIELDS if f not in ref or ref[f] in (None, "")]
        if missing:
            print(json.dumps({"status": "refused", "reason": "champs manquants", "missing": missing}, ensure_ascii=False))
            sys.exit(1)
        if ref["statut_consultation"] not in STATUSES:
            print(json.dumps({"status": "refused", "reason": f"statut_consultation doit valoir {sorted(STATUSES)}"}, ensure_ascii=False))
            sys.exit(1)
        seen = logged_urls(log)
        if ref["statut_consultation"] in ("consultee", "revalidee"):
            when = seen.get(normalize(ref["url"]))
            if not when:
                print(json.dumps({"status": "refused", "reason": "URL absente du journal de ce run : consigner la requête ou la visite d'abord (pas de source non vue)"}, ensure_ascii=False))
                sys.exit(1)
            ref["date_consultation"] = when
        ref.setdefault("date_publication_ou_maj", None)
        ref.setdefault("constats_cles", [])
        ref.setdefault("utilisee_pour", [])
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
        if ref["statut_consultation"] in ("consultee", "revalidee"):
            cache = [c for c in cache if normalize(c["url"]) != normalize(ref["url"])] + [{k: ref[k] for k in ref if k != "utilisee_pour"}]
            write_json(cache_path, cache)
        print(json.dumps({"status": "ok", "id": ref["id"], "date_consultation": ref.get("date_consultation")}, ensure_ascii=False))
    else:
        print(json.dumps({"log": log, "references": refs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
