#!/usr/bin/env python3
"""cortex board - the person's to-dos, follow-ups and inbox as a page in the browser.

Standard library only. A small server on 127.0.0.1 serves one page (board.html next to this file).
The markdown lines stay the record: a move on the board edits exactly one task line, behind a
line-identity check, and then runs the same generation as 'cortex build'.

Security: loopback only, a secret token in the launch link (kept as an HttpOnly cookie), Host
checked on every request, Origin checked on every POST, no CORS headers, ids instead of paths,
and nothing outside the vault is ever read for the page or written.
"""
from __future__ import annotations

import datetime as dt
import errno
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cortex as C  # noqa: E402

PAGE = Path(__file__).resolve().parent / "board.html"
IDLE_SECONDS = 30 * 60
PROMPT_LIMIT = 9000          # characters of the decoded prompt
URL_LIMIT = 14000            # characters of the whole encoded claude:// link
TRASH_KEEP = 20
PAGE_TEXT_LIMIT = 6000
MAX_BODY = 64 * 1024
COLUMNS = [("overdue", "Overdue", False), ("week", "This week", True), ("later", "Later", True),
           ("doing", "In progress", True), ("waiting", "Waiting on others", True),
           ("done", "Done (last 7 days)", True)]
TARGETS = {key for key, _, droppable in COLUMNS if droppable}


def state_file() -> Path:
    return Path.home() / ".cortex" / "board.json"


def trash_dir(vault: Path) -> Path:
    """Undo copies live outside the vault, so the GitHub backup never carries them."""
    return Path.home() / ".cortex" / "board-trash" / hashlib.sha256(str(vault).encode()).hexdigest()[:16]


def today() -> dt.date:  # tests replace this
    return dt.date.today()


def this_friday(d: dt.date) -> dt.date:
    """This week's Friday; on Saturday and Sunday the week is over, so next Friday."""
    ahead = 4 - d.weekday()
    return d + dt.timedelta(days=ahead if ahead >= 0 else ahead + 7)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def make_id(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:32]


def split_lines(text: str) -> list[list[str]]:
    """[content, ending] per line; ending is '\\n', '\\r\\n' or '' so a join gives the exact text back."""
    out = []
    parts = text.split("\n")
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if last and part == "":
            break
        if not last and part.endswith("\r"):
            out.append([part[:-1], "\r\n"])
        else:
            out.append([part, "" if last else "\n"])
    return out


def column_of(t: dict, now: dt.date) -> str | None:
    """Precedence: done > doing > theirs > overdue > this week > later."""
    if t["closed"]:
        return "done" if t["done"] and t["done"] >= (now - dt.timedelta(days=7)).isoformat() else None
    if t["doing"]:
        return "doing"
    if t["owner"] == "theirs":
        return "waiting"
    if t["due"] and t["due"] < now.isoformat():
        return "overdue"
    if t["due"] and t["due"] <= (now + dt.timedelta(days=7)).isoformat():
        return "week"
    return "later"


class Refused(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def edit_line(line: str, target: str, me: set[str], now: dt.date) -> str:
    """The new text of one task line after a move. Only this line's box, dates and tags change."""
    m = C.FOLLOWUP_RE.match(line)
    if not m:
        raise Refused(409, "This line is no longer a task line. The page was reloaded.")
    dates = C.META_RE.findall(m.group("meta"))
    owner, doing, box = m.group("owner"), bool(m.group("doing")), m.group("done")

    def set_date(key, value):
        nonlocal dates
        if value is None:
            dates = [(k, v) for k, v in dates if k != key]
        elif any(k == key for k, _ in dates):
            dates = [(k, value if k == key else v) for k, v in dates]
        else:
            dates.append((key, value))

    if target == "done":
        if box == " ":
            box = "x"
            set_date("done", now.isoformat())
        doing = False
    else:
        if box != " ":  # out of Done: open again
            box = " "
            set_date("done", None)
        if target == "waiting":
            if m.group("person") in me:
                raise Refused(400, "Who is it waiting on? This is your own to-do (@"
                              + m.group("person") + "). Ask Claude to put the person's name on it, "
                              "then it can wait on them.")
            owner, doing = "theirs", False
        elif target == "week":   # every move but Waiting keeps the owner: "Alex owes me" stays so
            set_date("due", this_friday(now).isoformat())
            doing = False
        elif target == "later":
            due = dict(dates).get("due", "")
            if not due or due <= (now + dt.timedelta(days=7)).isoformat():
                set_date("due", None)   # a date already beyond next week is kept
            doing = False
        elif target == "doing":
            doing = True
    head = line[:m.end("text")]
    head = re.sub(r"^(\s*-\s)\[[ xX]\]", lambda x: x.group(1) + "[" + box + "]", head, count=1).rstrip()
    meta = "".join(f" ({k} {v})" for k, v in dates)
    return head + meta + " {" + owner + "}" + (" {doing}" if doing else "") + m.group("trail")


def clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n - 3] + "..."


def task_prompt(t: dict, title: str, rel: str) -> str:
    line = clip(t["raw"].strip(), 4000)
    p = (f'About this item in my cortex: "{line}" (from {clip(str(title), 300)}, {clip(rel, 500)}; '
         f'due {t["due"] or "no date"}; {t["owner"]} @{t["person"]}).\n'
         "Read that page and the person page, then tell me: where does this stand, what is the next "
         "step, and is anything missing? Do not change any file unless I say so.")
    return p[:PROMPT_LIMIT]


def inbox_prompt(rel: str, title: str) -> str:
    p = (f'Help me file this note in my cortex: {clip(rel, 500)} ("{clip(str(title), 300)}").\n'
         "Read it, then propose where it belongs (area, thing, page type, tags, links) and wait for my "
         "yes before moving or changing anything.")
    return p[:PROMPT_LIMIT]


def claude_link(prompt: str, vault: Path) -> str:
    """The prompt is clipped in characters before encoding (so a %-escape is never cut in half)
    until the whole encoded link fits Claude's limit."""
    def link(n):
        return ("claude://code/new?q=" + urllib.parse.quote(prompt[:n], safe="")
                + "&folder=" + urllib.parse.quote(str(vault), safe=""))
    lo, hi = 0, min(len(prompt), PROMPT_LIMIT)
    if len(link(hi)) <= URL_LIMIT:
        return link(hi)
    while lo < hi:  # the longest prefix that fits
        mid = (lo + hi + 1) // 2
        lo, hi = (mid, hi) if len(link(mid)) <= URL_LIMIT else (lo, mid - 1)
    return link(lo)


def default_opener(target: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(["open", target], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    return r.returncode == 0, (r.stderr or "").strip()


# ---------------------------------------------------------------- the board (no HTTP here)

class Board:
    def __init__(self, vault: Path, opener=default_opener):
        self.vault = Path(vault).expanduser().resolve()
        self.opener = opener
        self.lock = threading.Lock()
        self.ids: dict[str, tuple] = {}   # id -> ("task", rel, line, occurrence) or ("inbox", rel, prompt)
        self.last: dict | None = None      # the last write, for Undo

    def me(self) -> set[str]:
        return C.self_slugs(self.vault)

    def inside(self, rel: str) -> Path | None:
        """The real path of a vault file, or None when it resolves outside the vault (a symlink out)."""
        try:
            real = (self.vault / rel).resolve()
            real.relative_to(self.vault)
        except (ValueError, OSError, RuntimeError):
            return None
        return real

    # ---- reading

    def state(self) -> dict:
        now = today()
        out = {"ok": True, "today": now.isoformat(), "vault": self.vault.name,
               "columns": [{"key": k, "title": t, "droppable": d} for k, t, d in COLUMNS],
               "items": [], "problems": [], "inbox": None}
        if not self.vault.is_dir():
            out["ok"] = False
            out["problems"].append(f"could not read your cortex folder {self.vault} - it is not there.")
            return out
        try:
            pages, _ = C.load_all(self.vault)
            me = self.me()
        except Exception as e:  # never an empty board without a reason
            out["ok"] = False
            out["problems"].append(f"could not read your cortex folder ({e}).")
            return out
        for p in pages:
            if p.errors and not p.meta:
                out["problems"].append(f"could not read {p.rel} - {p.errors[0]}. Its tasks are not on the board.")
                continue
            real = self.inside(p.rel)
            if real is None:
                out["problems"].append(f"could not read {p.rel} - it points outside your cortex folder.")
                continue
            try:
                raw = real.read_bytes()
                text = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError) as e:
                out["problems"].append(f"could not read {p.rel} ({e}).")
                continue
            digest, seen = sha(raw), {}
            for idx, line in self.task_lines(p.rel, text):
                n = idx + 1
                t = C.parse_task(line, me)
                if not t:
                    continue
                occ = seen.get(line, 0)
                seen[line] = occ + 1
                col = column_of(t, now)
                if col is None:
                    continue
                iid = make_id("task", p.rel, line, str(occ))
                self.ids[iid] = ("task", p.rel, line, occ)
                late = (now - dt.date.fromisoformat(t["due"])).days if col == "overdue" else 0
                out["items"].append({
                    "id": iid, "sha": digest, "column": col, "text": t["text"], "person": t["person"],
                    "owner": t["owner"], "todo": t["todo"], "mine": t["person"] in me, "due": t["due"],
                    "added": t["added"], "done": t["done"], "doing": t["doing"], "days_late": late,
                    "page_title": str(p.get("title") or p.rel), "page": p.rel, "area": str(p.get("area") or ""),
                    "line_no": n, "line": line.strip(), "prompt": task_prompt(t, p.get("title"), p.rel)})
        out["items"].sort(key=lambda i: (i["due"] or "9999", i["person"], i["text"]))
        out["inbox"] = self.inbox(out["problems"])
        return out

    def task_lines(self, rel: str, text: str):
        """(index, line) of the lines that can be tasks: the body, outside code fences - as the build sees it."""
        page = C.read_page(self.vault / rel, self.vault, text)
        lines = [c for c, _ in split_lines(text)]
        return list(C.task_lines(lines, getattr(page, "body_line", 1) - 1)) if page.meta else []

    def _inbox_row(self, kind: str, rel: str, title: str, **extra) -> dict:
        iid = make_id("inbox", kind, rel)
        self.ids[iid] = ("inbox", rel, inbox_prompt(rel, title))
        return dict(id=iid, rel=rel, title=title, prompt=inbox_prompt(rel, title), **extra)

    def inbox(self, problems: list[str]) -> dict:
        v = self.vault
        out = {"desk": [], "notes": [], "loose": [], "unsaved": [], "git": (v / ".git").exists()}
        desk = v / C.GENERATED / "sorting-desk.md"
        if desk.exists():
            try:
                for line in desk.read_text(encoding="utf-8").splitlines():
                    cells = [c.strip() for c in line.strip().strip("|").split("|")]
                    if line.lstrip().startswith("|") and cells and cells[0].isdigit() and len(cells) >= 6:
                        rel = cells[1].strip("`")
                        out["desk"].append(self._inbox_row(
                            "desk", rel, cells[2], n=cells[0],
                            where=" / ".join(c for c in cells[3:5] if c and c != "-"), type=cells[5],
                            why=cells[-1] if len(cells) >= 10 else ""))
            except (OSError, UnicodeDecodeError) as e:
                problems.append(f"could not read _cortex/sorting-desk.md ({e}).")
        inbox = v / "inbox"
        for f in sorted(inbox.glob("*.md")) if inbox.is_dir() else []:
            if self.inside(f.relative_to(v).as_posix()) is None:
                continue
            p = C.read_page(f, v)
            out["notes"].append(self._inbox_row("note", p.rel, str(p.get("title") or f.stem)))
        for rel in C.loose_notes(v):
            out["loose"].append(self._inbox_row("loose", rel, Path(rel).stem, tasks=C.loose_task_count(v, rel)))
        if out["git"]:
            try:
                r = subprocess.run(["git", "-C", str(v), "-c", "core.quotepath=off", "status", "--porcelain", "-z",
                                    "--untracked-files=all"], capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    raise OSError(r.stderr.strip()[:200])
                entries = r.stdout.split("\0")
                k = 0
                while k < len(entries):
                    entry = entries[k]
                    k += 1
                    if len(entry) < 4:
                        continue
                    code, rel = entry[:2], entry[3:]
                    if "R" in code or "C" in code:
                        k += 1  # -z puts the old name of a rename or copy in the next field
                    if rel.endswith(".md") and not rel.startswith(C.GENERATED + "/") and rel != "home.md":
                        what = "deleted" if "D" in code else "new" if "?" in code or "A" in code else "changed"
                        out["unsaved"].append(self._inbox_row("unsaved", rel, Path(rel).stem, status=what))
            except (OSError, subprocess.SubprocessError) as e:
                problems.append(f"could not read which pages are not saved yet ({e}).")
        return out

    def item(self, iid: str) -> dict:
        ref = self.ids.get(iid)
        if not ref:
            raise Refused(404, "That item is not on the board any more. The page was reloaded.")
        rel = ref[1]
        real = self.inside(rel)
        out = {"page": rel, "line": ref[2].strip() if ref[0] == "task" else "", "page_text": "",
               "person_page": "", "person_text": ""}
        if real is None:
            raise Refused(403, f"could not read {rel} - it points outside your cortex folder.")
        try:
            out["page_text"] = clip(real.read_text(encoding="utf-8"), PAGE_TEXT_LIMIT)
        except (OSError, UnicodeDecodeError) as e:
            out["page_text"] = f"could not read {rel} ({e})."
        if ref[0] == "task":
            t = C.parse_task(ref[2], self.me())
            person = f"people/{t['person']}.md" if t else ""
            preal = self.inside(person) if person else None
            if preal and preal.is_file():
                out["person_page"] = person
                try:
                    out["person_text"] = clip(preal.read_text(encoding="utf-8"), 2000)
                except (OSError, UnicodeDecodeError):
                    out["person_text"] = f"could not read {person}."
        return out

    # ---- writing

    def _page_errors(self, rel: str) -> list[str]:
        pages, people = C.load_all(self.vault)
        errors, _ = C.validate(pages, self.vault, people)
        return [e for e in errors if e.startswith(rel + ":")]

    def _rebuild(self) -> str:
        """The page is already saved here, so a failed rebuild is a note, never an error."""
        try:
            _, _, errors, _ = C.build_outputs(self.vault)
        except Exception:
            return "Saved, the card will catch up at the next build."
        return "" if not errors else (f"Saved. The card was not rebuilt: {len(errors)} problem(s) elsewhere "
                                      "in your cortex. Say 'build my cortex' in Claude to see them.")

    def _keep_copy(self, real: Path, original: bytes) -> None:
        d = trash_dir(self.vault)
        C.write_atomic(d / f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{real.name}", original)
        for old in sorted(d.iterdir())[:-TRASH_KEEP]:
            try:
                old.unlink()
            except OSError:
                pass

    @staticmethod
    def _replace_if_unchanged(real: Path, expected: str, data: bytes | str, rel: str) -> None:
        """Re-read right before replacing; if anyone else wrote meanwhile, write nothing."""
        try:
            now = real.read_bytes()
        except OSError as e:
            raise Refused(409, f"could not read {rel} ({e}). Nothing was changed.")
        if sha(now) != expected:
            raise Refused(409, "This page changed - reloaded. Nothing was changed; try again.")
        C.write_atomic(real, data)

    @staticmethod
    def _writable(real: Path, rel: str) -> None:
        if not os.access(real, os.W_OK):
            raise Refused(403, f"{rel} is read-only, so the board will not change it.")

    def move(self, iid: str, seen_sha: str, target: str) -> dict:
        ref = self.ids.get(iid)
        if not ref or ref[0] != "task":
            raise Refused(404, "That item is not on the board any more. The page was reloaded.")
        if target == "overdue":
            raise Refused(400, "Overdue comes from the date. Move it to This week or Later to change the date.")
        if target not in TARGETS:
            raise Refused(400, "That is not a column on the board.")
        _, rel, line, occ = ref
        with self.lock:
            real = self.inside(rel)
            if real is None:
                raise Refused(403, f"{rel} points outside your cortex folder, so the board will not change it.")
            try:
                raw = real.read_bytes()
                text = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError) as e:
                raise Refused(409, f"could not read {rel} ({e}). The page was reloaded.")
            lines = split_lines(text)
            hits = [i for i, c in self.task_lines(rel, text) if c == line]
            if sha(raw) == seen_sha and occ < len(hits):
                i = hits[occ]
            elif len(hits) == 1:
                i = hits[0]
            else:
                raise Refused(409, "This page changed - reloaded. Try the move again.")
            me, now = self.me(), today()
            new = edit_line(line, target, me, now)
            if new == line:
                return {"ok": True, "message": "Nothing to change.", "note": True}
            lines[i][0] = new
            out = self._write(rel, real, raw, "".join(c + e for c, e in lines))
            occ_new = sum(1 for k, c in self.task_lines(rel, "".join(c + e for c, e in lines)) if c == new and k < i)
            out["id"] = make_id("task", rel, new, str(occ_new))
            t = C.parse_task(new, me)
            landed = column_of(t, now)
            if landed != target and not out["note"]:
                names = {k: title for k, title, _ in COLUMNS}
                why = (f" because @{t['person']} owes it" if landed == "waiting" else
                       " because its date has passed" if landed == "overdue" else "")
                out.update(note=True, message=f"Saved. It shows under {names.get(landed, landed)}{why}.")
            return out

    def _write(self, rel: str, real: Path, original: bytes, text: str) -> dict:
        self._writable(real, rel)
        before = self._page_errors(rel)
        written = sha(text.encode("utf-8"))
        self._keep_copy(real, original)
        self._replace_if_unchanged(real, sha(original), text, rel)
        new_errors = [e for e in self._page_errors(rel) if e not in before]
        if new_errors:
            try:
                self._replace_if_unchanged(real, written, original, rel)
            except Refused:
                raise Refused(409, "The page was changed by something else while the board was checking it, "
                              "so the board left it alone. Open the page to check it.")
            raise Refused(422, "That change was not saved, because the page would no longer check out: "
                          + new_errors[0].split(": ", 1)[-1])
        self.last = {"rel": rel, "real": real, "original": original, "written": written}
        note = self._rebuild()
        return {"ok": True, "message": note or "Saved.", "note": bool(note), "undo": True}

    def undo(self) -> dict:
        with self.lock:
            last = self.last
            if not last:
                raise Refused(400, "Nothing to undo.")
            try:
                current = last["real"].read_bytes()
            except OSError as e:
                raise Refused(409, f"could not read {last['rel']} ({e}).")
            if sha(current) != last["written"]:
                raise Refused(409, "The page changed after that move, so undo would lose newer edits. Nothing was changed.")
            self._writable(last["real"], last["rel"])
            self._replace_if_unchanged(last["real"], last["written"], last["original"], last["rel"])
            self.last = None
            note = self._rebuild()
            return {"ok": True, "message": note or f"Undone. {last['rel']} is back as it was.", "note": bool(note)}

    # ---- opening things on this Mac

    def open(self, iid: str, how: str) -> dict:
        ref = self.ids.get(iid)
        if not ref:
            raise Refused(404, "That item is not on the board any more. The page was reloaded.")
        rel = ref[1]
        if how == "claude":
            prompt = task_prompt(C.parse_task(ref[2], self.me()), self._title(rel), rel) if ref[0] == "task" else ref[2]
            ok, err = self.opener(claude_link(prompt, self.vault))
            return {"ok": ok, "message": "Claude is opening with the question filled in. Check it, then press send."
                    if ok else "Could not open Claude. Is the Claude desktop app installed? Copy prompt still works."}
        real = self.inside(rel)
        if real is None:
            raise Refused(403, f"{rel} points outside your cortex folder, so the board will not open it.")
        if not real.exists():
            return {"ok": False, "message": f"{rel} is not there any more."}
        if how == "obsidian":
            ok, _ = self.opener("obsidian://open?path=" + urllib.parse.quote(str(real), safe=""))
            return {"ok": ok, "message": "Opening in Obsidian." if ok else "Could not open Obsidian. Is it installed?"}
        if how == "file":
            ok, _ = self.opener(str(real))
            return {"ok": ok, "message": "Opening the file." if ok else f"Could not open {rel}."}
        raise Refused(400, "Unknown way to open.")

    def _title(self, rel: str) -> str:
        real = self.inside(rel)
        return str(C.read_page(real, self.vault).get("title") or rel) if real else rel


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "cortex-board"
    sys_version = ""
    timeout = 10  # a slow or short body cannot hold a thread

    def log_message(self, *a):  # print nothing: the log would carry tokens and page names
        pass

    def _send(self, code: int, body: bytes, ctype: str, headers: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _token(self) -> str:
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("t", [""])[0]
        if q:
            return q
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except Exception:
            return ""
        c = jar.get(self.server.cookie)
        return c.value if c else ""

    def _allowed(self, post: bool) -> bool:
        srv = self.server
        srv.touch()
        if self.headers.get("Host", "") not in srv.hosts:
            self._json(403, {"ok": False, "message": "Wrong host."})
            return False
        if not hmac.compare_digest(self._token().encode(), srv.token.encode()):
            self._json(403, {"ok": False, "message": "This board link has expired. Say 'show my board' to open it again."})
            return False
        if post and self.headers.get("Origin", "") not in srv.origins:
            self._json(403, {"ok": False, "message": "Refused: this request did not come from the board page."})
            return False
        return True

    def do_GET(self):
        if not self._allowed(post=False):
            return
        url = urllib.parse.urlsplit(self.path)
        board: Board = self.server.board
        try:
            if url.path == "/":
                nonce = secrets.token_urlsafe(16)
                html = PAGE.read_text(encoding="utf-8").replace("<script>", f'<script nonce="{nonce}">')
                csp = (f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; "
                       "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; "
                       "frame-ancestors 'none'")
                cookie = f"{self.server.cookie}={self.server.token}; HttpOnly; SameSite=Strict; Path=/"
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8",
                           {"Content-Security-Policy": csp, "Set-Cookie": cookie})
            elif url.path == "/api/state":
                self._json(200, board.state())
            elif url.path == "/api/item":
                iid = urllib.parse.parse_qs(url.query).get("id", [""])[0]
                self._json(200, board.item(iid))
            elif url.path == "/api/ping":
                self._json(200, {"ok": True, "vault": str(board.vault)})
            else:
                self._json(404, {"ok": False, "message": "Not found."})
        except Refused as e:
            self._json(e.code, {"ok": False, "message": e.message})
        except Exception as e:
            self._json(500, {"ok": False, "message": f"could not read your cortex ({e})."})

    def do_POST(self):
        if not self._allowed(post=True):
            return
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._json(415, {"ok": False, "message": "Expected JSON."})
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            return self._json(413, {"ok": False, "message": "Request too large."})
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            return self._json(400, {"ok": False, "message": "Bad request."})
        board: Board = self.server.board
        path = urllib.parse.urlsplit(self.path).path
        try:
            if path == "/api/move":
                out = board.move(str(data.get("id", "")), str(data.get("sha", "")), str(data.get("to", "")))
            elif path == "/api/undo":
                out = board.undo()
            elif path == "/api/open":
                out = board.open(str(data.get("id", "")), str(data.get("how", "")))
            else:
                return self._json(404, {"ok": False, "message": "Not found."})
            self._json(200, out)
        except Refused as e:
            self._json(e.code, {"ok": False, "message": e.message})
        except Exception as e:
            self._json(500, {"ok": False, "message": f"Something went wrong, nothing was lost: {e}"})


class BoardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, board: Board, port: int = 0, token: str | None = None, idle: float = IDLE_SECONDS):
        super().__init__(("127.0.0.1", port), Handler)
        self.board = board
        self.port = self.server_address[1]
        self.token = token or secrets.token_urlsafe(24)
        self.cookie = f"cortex_board_{self.port}"
        self.hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        self.origins = {f"http://{h}" for h in self.hosts}
        self.idle = idle
        self.last_seen = time.monotonic()

    def touch(self):
        self.last_seen = time.monotonic()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"

    def watch_idle(self):
        def loop():
            while True:
                time.sleep(min(30.0, max(self.idle / 4, 0.05)))
                if time.monotonic() - self.last_seen > self.idle:
                    self.shutdown()
                    self.server_close()
                    return
        threading.Thread(target=loop, daemon=True).start()


def start_in_thread(board: Board, port: int = 0, token: str | None = None, idle: float = IDLE_SECONDS) -> BoardServer:
    """For tests and embedding: a running server on a background thread."""
    srv = BoardServer(board, port, token, idle)
    srv.watch_idle()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ---------------------------------------------------------------- the command

def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError as e:
        return e.errno == errno.EPERM
    return True


def open_board() -> dict | None:
    """The board recorded in ~/.cortex/board.json, if its process is alive and answers with its key
    (so a reused process number is never mistaken for it). Adds 'vault' as the board reports it."""
    try:
        info = json.loads(state_file().read_text())
        if not pid_alive(int(info["pid"])):
            return None
        req = urllib.request.Request(f"http://127.0.0.1:{int(info['port'])}/api/ping?t={info['token']}",
                                     headers={"Host": f"127.0.0.1:{int(info['port'])}"})
        with urllib.request.urlopen(req, timeout=2) as r:
            info["vault"] = json.loads(r.read()).get("vault")
            return info
    except Exception:
        return None


def running(vault: Path) -> dict | None:
    """The board already open for this vault."""
    info = open_board()
    return info if info and info["vault"] == str(vault) else None


STOP_HINT = "python3 ~/.cortex/engine/scripts/cortex.py board --stop"


def stop(vault: Path) -> int:
    info = open_board()
    if not info:
        print("No board is open.")
        return 0
    if info["vault"] != str(vault):
        print(f"The open board is for another cortex folder ({info['vault']}). Stop it with: "
              f"python3 ~/.cortex/engine/scripts/cortex.py --vault \"{info['vault']}\" board --stop")
        return 1
    os.kill(int(info["pid"]), signal.SIGTERM)
    for _ in range(50):
        if not pid_alive(int(info["pid"])):
            break
        time.sleep(0.1)
    print("Board closed.")
    return 0


def run(args) -> int:
    import fcntl
    vault = C.vault_path(args.vault)
    if not vault.is_dir():
        print(f"could not read your cortex folder {vault} - it is not there. Say 'something is broken' in Claude.")
        return 1
    if getattr(args, "stop", False):
        return stop(vault)
    show = args.open and not args.no_browser
    info = running(vault)
    if info:
        url = f"http://127.0.0.1:{info['port']}/?t={info['token']}"
        if show:
            default_opener(url)
        print(f"Your board is already open at http://127.0.0.1:{info['port']}/"
              + (" - opened it in your browser." if show else f"\n{url}"))
        return 0
    sf = state_file()
    sf.parent.mkdir(parents=True, exist_ok=True)
    lock = open(sf.with_suffix(".lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Another board is open (or still starting) for a different cortex folder. Close it with:\n  "
              + STOP_HINT + "\nthen ask again.")
        return 1
    try:
        srv = BoardServer(Board(vault), args.port or 0)
    except OSError as e:
        print(f"Could not start the board on port {args.port} ({e.strerror}). Try again without --port.")
        lock.close()
        return 1
    fd = os.open(sf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"pid": os.getpid(), "port": srv.port, "token": srv.token, "vault": str(vault)}, fh)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=srv.shutdown, daemon=True).start())
    if show:
        default_opener(srv.url)
    print(f"Board running at http://127.0.0.1:{srv.port}/"
          + (" - opened it in your browser." if show else f"\n{srv.url}")
          + "\nIt closes itself after 30 minutes without use.", flush=True)
    srv.watch_idle()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        try:
            if json.loads(sf.read_text()).get("pid") == os.getpid():
                sf.unlink()
        except (OSError, ValueError):
            pass
        lock.close()
    return 0
