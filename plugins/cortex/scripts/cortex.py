#!/usr/bin/env python3
"""cortex - the engine behind the cortex plugin.

Standard library only. Every command finds the vault from ~/.cortex/config.json
unless --vault is given. The contract this file implements is docs/SPEC.md;
change the spec first, then this file.

Commands:
  build                 validate every page, then write _cortex/{index,card,followups}.md and home.md
  check FILE...         validate only the named pages
  card                  print the start card
  new TYPE --area A [--thing T] [--collection C] --title "..."
                        print the right path, id and a frontmatter skeleton
  backup [--if-older-than-days N] [--quiet]
                        commit everything and push; log to _cortex/backup.log
  history [--days N]    the person's own typed requests + session summaries (input for Suggest)
  sort-desk             print the sorting desk
  doctor                health check in plain words
  install-backup        weekly backup LaunchAgent (Sundays 18:00 local)
  feedback --type T --message M [--name N --email E --org O --contact yes|no] [--dry-run]
                        submit to the maker's feedback form (the skill shows it and asks first)
  board [--open] [--port N] [--no-browser]
                        the board and inbox page on this Mac only (scripts/board.py)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
CONFIG = Path(os.environ.get("CORTEX_CONFIG", HOME / ".cortex" / "config.json"))
GENERATED = "_cortex"
SKIP_DIRS = {".git", ".claude", GENERATED, "sources", "_templates", "node_modules"}
# Files that are not pages: README.md and CLAUDE.md in any folder; the vault's own instruction and
# home files at the root (AGENTS.md and GEMINI.md since 0.3.0).
NOT_PAGES_ANYWHERE = {"CLAUDE.md", "README.md"}
NOT_PAGES_AT_ROOT = {"AGENTS.md", "GEMINI.md", "home.md"}
HEADER_KEY_RE = re.compile(r"^(id|title|type|status|created|updated|summary|area|tags|links):\s")
ANY_KEY_RE = re.compile(r"^[A-Za-z_][\w-]*:(\s|$)")  # any 'key: value' line right after an opening ---

THING_TYPES = {"session", "decision", "lesson", "insight", "how-to"}
TYPE_FOLDER = {"session": "sessions", "decision": "decisions", "lesson": "lessons",
               "insight": "insights", "how-to": "how-to"}
ALL_TYPES = THING_TYPES | {"thing", "area", "person", "organisation", "meeting", "note"}
STATUSES = {"active", "done", "superseded", "archived", "draft"}
REQUIRED = ["id", "title", "type", "status", "created", "updated", "summary"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# A task line: - [ ] @person what (due D) (added D) (done D) {mine|theirs} {doing}
# The dated parts are optional and in any order; {doing} is optional and comes last (0.4.0).
FOLLOWUP_RE = re.compile(
    r"^(?P<indent>\s*)-\s\[(?P<done>[ xX])\]\s+@(?P<person>[a-z0-9-]+)\s+(?P<text>.*?)"
    r"(?P<meta>(?:\s*\((?:due|added|done)\s+\d{4}-\d{2}-\d{2}\))*)"
    r"\s*\{(?P<owner>mine|theirs)\}(?:\s*\{(?P<doing>doing)\})?(?P<trail>\s*)$")
META_RE = re.compile(r"\((due|added|done)\s+(\d{4}-\d{2}-\d{2})\)")


# ---------------------------------------------------------------- config / vault

def load_config() -> dict:
    try:
        return json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        return {}


def vault_path(arg: str | None = None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    cfg = load_config()
    if not cfg.get("vault"):
        sys.exit("Cortex is not set up yet. Say 'set up my cortex' in Claude to begin.")
    return Path(cfg["vault"]).expanduser().resolve()


def today() -> str:
    return dt.date.today().isoformat()


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)[:70].strip("-") or "untitled"


# ---------------------------------------------------------------- frontmatter

class Page:
    def __init__(self, path: Path, rel: str, meta: dict, body: str, errors: list[str]):
        self.path, self.rel, self.meta, self.body, self.errors = path, rel, meta, body, errors

    def get(self, key, default=""):
        return self.meta.get(key, default)


def parse_value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [v.strip().strip("'\"") for v in inner.split(",") if v.strip()] if inner else []
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    return raw


def read_page(path: Path, vault: Path) -> Page:
    rel = path.relative_to(vault).as_posix()
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return Page(path, rel, {}, "", [f"cannot read file ({e})"])
    text = text.lstrip("\ufeff")  # Windows editors add a byte-order mark
    head = [l for l in text.splitlines()[:12] if l.strip() and not l.lstrip().startswith("#")]
    after_rule = head[1:4] if head and head[0].strip() == "---" else []
    # An opening --- starts a header only if a known header key follows, or two 'key: value' lines do;
    # '---' then 'Agenda: ...' is a scribble.
    opens_header = bool(after_rule) and (HEADER_KEY_RE.match(after_rule[0]) is not None
                                         or sum(bool(ANY_KEY_RE.match(l)) for l in after_rule[:2]) == 2)
    lead = 0  # lines dropped before the header, so task line numbers still match the file
    if opens_header:
        lead = text[:len(text) - len(text.lstrip())].count("\n")
        text = text.lstrip()  # a real header after a blank line or a space
    if not text.startswith("---\n") or not opens_header:
        # Looks like a header that lost its opening ---: two or more header keys before a --- line.
        keys_before_rule = 0
        for l in head:
            if l.strip() == "---":
                break
            keys_before_rule += bool(HEADER_KEY_RE.match(l))
        if keys_before_rule >= 2 and any(l.strip() == "---" for l in head):
            return Page(path, rel, {}, text, ["header is broken - it must start with a line of just ---"])
        # Anything else with no header (an empty Obsidian daily note, a scribble, a note with a --- divider)
        # is a loose note: it waits on the sorting desk instead of stopping the build.
        page = Page(path, rel, {}, text, [])
        page.loose = True
        return page
    end = text.find("\n---", 4)
    if end == -1:
        return Page(path, rel, {}, text, ["frontmatter is not closed with ---"])
    meta: dict = {}
    for n, line in enumerate(text[4:end].splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t", "-")):
            errors.append(f"line {n}: nested or list-style YAML is not allowed - use key: [a, b]")
            continue
        if ": " not in line and not line.rstrip().endswith(":"):
            errors.append(f"line {n}: expected 'key: value', got '{line.strip()}'")
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key in meta:
            errors.append(f"line {n}: '{key}' appears twice")
        meta[key] = parse_value(value)
    body = text[end + 4:].lstrip("\n")
    page = Page(path, rel, meta, body, errors)
    page.body_line = lead + text[:len(text) - len(body)].count("\n") + 1
    return page


def iter_pages(vault: Path):
    for root, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.endswith(".md") and f not in NOT_PAGES_ANYWHERE and not (root == str(vault) and f in NOT_PAGES_AT_ROOT):
                p = Path(root) / f
                yield read_page(p, vault)


# ---------------------------------------------------------------- expected id / location

def expected_id(page: Page) -> str | None:
    t, area, thing = page.get("type"), page.get("area"), page.get("thing")
    stem = page.path.stem
    parts = Path(page.rel).parts
    if t == "person":
        return f"person-{stem}"
    if t == "organisation":
        return f"organisation-{stem}"
    if t == "area":
        return f"area-{area}"
    if t == "thing":
        return f"thing-{area}-{parts[-2] if len(parts) >= 2 else stem}"
    if t in THING_TYPES and thing:
        return f"{t}-{area}-{thing}-{stem}"
    if t == "note" and parts[0] == "inbox":
        return f"note-inbox-{stem}"
    if t in ("meeting", "note") or t in THING_TYPES:
        return f"{t}-{area}-{stem}" if area else f"{t}-{stem}"
    return None


def location_errors(page: Page) -> list[str]:
    t, area, thing = page.get("type"), page.get("area"), page.get("thing")
    parts = Path(page.rel).parts
    errs = []
    if t == "person" and parts[0] != "people":
        errs.append("person pages live in people/")
    elif t == "organisation" and parts[0] != "organisations":
        errs.append("organisation pages live in organisations/")
    elif t == "area" and (len(parts) != 2 or parts[1] != "_index.md" or parts[0] != area):
        errs.append(f"area page must be {area}/_index.md")
    elif t == "thing":
        if len(parts) != 4 or parts[0] != area or parts[-1] != "_index.md":
            errs.append(f"thing page must be {area}/<collection>/<thing>/_index.md")
    elif t == "meeting" and (len(parts) != 3 or parts[0] != area or parts[1] != "meetings"):
        errs.append(f"meeting pages live in {area}/meetings/")
    elif t in THING_TYPES and thing:
        want = TYPE_FOLDER[t]
        if len(parts) != 5 or parts[0] != area or parts[2] != thing or parts[3] != want:
            errs.append(f"{t} for '{thing}' must live in {area}/<collection>/{thing}/{want}/")
    elif t in THING_TYPES and not thing and parts[0] != area:
        errs.append(f"{t} page must sit under its area folder '{area}/'")
    return errs


# ---------------------------------------------------------------- validation

def validate(pages: list[Page], vault: Path, people: set[str]) -> tuple[list[str], list[str]]:
    me = self_slugs(vault)
    headerless_people = {Path(rel).stem for rel in loose_notes(vault) if rel.startswith("people/")}
    errors, warnings = [], []
    all_ids = {p.get("id") for p in pages if p.get("id")}
    seen: dict[str, str] = {}
    for p in pages:
        pe = list(p.errors)
        m = p.meta
        if not p.errors:
            for k in REQUIRED:
                if not m.get(k):
                    pe.append(f"missing '{k}'")
            t = m.get("type")
            if t and t not in ALL_TYPES:
                pe.append(f"type '{t}' is not one of: {', '.join(sorted(ALL_TYPES))}")
            if m.get("status") and m["status"] not in STATUSES:
                pe.append(f"status '{m['status']}' is not one of: {', '.join(sorted(STATUSES))}")
            if m.get("status") == "superseded" and not m.get("superseded_by"):
                pe.append("status superseded needs 'superseded_by: <id>'")
            for k in ("created", "updated", "date", "due"):
                if m.get(k) and not DATE_RE.match(str(m[k])):
                    pe.append(f"'{k}' must be YYYY-MM-DD")
            in_inbox = t == "note" and p.rel.startswith("inbox/")
            if t not in ("person", "organisation") and t and not in_inbox and not m.get("area"):
                pe.append("missing 'area'")
            if t == "meeting":
                if not m.get("date"):
                    pe.append("meeting needs 'date'")
                if not isinstance(m.get("people"), list):
                    pe.append("meeting needs 'people: [slug, ...]'")
            for k in ("tags", "links", "sources", "people"):
                if k in m and not isinstance(m[k], list):
                    pe.append(f"'{k}' must be a list like [a, b]")
            if not SLUG_RE.match(p.path.stem) and p.path.name != "_index.md":
                pe.append(f"file name '{p.path.name}' must be lowercase words joined by hyphens")
            if t in ALL_TYPES:
                pe += location_errors(p)
                exp = expected_id(p)
                if exp and m.get("id") and m["id"] != exp:
                    pe.append(f"id should be '{exp}' (it is '{m['id']}')")
            pid = m.get("id")
            if pid:
                if pid in seen:
                    pe.append(f"id '{pid}' is also used by {seen[pid]}")
                seen[pid] = p.rel
            for link in m.get("links", []) if isinstance(m.get("links"), list) else []:
                if link not in all_ids:
                    pe.append(f"link '{link}' points to a page that does not exist")
            for src in m.get("sources", []) if isinstance(m.get("sources"), list) else []:
                if not (vault / src).exists():
                    pe.append(f"source '{src}' is not in the vault")
            if m.get("superseded_by") and m["superseded_by"] not in all_ids:
                pe.append(f"superseded_by '{m['superseded_by']}' does not exist")
            for line in p.body.splitlines():
                fm = FOLLOWUP_RE.match(line)
                who = fm.group("person") if fm else ""
                if fm and who in headerless_people:
                    pe.append(f"follow-up names @{who} but people/{who}.md has no header")
                elif fm and who not in people and who not in me:
                    pe.append(f"follow-up names @{who} but people/{who}.md does not exist")
                elif fm and who in me and fm.group("owner") == "theirs":
                    warnings.append(f"{p.rel}: '@{who} ... {{theirs}}' reads as owed to yourself - use {{mine}} for your own to-do")
                elif re.match(r"^\s*-\s\[[ xX]\]\s+@", line) and not fm:
                    warnings.append(f"{p.rel}: follow-up line not in the standard shape: '{line.strip()[:80]}'")
        for e in pe:
            errors.append(f"{p.rel}: {e}")
    by_id = {p.get("id"): p for p in pages if p.get("id")}
    for p in pages:
        for link in p.get("links", []) if isinstance(p.get("links"), list) else []:
            other = by_id.get(link)
            if other and p.get("id") not in (other.get("links") or []):
                warnings.append(f"{p.rel}: links to '{link}' but that page does not link back")
    return errors, warnings


# ---------------------------------------------------------------- generated files

def self_slugs(vault: Path) -> set[str]:
    """Who 'I' am in follow-up lines: @me, or the person's own slug from kit.yaml."""
    name = parse_kit(vault).get("name") or ""
    return {"me"} | ({slugify(str(name))} if name else set())


def parse_task(line: str, me: set[str] = frozenset({"me"})) -> dict | None:
    """One task line, or None. Dates: due, added, done ('' when absent; the last one wins)."""
    m = FOLLOWUP_RE.match(line)
    if not m:
        return None
    dates = dict(META_RE.findall(m.group("meta")))
    return {"person": m.group("person"), "text": m.group("text").strip(), "owner": m.group("owner"),
            "closed": m.group("done") != " ", "due": dates.get("due", ""), "added": dates.get("added", ""),
            "done": dates.get("done", ""), "doing": bool(m.group("doing")),
            "todo": m.group("person") in me and m.group("owner") == "mine", "raw": line}


def followups(pages: list[Page], me: set[str] = frozenset({"me"})) -> list[dict]:
    """Open task lines. A line I owe to myself (@me, or my own slug) is a to-do, not a follow-up:
    follow-ups are promises between people, to-dos are my own work."""
    out = []
    for p in pages:
        first = getattr(p, "body_line", 1)
        for n, line in enumerate(p.body.split("\n")):
            t = parse_task(line, me)
            if t and not t["closed"]:
                t.update(page=p.rel, page_title=p.get("title"), line=first + n)
                out.append(t)
    return out


def write_atomic(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if isinstance(text, bytes):
        tmp.write_bytes(text)
    else:
        tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def render_index(pages: list[Page]) -> str:
    rows = ["# Index", "", f"Generated {today()} - every page in the cortex. Do not edit by hand.", "",
            "| id | type | area | status | updated | summary |", "|---|---|---|---|---|---|"]
    for p in sorted(pages, key=lambda x: (x.get("area"), x.get("type"), x.rel)):
        summ = str(p.get("summary")).replace("|", "/")
        rows.append(f"| [{p.get('id')}]({'../' + p.rel}) | {p.get('type')} | {p.get('area') or '-'} | "
                    f"{p.get('status')} | {p.get('updated')} | {summ} |")
    return "\n".join(rows) + "\n"


def render_followups(items: list[dict]) -> str:
    now = today()
    lines = ["# Open follow-ups", "", f"Generated {now}. Close one by changing its `- [ ]` to `- [x]` on the page it comes from.", ""]
    groups = (("My to-dos", lambda i: i["todo"]), ("I owe", lambda i: i["owner"] == "mine" and not i["todo"]),
              ("Owed to me", lambda i: i["owner"] == "theirs"))
    for label, keep in groups:
        group = sorted((i for i in items if keep(i)), key=lambda i: (i["due"] or "9999", i["person"]))
        lines += [f"## {label} ({len(group)})", ""]
        if not group:
            lines += ["Nothing open.", ""]
            continue
        lines += ["| person | what | due | from page |", "|---|---|---|---|"]
        for i in group:
            due = i["due"] or "-"
            if i["due"] and i["due"] < now:
                due += " OVERDUE"
            lines.append(f"| @{i['person']} | {i['text']} | {due} | [{i['page_title']}](../{i['page']}) |")
        lines.append("")
    return "\n".join(lines)


def last_backup(vault: Path) -> str | None:
    log = vault / GENERATED / "backup.log"
    try:
        for line in reversed(log.read_text().splitlines()):
            if " pushed" in line or " committed" in line or " nothing to back up" in line:
                return line[:10]
    except OSError:
        pass
    return None


def render_card(pages: list[Page], items: list[dict], vault: Path) -> str:
    now = dt.date.today()
    cfg = parse_kit(vault)
    name = cfg.get("name", "")
    lines = [f"# Cortex card{' - ' + name if name else ''}", "", f"As of {now.isoformat()}.", ""]
    areas = [p for p in pages if p.get("type") == "area"]
    if areas:
        lines.append("Areas: " + ", ".join(sorted(p.get("area") for p in areas)))
        lines.append("")
    things = [p for p in pages if p.get("type") == "thing" and p.get("status") == "active"]
    sessions = sorted((p for p in pages if p.get("type") == "session"), key=lambda p: str(p.get("updated")), reverse=True)
    last_by_thing: dict[str, Page] = {}
    for s in sessions:
        last_by_thing.setdefault(f"{s.get('area')}/{s.get('thing')}", s)
    if things:
        lines += ["## Active", ""]
        def recency(t):
            s = last_by_thing.get(f"{t.get('area')}/{Path(t.rel).parts[-2]}")
            return str(s.get("updated")) if s else str(t.get("updated"))
        for t in sorted(things, key=recency, reverse=True)[:8]:
            lines.append(f"- **{t.get('title')}** ({t.get('area')}, last {recency(t)}): {t.get('summary')}")
        lines.append("")
    for typ, label, n in (("decision", "Latest decisions", 5), ("lesson", "Lessons to remember", 3)):
        group = sorted((p for p in pages if p.get("type") == typ and p.get("status") == "active"),
                       key=lambda p: str(p.get("updated")), reverse=True)[:n]
        if group:
            lines += [f"## {label}", ""] + [f"- {p.get('title')} - {p.get('summary')}" for p in group] + [""]
    soon = (now + dt.timedelta(days=7)).isoformat()
    todos = [i for i in items if i["todo"]]
    items = [i for i in items if not i["todo"]]
    if todos:
        lines += [f"## To-dos ({len(todos)} open)", ""]
        due_todos = sorted((i for i in todos if i["due"] and i["due"] <= soon), key=lambda i: i["due"])
        for i in due_todos[:6]:
            flag = "OVERDUE: " if i["due"] < now.isoformat() else ""
            lines.append(f"- {i['due']} - {flag}{i['text']}")
        if not due_todos:
            lines.append("- Nothing due in the next 7 days. Say 'what is on my list' for all of them.")
        lines.append("")
    urgent = [i for i in items if i["due"] and i["due"] <= soon]
    if urgent or items:
        lines += [f"## Follow-ups ({len(items)} open)", ""]
        for i in sorted(urgent, key=lambda i: i["due"])[:6]:
            flag = " - OVERDUE" if i["due"] < now.isoformat() else ""
            who = "I owe" if i["owner"] == "mine" else "owed by"
            lines.append(f"- {i['due']}{flag}: {who} @{i['person']} - {i['text']}")
        if not urgent:
            lines.append("- Nothing due in the next 7 days. Say 'what did I promise whom' for the full list.")
        lines.append("")
    overdue = sum(1 for i in todos + items if i["due"] and i["due"] < now.isoformat())
    if overdue:
        lines += [f"{overdue} overdue - say 'show my board' to open them.", ""]
    inbox = list((vault / "inbox").glob("*.md")) if (vault / "inbox").exists() else []
    if inbox:
        lines += [f"Sorting desk: {len(inbox)} imported note(s) waiting. Say 'open the sorting desk'.", ""]
    loose = loose_notes(vault)
    if loose:
        lines += [f"Loose notes: {len(loose)} with no header. Say 'open the sorting desk'.", ""]
    lb = last_backup(vault)
    if lb:
        age = (now - dt.date.fromisoformat(lb)).days
        lines.append(f"Last backup: {lb}{' - more than a week ago' if age > 7 else ''}.")
    else:
        lines.append("Last backup: none yet.")
    if not pages or (not things and not sessions):
        lines += ["", "This cortex is new. Work as usual, then say 'log this' at the end - the next session starts from here."]
    return "\n".join(lines) + "\n"


def parse_kit(vault: Path) -> dict:
    out = {}
    try:
        for line in (vault / "kit.yaml").read_text().splitlines():
            if ": " in line and not line.startswith((" ", "#", "-")):
                k, _, v = line.partition(":")
                out[k.strip()] = parse_value(v)
    except OSError:
        pass
    return out


def render_home(pages: list[Page], vault: Path) -> str:
    lines = ["# Home", "", "The map of this cortex. Generated after every log - do not edit by hand.", ""]
    areas = sorted((p for p in pages if p.get("type") == "area"), key=lambda p: p.get("area"))
    for a in areas:
        lines += [f"## {a.get('title')}", "", str(a.get("summary")), ""]
        for t in sorted((p for p in pages if p.get("type") == "thing" and p.get("area") == a.get("area")),
                        key=lambda p: p.rel):
            coll = Path(t.rel).parts[1]
            lines.append(f"- [{t.get('title')}]({t.rel}) - {coll} - {t.get('status')}")
        lines.append("")
    n_people = sum(1 for p in pages if p.get("type") == "person")
    n_orgs = sum(1 for p in pages if p.get("type") == "organisation")
    lines += [f"People: {n_people} - see people/. Organisations: {n_orgs} - see organisations/.", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- commands

def load_all(vault: Path):
    pages = [p for p in iter_pages(vault) if not getattr(p, "loose", False)]
    people = {p.path.stem for p in pages if p.rel.startswith("people/")}
    return pages, people


def loose_notes(vault: Path) -> list[str]:
    """Header-less notes outside inbox/ (inbox notes are already on the sorting desk)."""
    return [p.rel for p in iter_pages(vault) if getattr(p, "loose", False) and not p.rel.startswith("inbox/")]


def loose_task_count(vault: Path, rel: str) -> int:
    """Open task lines in a loose note - not counted anywhere until the note has a header."""
    try:
        text = (vault / rel).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    return sum(1 for l in text.splitlines() if re.match(r"^\s*-\s\[ \]\s+@", l))


def build_outputs(vault: Path):
    """Validate, then write the generated files. Shared by 'build' and the board's write path.
    Returns (pages, items, errors, warnings); nothing is written when there are errors."""
    pages, people = load_all(vault)
    errors, warnings = validate(pages, vault, people)
    for rel in loose_notes(vault):
        tasks = loose_task_count(vault, rel)
        extra = f"; {tasks} task line(s) not counted until it has a header" if tasks else ""
        warnings.append(f"{rel}: loose note (no header) - left for the sorting desk{extra}")
    if errors:
        return pages, [], errors, warnings
    items = followups(pages, self_slugs(vault))
    gen = vault / GENERATED
    write_atomic(gen / "index.md", render_index(pages))
    write_atomic(gen / "followups.md", render_followups(items))
    write_atomic(gen / "card.md", render_card(pages, items, vault))
    write_atomic(vault / "home.md", render_home(pages, vault))
    return pages, items, errors, warnings


def cmd_build(args) -> int:
    vault = vault_path(args.vault)
    pages, items, errors, warnings = build_outputs(vault)
    for w in warnings:
        print(f"note: {w}")
    if errors:
        print(f"\nBuild stopped - {len(errors)} problem(s) to fix first:")
        for e in errors:
            print(f"  - {e}")
        return 1
    todos = sum(1 for i in items if i["todo"])
    print(f"Build OK - {len(pages)} page(s), {len(items) - todos} open follow-up(s), {todos} to-do(s), {len(warnings)} note(s).")
    return 0


def cmd_check(args) -> int:
    vault = vault_path(args.vault)
    pages, people = load_all(vault)
    wanted = {Path(f).expanduser().resolve() for f in args.files}
    errors, warnings = validate(pages, vault, people)
    rels = {p.relative_to(vault).as_posix() for p in wanted if str(p).startswith(str(vault))}
    mine_err = [e for e in errors if e.split(":", 1)[0] in rels]
    mine_err += [f"{rel}: no header - give it one with 'cortex.py new', or leave it for the sorting desk"
                 for rel in loose_notes(vault) if rel in rels]
    mine_warn = [w for w in warnings if w.split(":", 1)[0] in rels]
    for w in mine_warn:
        print(f"note: {w}")
    for e in mine_err:
        print(f"problem: {e}")
    print("OK" if not mine_err else f"{len(mine_err)} problem(s)")
    return 1 if mine_err else 0


def cmd_card(args) -> int:
    vault = vault_path(args.vault)
    card = vault / GENERATED / "card.md"
    if card.exists():
        print(card.read_text())
        return 0
    pages, _ = load_all(vault)
    print(render_card(pages, followups(pages, self_slugs(vault)), vault))
    return 0


def cmd_new(args) -> int:
    vault = vault_path(args.vault)
    t, area, thing, coll = args.type, args.area, args.thing, args.collection
    if t not in ALL_TYPES:
        sys.exit(f"type must be one of: {', '.join(sorted(ALL_TYPES))}")
    slug = args.slug or slugify(args.title)
    d = args.date or today()
    if t in ("session", "meeting") and not slug.startswith(d):
        slug = f"{d}-{slug}"
    if t in THING_TYPES and thing:
        matches = list(vault.glob(f"{area}/*/{thing}/_index.md"))
        if not matches and not coll:
            sys.exit(f"No thing '{thing}' in area '{area}'. Create it first: new thing --area {area} --collection <name> --title ...")
        base = matches[0].parent if matches else vault / area / coll / thing
        path = base / TYPE_FOLDER[t] / f"{slug}.md"
        pid = f"{t}-{area}-{thing}-{slug}"
    elif t == "thing":
        if not coll:
            sys.exit("a thing needs --collection (e.g. projects)")
        path = vault / area / coll / slug / "_index.md"
        pid = f"thing-{area}-{slug}"
    elif t == "area":
        path, pid = vault / area / "_index.md", f"area-{area}"
    elif t == "person":
        path, pid, area = vault / "people" / f"{slug}.md", f"person-{slug}", ""
    elif t == "organisation":
        path, pid, area = vault / "organisations" / f"{slug}.md", f"organisation-{slug}", ""
    elif t == "meeting":
        path, pid = vault / area / "meetings" / f"{slug}.md", f"meeting-{area}-{slug}"
    elif t == "note":
        path = (vault / area / f"{slug}.md") if area else (vault / "inbox" / f"{slug}.md")
        pid = f"note-{area}-{slug}" if area else f"note-inbox-{slug}"
    else:  # a session/decision/lesson/insight/how-to that belongs to an area, not a thing
        if not area:
            sys.exit(f"a {t} needs --area (and usually --thing)")
        path = vault / area / TYPE_FOLDER[t] / f"{slug}.md"
        pid = f"{t}-{area}-{slug}"
    fm = [f"id: {pid}", f"title: {args.title}", f"type: {t}"]
    if area:
        fm.append(f"area: {area}")
    if t in THING_TYPES and thing:
        fm.append(f"thing: {thing}")
    fm += ["status: active", f"created: {today()}", f"updated: {today()}"]
    if t == "meeting":
        fm += [f"date: {d}", "people: []"]
    fm += ["tags: []", "links: []", "summary: "]
    tpl = Path(__file__).resolve().parent.parent / "templates" / "pages" / f"{t}.md"
    body = tpl.read_text() if tpl.exists() else f"# {args.title}\n"
    body = body.replace("{{title}}", args.title)
    rel = path.relative_to(vault).as_posix()
    if args.json:
        print(json.dumps({"path": str(path), "rel": rel, "id": pid, "exists": path.exists(),
                          "content": "---\n" + "\n".join(fm) + "\n---\n\n" + body}))
    else:
        print(f"path: {path}\nid: {pid}\nexists: {path.exists()}\n\n---\n" + "\n".join(fm) + "\n---\n\n" + body)
    return 0


def git(vault: Path, *a, check=False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(vault), *a], capture_output=True, text=True, check=check, timeout=120)


def log_backup(vault: Path, msg: str) -> None:
    p = vault / GENERATED / "backup.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M')} {msg}\n")


def cmd_backup(args) -> int:
    vault = vault_path(args.vault)
    if args.if_older_than_days is not None:
        lb = last_backup(vault)
        if lb and (dt.date.today() - dt.date.fromisoformat(lb)).days < args.if_older_than_days:
            if not args.quiet:
                print(f"Backup not needed - last one {lb}.")
            return 0
    if not (vault / ".git").exists():
        print("This cortex folder is not a git repository yet - run setup or 'cortex doctor'.")
        return 1
    git(vault, "add", "-A")
    status = git(vault, "status", "--porcelain").stdout.strip()
    committed = False
    if status:
        r = git(vault, "commit", "-q", "-m", f"cortex backup {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        committed = r.returncode == 0
    has_remote = bool(git(vault, "remote").stdout.strip())
    if not has_remote:
        msg = "committed locally (no GitHub remote yet)" if committed else "nothing to back up (no GitHub remote yet)"
        log_backup(vault, msg)
        print(f"Backup: {msg}.")
        return 0
    ahead = git(vault, "rev-list", "--count", "@{u}..HEAD")
    if ahead.returncode != 0:
        branch = git(vault, "branch", "--show-current").stdout.strip() or "main"
        push = git(vault, "push", "-q", "-u", "origin", branch)
    elif ahead.stdout.strip() == "0" and not committed:
        log_backup(vault, "nothing to back up")
        if not args.quiet:
            print("Backup: already up to date on GitHub.")
        return 0
    else:
        push = git(vault, "push", "-q")
    if push.returncode != 0:
        log_backup(vault, f"push FAILED: {push.stderr.strip()[:200]}")
        print("Backup: saved on this Mac, but the push to GitHub failed:\n  " + push.stderr.strip()[:400])
        return 1
    log_backup(vault, "pushed")
    if not args.quiet:
        print("Backup: saved and pushed to GitHub.")
    return 0


def cmd_history(args) -> int:
    vault = vault_path(args.vault)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)
    projects = HOME / ".claude" / "projects"
    rows = []
    for f in projects.glob("*/*.jsonl") if projects.exists() else []:
        try:
            if dt.datetime.fromtimestamp(f.stat().st_mtime, dt.timezone.utc) < since:
                continue
            for line in f.open(encoding="utf-8", errors="ignore"):
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("type") != "user" or e.get("isMeta") or e.get("isSidechain"):
                    continue
                cwd = e.get("cwd", "")
                sid = e.get("sessionId", "")
                # Sessions inside the cortex folder, or anywhere Cortex was active (its hooks keep a folder per session).
                if not (cwd.startswith(str(vault)) or (sid and (HOME / ".cortex" / "sessions" / sid).is_dir())):
                    continue
                c = (e.get("message") or {}).get("content")
                if isinstance(c, list):
                    c = " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
                if not isinstance(c, str) or not c.strip() or c.startswith(("<", "[Request interrupted")):
                    continue
                ts = e.get("timestamp", "")
                try:
                    when = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if when < since:
                    continue
                rows.append((when.astimezone().strftime("%Y-%m-%d %H:%M"), e.get("sessionId", "")[:8],
                             " ".join(c.split())[:300]))
        except OSError:
            continue
    rows.sort()
    print(f"# Typed requests in sessions where Cortex was active, last {args.days} days ({len(rows)})\n")
    for when, sid, text in rows:
        print(f"- {when} [{sid}] {text}")
    pages, _ = load_all(vault)
    cutoff = (dt.date.today() - dt.timedelta(days=args.days)).isoformat()
    sess = sorted((p for p in pages if p.get("type") == "session" and str(p.get("created")) >= cutoff),
                  key=lambda p: str(p.get("created")))
    print(f"\n# Session pages, last {args.days} days ({len(sess)})\n")
    for p in sess:
        print(f"- {p.get('created')} {p.get('id')}: {p.get('summary')}")
    return 0


def cmd_sort_desk(args) -> int:
    vault = vault_path(args.vault)
    desk = vault / GENERATED / "sorting-desk.md"
    inbox = sorted((vault / "inbox").glob("*.md")) if (vault / "inbox").exists() else []
    print(desk.read_text() if desk.exists() else "The sorting desk is empty.")
    print(f"\n{len(inbox)} note(s) in inbox/.")
    loose = loose_notes(vault)
    if loose:
        print(f"\n{len(loose)} loose note(s) with no header - give each a header and a home, or archive it:")
        for rel in loose:
            print(f"  - {rel}")
    return 0


PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.cortex.backup</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>{script}</string>
    <string>backup</string><string>--quiet</string><string>--vault</string><string>{vault}</string>
  </array>
  <key>StartCalendarInterval</key><dict><key>Weekday</key><integer>0</integer>
    <key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>{home}/.cortex/backup-agent.log</string>
  <key>StandardErrorPath</key><string>{home}/.cortex/backup-agent.log</string>
</dict></plist>
"""


def cmd_install_backup(args) -> int:
    vault = vault_path(args.vault)
    # The plugin cache path changes on every update, so the agent runs a stable copy.
    stable = HOME / ".cortex" / "bin" / "cortex.py"
    stable.parent.mkdir(parents=True, exist_ok=True)
    stable.write_text(Path(__file__).read_text())
    plist = HOME / "Library" / "LaunchAgents" / "com.cortex.backup.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(PLIST.format(script=stable, vault=vault, home=HOME))
    if os.environ.get("CORTEX_NO_LAUNCHD"):
        print("Weekly backup file written (test mode: not switched on).")
        return 0
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(plist)], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Weekly backup file written but could not be switched on: {r.stderr.strip()}")
        return 1
    print("Weekly backup is on: every Sunday at 18:00 your cortex is saved and pushed to GitHub.")
    return 0


def cmd_doctor(args) -> int:
    ok = True
    def line(good: bool, text: str, fix: str = ""):
        nonlocal ok
        ok &= good
        print(f"{'OK ' if good else 'FIX'} {text}{'' if good or not fix else ' - ' + fix}")
    clt = subprocess.run(["xcode-select", "-p"], capture_output=True).returncode == 0
    line(clt, "Apple Command Line Tools (git, python3)", "run: xcode-select --install")
    cfg = load_config()
    line(bool(cfg.get("vault")), f"setup done ({CONFIG})", "say 'set up my cortex'")
    if not cfg.get("vault"):
        return 1
    vault = Path(cfg["vault"]).expanduser()
    line(vault.exists(), f"cortex folder {vault}")
    cloud = any(s in str(vault) for s in ("Mobile Documents", "iCloud", "OneDrive", "Dropbox", "Google Drive"))
    line(not cloud, "cortex folder is outside iCloud/OneDrive/Dropbox", "move it - sync folders damage git")
    line((vault / ".git").exists(), "git repository", "run setup again")
    remote = git(vault, "remote", "get-url", "origin").stdout.strip() if (vault / ".git").exists() else ""
    line(bool(remote), f"GitHub backup remote {remote or ''}".strip(), "add your private GitHub repo")
    agent = HOME / "Library" / "LaunchAgents" / "com.cortex.backup.plist"
    line(agent.exists(), "weekly backup switched on", "run: cortex.py install-backup")
    lb = last_backup(vault)
    line(bool(lb) and (dt.date.today() - dt.date.fromisoformat(lb)).days <= 8,
         f"last backup {lb or 'never'}", "say 'back up my cortex'")
    pages, people = load_all(vault)
    errors, _ = validate(pages, vault, people)
    line(not errors, f"{len(pages)} pages, {len(errors)} problem(s)", "say 'log this' or run build to see them")
    return 0 if ok else 1


FEEDBACK_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSev73gOwoi9xKCcABXqMJlzQ2sLBw7k2oEbMHAHyS7-RSr3Ig/formResponse"
FEEDBACK_FIELDS = {"name": "entry.1113413954", "email": "entry.173656857", "org": "entry.703318526",
                   "version": "entry.592227497", "type": "entry.1881441667", "message": "entry.891232302",
                   "contact": "entry.885549406"}
FEEDBACK_TYPES = {"idea": "Idea or feature request", "problem": "Something is broken", "question": "Question"}


def cmd_feedback(args) -> int:
    import urllib.parse
    import urllib.request
    kit = {}
    try:
        kit = parse_kit(vault_path(args.vault))
    except SystemExit:
        pass
    data = {
        "name": args.name or kit.get("feedback_name", ""),
        "email": args.email or kit.get("feedback_email", ""),
        "org": args.org or kit.get("feedback_org", ""),
        "version": kit.get("kit_version", "") or load_config().get("kit_version", ""),
        "type": FEEDBACK_TYPES[args.type],
        "message": args.message,
        "contact": "Yes" if args.contact == "yes" else "No",
    }
    missing = [k for k in ("name", "email", "message") if not data[k]]
    if missing:
        print("Missing: " + ", ".join(missing) + ". Ask the person, then run again.")
        return 2
    print("Will send to the Cortex feedback form:")
    for k, v in data.items():
        print(f"  {k}: {v}")
    if args.dry_run:
        return 0
    body = urllib.parse.urlencode({FEEDBACK_FIELDS[k]: v for k, v in data.items()}).encode()
    req = urllib.request.Request(FEEDBACK_FORM, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            ok = r.status == 200
    except Exception as e:  # offline, blocked by a company network, form changed
        print(f"Could not reach the feedback form ({e}). Use the email fallback: info@thehimanshushukla.com")
        return 1
    print("Sent. Thank you - it goes straight to the maker." if ok else "The form did not accept it; use the email fallback.")
    return 0 if ok else 1


def cmd_board(args) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import board
    return board.run(args)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cortex")
    ap.add_argument("--vault")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    c = sub.add_parser("check"); c.add_argument("files", nargs="+")
    sub.add_parser("card")
    n = sub.add_parser("new")
    n.add_argument("type"); n.add_argument("--area", default=""); n.add_argument("--thing", default="")
    n.add_argument("--collection", default=""); n.add_argument("--title", required=True)
    n.add_argument("--slug"); n.add_argument("--date"); n.add_argument("--json", action="store_true")
    b = sub.add_parser("backup"); b.add_argument("--if-older-than-days", type=int); b.add_argument("--quiet", action="store_true")
    h = sub.add_parser("history"); h.add_argument("--days", type=int, default=30)
    sub.add_parser("sort-desk"); sub.add_parser("doctor"); sub.add_parser("install-backup")
    f = sub.add_parser("feedback")
    f.add_argument("--type", choices=sorted(FEEDBACK_TYPES), required=True); f.add_argument("--message", required=True)
    f.add_argument("--name"); f.add_argument("--email"); f.add_argument("--org")
    f.add_argument("--contact", choices=["yes", "no"], default="yes"); f.add_argument("--dry-run", action="store_true")
    bd = sub.add_parser("board"); bd.add_argument("--open", action="store_true")
    bd.add_argument("--port", type=int, default=0); bd.add_argument("--no-browser", action="store_true")
    # --vault is accepted after the subcommand too (the LaunchAgent passes it that way)
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--vault" in argv[1:]:
        i = argv.index("--vault")
        argv = argv[i:i + 2] + argv[:i] + argv[i + 2:]
    args = ap.parse_args(argv)
    fn = {"build": cmd_build, "check": cmd_check, "card": cmd_card, "new": cmd_new, "backup": cmd_backup,
          "history": cmd_history, "sort-desk": cmd_sort_desk, "doctor": cmd_doctor,
          "install-backup": cmd_install_backup, "feedback": cmd_feedback, "board": cmd_board}[args.cmd]
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
