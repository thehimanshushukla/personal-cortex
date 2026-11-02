#!/usr/bin/env python3
"""cortex gardener - which working sessions never reached the cortex (phase 1, no AI).

Standard library only. No model is called and nothing leaves this Mac. Reads the transcripts
Claude Code and Codex keep on disk, only to count real messages and take a short title from the
first request. It never prints or stores any other transcript text. Claude Chat conversations are
not on the Mac, so they cannot be seen here. Contract: docs/SPEC.md.

The format of these files is internal to each tool and can change without notice, so every read
expects bad data: a file it cannot understand is counted as such and never stops the run.

State lives in ~/.cortex/gardener/, outside the git-backed vault, so nothing taken from a chat can
reach GitHub: state.json (Dismiss), cache.json (one short row per transcript), summary.json (what
the start hook reads). The only thing written into the vault is the weekly journal.
"""
from __future__ import annotations

import collections
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cortex as C  # noqa: E402

OVERLAP_DAYS = 2            # the window always reaches this much further back, so an edge session is not lost
LOOKBACK_DAYS = 32          # how far back a session can still be missed (Claude Code's default is 30 days)
MAX_DAYS = LOOKBACK_DAYS - OVERLAP_DAYS   # the most --days can honestly promise
WARN_DAYS = 21              # warn when an unlogged session is this old
FRESH_SECONDS = 600         # a file changed in the last 10 minutes may be a chat still going
MIN_USER_MESSAGES = 3
CONTINUED_MESSAGES = 10     # this many typed messages after a session was logged make it worth listing again
COPY_GAP = 2                # an exact copy of a session may differ from it by this many typed messages
ELSEWHERE_DAYS = 7          # the card and the board count sessions elsewhere over the same days
ELSEWHERE_EVERY = 7 * 86400 # the card says it at most this often
TITLE_CHARS = 80
READ_CHARS = 2000           # titles are cut from this much of the first request
MENTION_CHARS = 20000
MAX_LINE = 4 * 1024 * 1024  # a longer line is skipped (usually a pasted image), never held in memory
MAX_FILE_BYTES = 256 * 1024 * 1024
FILE_SECONDS = 5.0          # no single transcript may take longer than this
CLI_SECONDS = 60.0
REFRESH_SECONDS = 120.0
MAX_DISMISSED = 5000
WEEK_IDS = 200              # ids the start hook checks; only a bound, far above any real week
SUMMARY_VAULTS = 8          # the summary keeps this many vaults, the most recently counted
METADATA_BYTES = 64 * 1024  # a metadata-only file is this small; anything bigger is reported as not understood
METADATA_LINES = 20
CACHE_VERSION = 3           # bumped when a row's meaning changes, so old rows and titles are read again
AUTOMATION_MARK = "[CORTEX_AUTOMATION]"   # how the kit's own automated prompts start
SCOPES = {"cortex", "all", "off"}
SESSION_ENVS = ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")   # set inside a running session

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
CODEX_ID_RE = re.compile(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$")
MENTION_RE = re.compile(r"\bcortex\b", re.I)
# Messages in a user slot that the person did not type: tool output, slash-command wrappers, summaries.
NOT_TYPED = ("<", "[Request interrupted", "Caveat:", "This session is being continued",
             "Base directory for this skill", "# AGENTS.md instructions")
CLAUDE_TYPES = {"user", "assistant", "summary", "system", "attachment", "progress"}
CODEX_TYPES = {"session_meta", "turn_context", "event_msg", "response_item", "compacted", "message"}
# Lines in a file with none of these and a type of their own are bookkeeping, not a format we cannot read.
TALK_KEYS = {"message", "content", "payload", "text", "role"}
CHAT_NOTE = ("A plain Claude Chat cannot be seen here, because its conversations are not on this Mac. "
             "To keep one, say 'save this chat' in that chat (it needs the Cortex extension for the Chat tab, from the kit's latest GitHub release).")


def home() -> Path:
    return Path.home()


def state_dir() -> Path:
    d = home() / ".cortex" / "gardener"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)   # titles come from private chats
    return d


def read_regular(path: Path, limit: int = -1) -> bytes:
    """A plain file's bytes. O_NONBLOCK and O_NOFOLLOW: a pipe or a link in its place cannot hang the read."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            raise OSError("not a plain file")
        return fh.read(limit)


def read_json(path: Path, default):
    try:
        out = json.loads(read_regular(path).decode("utf-8"))
        return out if isinstance(out, type(default)) else default
    except (OSError, ValueError, RecursionError):
        return default


def write_private(path: Path, text: str) -> None:
    """Only this user can read what the Gardener keeps."""
    C.write_atomic(path, text)
    os.chmod(path, 0o600)


# ---------------------------------------------------------------- titles

# Shapes that look like a secret.
_VALUE = r"""(?:"[^"]*"|'[^']*'|\S+)"""
_KEYWORD = r"password|passwd|pwd|passphrase|secret|token|auth[-_]?key|api[-_ ]?key|access[-_ ]?key|private[-_ ]?key|credentials?"
SECRET_RES = [
    re.compile(r"-----BEGIN [^-]{0,40}-----.*?(?:-----END [^-]{0,40}-----|$)", re.S),
    re.compile(r"\b(?:sk|pk|rk)[-_][A-Za-z0-9_-]{8,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"\bgithub_pat_\w{8,}"),
    re.compile(r"\bxox[abprs]-[\w-]{8,}"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{12,}"),
    re.compile(r"\bAIza[\w-]{20,}"),
    re.compile(r"\beyJ[\w-]{8,}\.[\w-]+(?:\.[\w-]+)?"),
    re.compile(r"(?i)\bbearer\s+[\w.~+/=-]{8,}"),
    # A name that holds a keyword, then a value: DB_PASSWORD=x, CLIENT_SECRET: x, "api_key": "x", my token is x.
    re.compile(r"(?i)[\w.-]{0,64}(?:" + _KEYWORD + r")[\w.-]{0,64}[\"']?\s*(?:\bis\b|=|:)\s*" + _VALUE),
    re.compile(r"(?i)(?<![A-Za-z0-9])(?:password|passwd|pwd|passphrase)\b\s*" + _VALUE),
    re.compile(r"(?i)(?<![A-Za-z0-9])pass[\"']?\s*[:=]\s*" + _VALUE),
    re.compile(r"(?i)(?<!\S)--[\w-]{0,40}(?:password|passwd|token|secret|api-?key)[\w-]{0,40}\s+\S+"),
    re.compile(r"(?<!\S)(?:-u|--user)[ =]?\S+:\S+"),
    re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"),
    re.compile(r"[\w.+-]{1,64}@[\w-]+(?:\.[\w-]+)+"),                             # an email address
    re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),                                 # a US social security number
    re.compile(r"(?i)(?<![a-z0-9])[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(?![a-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])[0-9a-fA-F]{16,}(?![A-Za-z0-9])"),                  # long hex
    re.compile(r"\b\d(?:[ -]?\d){12,18}\b"),
]
# These say a whole line of credentials follows, and it has no clear end, so nothing of the title is kept.
WHOLE_TITLE_RE = re.compile(r"""(?ix)
    (?<![a-z0-9-]) (?:set-)? cookie ["']? \s* [:=]
  | (?<![a-z0-9-]) (?:proxy-)? authorization ["']? \s* [:=]
  | (?<![a-z0-9-]) x-(?:api|auth)-[\w-]{0,40} ["']? \s* :
  | -----BEGIN \s
""")
HIDDEN_TITLE = "(title hidden)"
SHELL_RE = re.compile(r"\$\([^()]*\)|\$\{[^{}]*\}")
LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9_+=/-]{32,}")
MIXED_TOKEN_RE = re.compile(r"\b(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{20,}\b")
TAG_RE = re.compile(r"</?[A-Za-z_!?][^<>]{0,200}>")
# Any of these anywhere hides a whole title. It errs towards hiding: "pass the deck to Sam" goes too.
SECRET_WORD_RE = re.compile(r"""(?ix)
    p[a@4]ssw[o0]rd | passwd | passcode | passphrase | secret | token | credential | cookie | bearer
  | api [-_\s]? key | (?:private|access|auth|ssh|signing|encryption) [-_\s]? key
  | key \s* = | (?<![a-z]) key \s* :
  | (?<![a-z]) (?: pass | pwd? | pins? | o?auth (?: n | z | enticat\w* | ori[sz]\w* )? ) (?![a-z])
  | \bbasic \s+ [a-z0-9+/=]{8,}
  | (?<![\w-]) -p \s* \S
""")
SECRET_CAMEL_RE = re.compile(r"[a-z0-9](?:Pass|Pwd?|Pin|Auth)(?![a-z])|[A-Z]{2,}PASS(?![A-Za-z])")
BASE64_RE = re.compile(r"\b(?=[A-Za-z0-9+]*[a-z])(?=[A-Za-z0-9+]*[A-Z])[A-Za-z0-9+]{24,}|[A-Za-z0-9+/]{16,}={1,2}")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f​-‏ -‮⁠-⁯﻿]+")


def _hide_long(m: re.Match) -> str:
    """A long unbroken run with a digit in it reads as a key, slashes or not. Without a digit it stays."""
    return "[hidden]" if re.search(r"\d", m.group(0)) else m.group(0)


def _no_shell(s: str) -> str:
    """A title may end up inside a command, so nothing in it may be able to run as one."""
    for _ in range(8):      # nested $( $( ) ) comes off from the inside
        s, n = SHELL_RE.subn(" ", s)
        if not n:
            break
    return s.replace("$(", " ").replace("${", " ").replace("`", " ")


def looks_secret(text: str) -> bool:
    """A secret-related word or shape anywhere. Taken from a part of a title, a secret can always survive
    in a form no pattern knows, so the answer is for the whole title. A best effort, not a guarantee."""
    plain = unicodedata.normalize("NFKC", text)
    for s in (CONTROL_RE.sub(" ", plain), CONTROL_RE.sub("", plain)):      # an invisible character splits no word
        if SECRET_WORD_RE.search(s) or SECRET_CAMEL_RE.search(s) or BASE64_RE.search(s) or WHOLE_TITLE_RE.search(s):
            return True
        if any(rx.search(s) for rx in SECRET_RES):
            return True
        if MIXED_TOKEN_RE.search(s) or any(re.search(r"\d", m) for m in LONG_TOKEN_RE.findall(s)):
            return True
    return False


def clean_title(text, limit: int = TITLE_CHARS, is_path: bool = False) -> str:
    """One short plain line: no line breaks, no markup that could read as a tag, nothing that could run
    as a command. A title with anything like a secret in it is hidden whole, tested on the text before it
    is cut, so a cut can never leave half of one. A folder path comes from the tool, not from typing, so
    only the secret itself comes out of it and a long path with a digit in it stays readable."""
    if not is_path and looks_secret(str(text)[:READ_CHARS]):
        return HIDDEN_TITLE
    s = CONTROL_RE.sub(" ", str(text)[:READ_CHARS])
    s = _no_shell(TAG_RE.sub(" ", s).replace("<", " ").replace(">", " "))
    if WHOLE_TITLE_RE.search(s):
        return HIDDEN_TITLE
    for rx in SECRET_RES:
        s = rx.sub("[hidden]", s)
    if not is_path:
        s = LONG_TOKEN_RE.sub(_hide_long, s)
    s = MIXED_TOKEN_RE.sub("[hidden]", s)
    if s.count("[hidden]") >= 2:
        return HIDDEN_TITLE
    s = " ".join(s.split())
    if len(s) > limit:
        s = s[:limit - 3].rstrip() + "..."
    return s or "(no title)"


# ---------------------------------------------------------------- reading one transcript

def parse_time(value):
    """Epoch seconds, or None. A time with no zone is taken as local."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        when = value / 1000 if value > 1e11 else float(value)
    elif isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")
        s = re.sub(r"\.(\d{1,6})\d*", lambda m: "." + m.group(1).ljust(6, "0"), s)
        try:
            when = dt.datetime.fromisoformat(s).timestamp()
        except (ValueError, OverflowError, OSError):
            return None
    else:
        return None
    return when if 946684800 <= when <= 4102444800 else None   # 2000 to 2100; anything else is not a real time


def local_date(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch).date().isoformat()


def block_text(content) -> str:
    """The typed text of a message: a plain string, or the text blocks of a list (never tool output)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(b.get("text") or "") for b in content
                        if isinstance(b, dict) and b.get("type") in ("text", "input_text"))
    return ""


def typed(text: str) -> str:
    text = text.strip() if isinstance(text, str) else ""
    return "" if not text or text.startswith(NOT_TYPED) else text


class Reader:
    """Collects what one file says, line by line. Nothing but the fields below is kept."""

    def __init__(self, source: str, marks: list[str]):
        self.source, self.marks = source, marks
        self.known = False          # at least one line in a shape this code knows
        self.main = self.side = 0   # user lines outside and inside a subagent
        self.first = ""             # the first typed request
        self.users = 0
        self.first_event = ""       # Codex says each typed message twice; its event form is the clean one
        self.events = 0
        self.first_time = None
        self.cwd = ""
        self.in_vault = self.touched = False
        self.subagent = False
        self.sdk = self.person = False       # which entrypoints the lines name (Claude Code)
        self.meta_seen = self.exec = False   # the file's own first session_meta (Codex)
        self.fork_of = ""                    # the session this one was forked from, when the file says
        # When the last typed messages were sent, enough to tell if many came after a session was logged.
        self.times = collections.deque(maxlen=CONTINUED_MESSAGES)
        self.event_times = collections.deque(maxlen=CONTINUED_MESSAGES)
        # A one-way fingerprint of all typed messages so far, for the last few messages. Enough to tell
        # whether one session is an exact copy of another, and it holds no words.
        self.prints = collections.deque(maxlen=COPY_GAP + 1)
        self.event_prints = collections.deque(maxlen=COPY_GAP + 1)

    def note_print(self, prints, text: str) -> None:
        last = prints[-1] if prints else ""
        prints.append(hashlib.sha256(f"{last}\0{text}".encode("utf-8", "replace")).hexdigest()[:16])

    def note_time(self, times, value) -> None:
        when = parse_time(value)
        if when is not None:
            times.append(int(when))

    def note_cwd(self, cwd) -> None:
        if not isinstance(cwd, str) or not cwd.startswith("/") or len(cwd) > 4096:
            return     # a folder is a path; anything else in this slot is not kept
        self.cwd = self.cwd or cwd
        if self.in_vault or not self.marks:
            return
        for path in (cwd, os.path.realpath(cwd)):
            if path == self.marks[0] or path.startswith(self.marks[0] + os.sep):
                self.in_vault = True

    def note_text(self, text: str) -> None:
        part = text[:MENTION_CHARS]
        if MENTION_RE.search(part) or any(m in part for m in self.marks):
            self.touched = True

    def note_tool(self, payload) -> None:
        """A tool call that named the vault folder touched the cortex. Only calls count: the start card
        names the vault in every session, so its mere presence in a transcript says nothing."""
        if any(m in json.dumps(payload, ensure_ascii=False) for m in self.marks):
            self.touched = True

    def claude(self, e: dict) -> None:
        kind = e.get("type")
        self.known = self.known or kind in CLAUDE_TYPES
        entry = e.get("entrypoint")
        if isinstance(entry, str) and entry:   # any value but sdk-* is a person, known or not
            self.sdk, self.person = self.sdk or entry.startswith("sdk-"), self.person or not entry.startswith("sdk-")
        fork = e.get("forkedFrom")
        if isinstance(fork, dict) and isinstance(fork.get("sessionId"), str):
            self.fork_of = self.fork_of or fork["sessionId"]
        if kind == "assistant":
            content = (e.get("message") or {}).get("content") if isinstance(e.get("message"), dict) else None
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    self.note_tool(b.get("input"))
            return
        if kind != "user":
            return
        if e.get("isSidechain"):
            self.side += 1
            return
        self.main += 1
        self.note_cwd(e.get("cwd"))
        if self.first_time is None:
            self.first_time = parse_time(e.get("timestamp"))
        if e.get("isMeta") or e.get("isCompactSummary") or e.get("isVisibleInTranscriptOnly"):
            return
        msg = e.get("message")
        text = typed(block_text(msg.get("content") if isinstance(msg, dict) else None))
        if text:
            self.users += 1
            self.first = self.first or text
            self.note_text(text)
            self.note_time(self.times, e.get("timestamp"))
            self.note_print(self.prints, text)

    def codex(self, e: dict) -> None:
        kind = e.get("type")
        self.known = self.known or kind in CODEX_TYPES
        p = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        if self.first_time is None:
            self.first_time = parse_time(e.get("timestamp"))
        if kind == "session_meta":
            self.note_cwd(p.get("cwd"))
            src = p.get("source")
            if (isinstance(src, dict) and "subagent" in src) or src == "subagent":
                self.subagent = True
            if not self.meta_seen:      # a fork carries its parent's meta further down
                self.meta_seen = True
                self.exec = src == "exec" or p.get("originator") == "codex_exec"
                if isinstance(p.get("forked_from_id"), str):
                    self.fork_of = p["forked_from_id"]
        elif kind == "turn_context":
            self.note_cwd(p.get("cwd"))
        elif kind == "event_msg" and p.get("type") == "user_message":
            text = typed(p.get("message"))
            if text:
                self.events += 1
                self.first_event = self.first_event or text
                self.note_text(text)
                self.note_time(self.event_times, e.get("timestamp"))
                self.note_print(self.event_prints, text)
        elif kind == "response_item" or kind == "message":
            item = p if kind == "response_item" else e
            if item.get("type") == "message" and item.get("role") == "user":
                text = typed(block_text(item.get("content")))
                if text:
                    self.users += 1
                    self.first = self.first or text
                    self.note_text(text)
                    self.note_time(self.times, e.get("timestamp"))
                    self.note_print(self.prints, text)
            elif item.get("type") in ("function_call", "local_shell_call", "custom_tool_call"):
                self.note_tool(item)


def read_lines(fh, deadline: float, out: dict):
    """The file's lines as bytes, each bounded. Stops at the byte cap or the time limit and says so."""
    total, too_long = 0, False
    while True:
        line = fh.readline(MAX_LINE)
        if not line:
            return
        total += len(line)
        if total > MAX_FILE_BYTES:
            out["truncated"] = True
            return
        if time.monotonic() > deadline:
            out["truncated"] = out["clock_cut"] = True   # only this run's clock: worth reading again
            return
        ended = line.endswith(b"\n")
        if not too_long and (ended or len(line) < MAX_LINE):
            yield line
        too_long = not ended and len(line) == MAX_LINE   # the rest of an over-long line is dropped too


def read_transcript(path: str, source: str, marks: list[str], deadline: float) -> dict | None:
    """What one transcript says, or None when it is gone or cannot be opened. Fails closed: no text but
    the title leaves this function."""
    out = {"truncated": False, "clock_cut": False}
    r = Reader(source, marks)
    needles = [b"user"] + [m.encode("utf-8", "ignore") for m in marks]
    any_line = False
    bookkeeping, lines, size = True, 0, 0
    try:
        # O_NONBLOCK and O_NOFOLLOW: a pipe or a link named like a transcript cannot hang or redirect the read.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as fh:
            if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
                return None
            size = os.fstat(fh.fileno()).st_size
            for n, raw in enumerate(read_lines(fh, deadline, out)):
                if not raw.strip():
                    continue
                any_line = True
                lines += 1
                # Reading JSON is the slow part, and most lines are tool output nobody needs here.
                if n > 20 and not any(x in raw for x in needles):
                    continue
                try:
                    e = json.loads(raw)
                    bookkeeping = bookkeeping and _is_bookkeeping(e)
                    if isinstance(e, dict):
                        (r.claude if source == "claude" else r.codex)(e)
                except (ValueError, TypeError, AttributeError, RecursionError):
                    bookkeeping = False
                    continue    # one bad line never costs the rest of the file
    except OSError:
        return None
    users, first = (r.events, r.first_event) if r.events else (r.users, r.first)
    times = r.event_times if r.events else r.times
    prints = r.event_prints if r.events else r.prints
    folder = _folder_name(r.cwd, path, source)
    kind = "session"
    if not any_line:
        kind = "unknown" if out["truncated"] else "empty"   # one endless line is not an empty file
    elif not r.known:
        small = not out["truncated"] and size <= METADATA_BYTES and lines <= METADATA_LINES
        kind = "metadata" if bookkeeping and small else "unknown"
    elif r.subagent or (source == "claude" and r.side and not r.main):
        kind = "subagent"
    elif first.startswith(AUTOMATION_MARK) or r.exec or (r.sdk and not r.person):
        kind = "automated"
    elif out["truncated"] and users < MIN_USER_MESSAGES:
        kind = "unknown"
    return {"kind": kind, "users": users, "title": clean_title(first) if first else "",
            "first_time": r.first_time, "folder": folder, "in_vault": r.in_vault, "touched": r.touched,
            "truncated": out["truncated"], "clock_cut": out["clock_cut"], "times": list(times), "fork_of": r.fork_of,
            "prints": list(prints)}


def _is_bookkeeping(e) -> bool:
    """A line such as custom-title or bridge-session: it names its own type and holds no conversation."""
    return isinstance(e, dict) and isinstance(e.get("type"), str) and not TALK_KEYS & set(e)


def good_row(hit, mtime, size) -> bool:
    """A cache row is only used when it is for this exact file and every field has the right type."""
    if not isinstance(hit, dict) or hit.get("mtime") != mtime or hit.get("size") != size:
        return False
    number = lambda v: type(v) in (int, float)  # noqa: E731
    first, times, prints = hit.get("first_time"), hit.get("times"), hit.get("prints")
    return (isinstance(hit.get("kind"), str) and type(hit.get("users")) is int
            and isinstance(hit.get("title"), str) and isinstance(hit.get("folder"), str)
            and isinstance(hit.get("fork_of"), str)
            and all(type(hit.get(k)) is bool for k in ("in_vault", "touched", "truncated"))
            and (first is None or (number(first) and 946684800 <= first <= 4102444800))
            and isinstance(times, list) and all(number(t) for t in times)
            and isinstance(prints, list) and all(isinstance(p, str) for p in prints))


# ---------------------------------------------------------------- finding transcripts

def _regular_files(folder: Path, prefix: str = ""):
    try:
        with os.scandir(folder) as it:
            for f in it:
                if f.name.endswith(".jsonl") and f.name.startswith(prefix) and f.is_file(follow_symlinks=False):
                    yield f
    except OSError:
        return


def _subfolders(folder: Path):
    try:
        with os.scandir(folder) as it:
            return sorted(Path(d.path) for d in it if d.is_dir(follow_symlinks=False))
    except OSError:
        return []


def candidates():
    """(source, DirEntry) for every transcript on this Mac, without opening any of them."""
    for proj in _subfolders(home() / ".claude" / "projects"):
        for f in _regular_files(proj):
            yield "claude", f
    for year in _subfolders(home() / ".codex" / "sessions"):
        for month in _subfolders(year):
            for day in _subfolders(month):
                for f in _regular_files(day, "rollout-"):
                    yield "codex", f


def session_id(source: str, name: str) -> str | None:
    """The id comes from the file name, never from inside the file: a poisoned line cannot claim
    another session's id. It is used as a folder name below, so it must be a safe one."""
    stem = name[:-6]
    if source == "codex":
        m = CODEX_ID_RE.search(stem)
        stem = m.group(1) if m else stem
    return stem if ID_RE.match(stem) else None


# ---------------------------------------------------------------- is it covered?

def page_chat_ids(vault: Path) -> dict[str, float]:
    """Every chat id on a page, with when that page last changed."""
    ids: dict[str, float] = {}
    for p in C.iter_pages(vault):
        v = p.meta.get("chat_id") if p.meta else None
        if v:
            try:
                when = (vault / p.rel).stat().st_mtime
            except OSError:
                when = 0
            for x in v if isinstance(v, list) else [v]:
                ids[str(x)] = max(ids.get(str(x), 0), when)
    return ids


def wrote_pages(session_dir: Path, vault: Path) -> bool:
    try:
        lines = read_regular(session_dir / "written.txt", 256 * 1024).decode("utf-8", "ignore").splitlines()
    except OSError:
        return False
    root = str(vault) + os.sep
    generated = root + C.GENERATED + os.sep
    return any(l.startswith(root) and l.endswith(".md") and not l.startswith(generated) for l in lines)


def covered_by(sid: str, chat_ids, vault: Path) -> str:
    d = home() / ".cortex" / "sessions" / sid
    if (d / "logged").exists():
        return "logged"
    if (d / "skipped").exists():    # the person said "skip" when asked; asking again would be nagging
        return "skipped"
    if sid in chat_ids:
        return "page"
    return "wrote" if wrote_pages(d, vault) else ""


def covered_at(sid: str, chat_ids: dict[str, float]) -> float:
    """The last time this session reached the vault, from the flag, the ledger and its pages."""
    d = home() / ".cortex" / "sessions" / sid
    latest = chat_ids.get(sid, 0)
    for name in ("logged", "written.txt"):
        try:
            latest = max(latest, (d / name).stat().st_mtime)
        except OSError:
            pass
    return latest


def continued_after(row: dict, when: float) -> bool:
    """Were many messages typed after this time? The file's last few times are enough to say."""
    times = row.get("times") or []
    return bool(when) and len(times) >= CONTINUED_MESSAGES and times[-CONTINUED_MESSAGES] > when


def scope_of(vault: Path) -> str:
    """Which sessions can count as missed. 'cortex' (the default): those in the vault folder, plus
    those whose typed messages mention the cortex or whose tool calls named the vault. 'all': every
    session. 'off': the Gardener does nothing. See docs/SPEC.md for why."""
    v = C.parse_kit(vault).get("gardener_scope", "cortex")
    return v if isinstance(v, str) and v in SCOPES else "cortex"


def elsewhere_off(vault: Path) -> bool:
    """gardener_elsewhere: off in kit.yaml: sessions elsewhere are not mentioned at all."""
    return str(C.parse_kit(vault).get("gardener_elsewhere", "")).strip().lower() == "off"


def vault_marks(vault: Path) -> list[str]:
    marks = [str(vault)]
    try:
        marks.append("~/" + vault.relative_to(home().resolve()).as_posix())
    except ValueError:
        pass
    return marks


# ---------------------------------------------------------------- the inventory

def load_state() -> dict:
    return read_json(state_dir() / "state.json", {})


def dismissed_ids() -> set[str]:
    d = load_state().get("dismissed")
    return set(d) if isinstance(d, dict) else set()


def set_dismissed(sid: str, on: bool) -> None:
    if not ID_RE.match(sid):
        raise ValueError("not a session id")
    d = state_dir()
    with (d / "state.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state()
        items = state.get("dismissed") if isinstance(state.get("dismissed"), dict) else {}
        if on:
            items[sid] = C.today()
        else:
            items.pop(sid, None)
        state["dismissed"] = dict(sorted(items.items(), key=lambda kv: str(kv[1]))[-MAX_DISMISSED:])
        write_private(d / "state.json", json.dumps(state))
        if on:     # the start card must agree at once, not after the next scan
            _take_off_summary(d, sid)


def claim_elsewhere_line(vault: Path, now: float | None = None) -> bool:
    """May the start card say how many sessions elsewhere were not checked? At most once a week per
    vault, recorded before it is said. When that cannot be recorded, it is not said."""
    if elsewhere_off(vault):
        return False
    now = time.time() if now is None else now
    d = state_dir()
    with (d / "state.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)    # a session start never waits on this
        except OSError:
            return False
        state = load_state()
        shown = state.get("elsewhere_shown") if isinstance(state.get("elsewhere_shown"), dict) else {}
        shown = {k: v for k, v in shown.items() if type(v) in (int, float)}
        last = shown.get(vault_key(vault))
        if last is not None and 0 <= now - last < ELSEWHERE_EVERY:      # a date ahead of the clock counts for nothing
            return False
        shown[vault_key(vault)] = now
        state["elsewhere_shown"] = dict(sorted(shown.items(), key=lambda kv: kv[1])[-SUMMARY_VAULTS:])
        write_private(d / "state.json", json.dumps(state))
    return True


def _take_off_summary(d: Path, sid: str) -> None:
    summary = read_json(d / "summary.json", {})
    vaults = summary.get("vaults") if isinstance(summary.get("vaults"), dict) else {}
    changed = False
    for entry in vaults.values():
        for ids_key, count_key in (("week_ids", "week"), ("continued_ids", "week"), ("elsewhere_ids", "elsewhere")):
            ids = entry.get(ids_key) if isinstance(entry, dict) else None
            if isinstance(ids, list) and sid in ids and isinstance(entry.get(count_key), int):
                ids.remove(sid)
                entry[count_key] = max(0, entry[count_key] - 1)
                changed = True
    if changed:
        write_private(d / "summary.json", json.dumps(summary))


def vault_key(vault: Path) -> str:
    return os.path.realpath(str(vault))


def write_summary(vault: Path, entry: dict) -> None:
    """The start hook's numbers, per vault: a run on one vault says nothing about another."""
    d = state_dir()
    with (d / "state.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old = read_json(d / "summary.json", {})
        vaults = old.get("vaults") if isinstance(old.get("vaults"), dict) else {}
        vaults = {k: v for k, v in vaults.items() if isinstance(v, dict) and isinstance(v.get("at"), (int, float))}
        vaults[vault_key(vault)] = entry
        newest = sorted(vaults.items(), key=lambda kv: kv[1]["at"], reverse=True)[:SUMMARY_VAULTS]
        write_private(d / "summary.json", json.dumps({"vaults": dict(newest)}))


def scan(vault: Path, budget: float, now: float) -> tuple[list[dict], dict]:
    """One row per transcript, newest first, with its status. Rows come from the cache unless the file
    changed, so a repeat run only costs a stat per file. Out of time, the rest wait for the next run."""
    scope = scope_of(vault)
    info = {"scope": scope, "not_finished": 0, "too_old": 0}
    d = state_dir()
    if scope == "off":
        (d / "cache.json").unlink(missing_ok=True)   # switched off means no titles kept either
        return [], info
    stop_at = time.monotonic() + budget
    old = read_json(d / "cache.json", {})
    usable = old.get("version") == CACHE_VERSION and old.get("vault") == str(vault)
    cache = old.get("files") if usable and isinstance(old.get("files"), dict) else {}
    files = []
    for source, f in candidates():
        try:
            st = f.stat(follow_symlinks=False)
        except OSError:
            continue     # deleted since it was listed
        if st.st_mtime >= now - LOOKBACK_DAYS * 86400:
            files.append((st.st_mtime, st.st_size, source, f.path, f.name))
        else:
            info["too_old"] += 1
    files.sort(reverse=True)
    marks = vault_marks(vault)
    chat_ids = page_chat_ids(vault)
    dismissed = dismissed_ids()
    current = {os.environ.get(k) for k in SESSION_ENVS} - {None, ""}   # the chat asking is still going on
    rows, fresh_cache, dirty = [], {}, not usable
    for mtime, size, source, path, name in files:
        base = {"path": path, "source": source, "mtime": mtime, "id": session_id(source, name)}
        if mtime > now - FRESH_SECONDS or base["id"] in current:
            rows.append(dict(base, status="too_recent"))
            continue
        if source == "claude" and name.startswith("agent-"):
            rows.append(dict(base, status="subagent"))
            continue
        hit = cache.get(path)
        if good_row(hit, mtime, size):
            meta = hit
        else:
            left = stop_at - time.monotonic()
            if left <= 0:
                info["not_finished"] += 1
                continue
            meta = read_transcript(path, source, marks, time.monotonic() + min(FILE_SECONDS, left))
            if meta is None:
                continue     # deleted while being read, or not a plain file
            cut = meta.pop("clock_cut")
            if cut and (meta["users"] < MIN_USER_MESSAGES or stop_at - time.monotonic() <= 0):
                info["not_finished"] += 1     # cut by this run's clock, not by its size: read it again later
                continue
            meta.update(mtime=mtime, size=size)
            if cut:    # enough to list now, but not kept, so the next run reads the rest
                rows.append(_classify(dict(base, **meta), scope, chat_ids, dismissed, vault))
                continue
            dirty = True
        fresh_cache[path] = meta
        rows.append(_classify(dict(base, **meta), scope, chat_ids, dismissed, vault))
    if dirty or len(fresh_cache) != len(cache):
        write_private(d / "cache.json", json.dumps({"version": CACHE_VERSION, "vault": str(vault), "files": fresh_cache}))
    collapse_forks(rows)
    return rows, info


def _is_copy(longer: dict, shorter: dict) -> bool:
    """The shorter session's typed messages are the longer one's first messages, and at most COPY_GAP are
    added. One that goes on for longer, or changes direction, is its own work."""
    gap = longer["users"] - shorter["users"]
    prints, own = longer.get("prints") or [], shorter.get("prints") or []
    return 0 <= gap <= COPY_GAP and gap < len(prints) and bool(own) and prints[-1 - gap] == own[-1]


def _same_start(a: dict, b: dict) -> bool:
    """They began as one: the same first moment, or the file's own note of where it was forked from.
    The same words typed at another moment are two sessions."""
    if a.get("first_time") and a.get("first_time") == b.get("first_time"):
        return True
    x, y = a.get("fork_of"), b.get("fork_of")
    return x == b["id"] or y == a["id"] or (bool(x) and x == y)


def collapse_forks(rows: list[dict]) -> None:
    """Only an exact copy shares a row, with the session it copies, the one with the most messages. Any
    other fork is listed by itself. A dismissed session takes no part: a dismissal is for one id only.
    Nor does a file not read to its end, as its count cannot be trusted."""
    live = [r for r in rows if r.get("id") and r["status"] in ("missed", "covered", "other_folder") and not r.get("truncated")]
    groups: list[list[dict]] = []
    heads: dict[tuple, list[list[dict]]] = {}
    for r in sorted(live, key=lambda r: (r["users"], r["mtime"]), reverse=True):
        last = (r.get("prints") or [""])[-1]
        group = next((g for g in heads.get((r["source"], last), []) if _is_copy(g[0], r) and _same_start(g[0], r)), None)
        if group:
            group.append(r)
            continue
        groups.append([r])
        for p in r.get("prints") or []:
            heads.setdefault((r["source"], p), []).append(groups[-1])
    for group in groups:
        if len(group) < 2:
            continue
        keep = group[0]
        logged = [r for r in group if r["status"] == "covered"]
        keep["also"] = [r["path"] for r in group[1:]]
        for r in group[1:]:
            r["status"] = "fork_copy"
        if keep["status"] != "covered" and logged:
            if continued_after(keep, max(r.get("cover_at", 0) for r in logged)):
                keep["status"], keep["continued"] = "missed", True
            else:
                keep["status"], keep["route"], keep["continued"] = "covered", logged[0]["route"], False


def _classify(row: dict, scope: str, chat_ids: dict[str, float], dismissed: set[str], vault: Path) -> dict:
    sid = row["id"]
    kind = row.get("kind")
    row["date"] = local_date(row["first_time"] if row.get("first_time") else row["mtime"])
    if kind != "session":
        row["status"] = {"subagent": "subagent", "automated": "automated", "unknown": "unknown"}.get(kind, "short")
    elif not sid:
        row["status"] = "unknown"
    elif (home() / ".cortex" / "sessions" / sid / "automation").exists():
        row["status"] = "automated"
    elif row["users"] < MIN_USER_MESSAGES:
        row["status"] = "short"
    else:
        route = covered_by(sid, chat_ids, vault)
        at = covered_at(sid, chat_ids) if route and route != "skipped" else 0
        if route and not continued_after(row, at):
            row["status"], row["route"], row["cover_at"] = "covered", route, at
        elif sid in dismissed:
            row["status"] = "dismissed"
        elif route or scope == "all" or row.get("in_vault") or row.get("touched"):
            row["status"], row["continued"] = "missed", bool(route)   # logged once, then much more work
        else:
            row["status"] = "other_folder"
    return row


def _folder_name(cwd: str, path: str, source: str) -> str:
    if cwd:
        h = str(home())
        return clean_title("~" + cwd[len(h):] if cwd == h or cwd.startswith(h + os.sep) else cwd, 60, is_path=True)
    return clean_title(Path(path).parent.name, 60, is_path=True) if source == "claude" else "(unknown folder)"


def public_row(r: dict, now: float) -> dict:
    return {"id": r["id"], "source": r["source"], "date": r["date"], "folder": r["folder"],
            "title": r.get("title") or "(no title)", "users": r["users"], "path": r["path"],
            "age_days": int((now - r["mtime"]) // 86400), "continued": bool(r.get("continued")),
            "also": r.get("also") or []}


def elsewhere_line(n: int) -> str:
    return (f"{n} session{' elsewhere was' if n == 1 else 's elsewhere were'} not checked - "
            f"say 'catch up' to see {'it' if n == 1 else 'them'}.")


def risk_warning(oldest_mtime: float, now: float) -> str:
    return (f"Your oldest unlogged Claude Code session is {int((now - oldest_mtime) // 86400)} days old. "
            "Claude Code deletes transcripts after 30 days by default, so say 'catch up' soon.")


def inventory(vault: Path, days: int = 7, budget: float = CLI_SECONDS, now: float | None = None) -> dict:
    """The report behind the command, the start card and the Inbox. Reads no text beyond titles."""
    now = time.time() if now is None else now
    asked = days
    days = max(0, min(days, MAX_DAYS))
    rows, info = scan(vault, budget, now)
    quiet = elsewhere_off(vault)
    since = now - (days + OVERLAP_DAYS) * 86400
    window = [r for r in rows if r["mtime"] >= since]
    count = lambda status: sum(1 for r in window if r["status"] == status)  # noqa: E731
    missed_all = [r for r in rows if r["status"] == "missed"]
    routes: dict[str, int] = {}
    for r in window:
        if r["status"] == "covered":
            routes[r["route"]] = routes.get(r["route"], 0) + 1
    at_risk = [r for r in missed_all if r["source"] == "claude" and now - r["mtime"] > WARN_DAYS * 86400]
    oldest = min((r["mtime"] for r in at_risk), default=0)
    newest_first = lambda status, among: [public_row(r, now) for r in sorted((r for r in among if r["status"] == status),  # noqa: E731
                                                                             key=lambda r: (r["date"], r["mtime"]), reverse=True)]
    report = {
        "scope": info["scope"], "window_days": days + OVERLAP_DAYS,
        "days_asked": asked, "days_cut": asked > days, "too_old": info["too_old"],
        "missed": newest_first("missed", window),
        "elsewhere": [] if quiet else newest_first("other_folder", window),
        "dismissed_rows": newest_first("dismissed", rows),
        "older_missed": sum(1 for r in missed_all if r["mtime"] < since),
        "covered": sum(routes.values()), "covered_by": routes, "dismissed": count("dismissed"),
        "other_folders": 0 if quiet else count("other_folder"),
        "skipped": {"too_recent": count("too_recent"), "subagent": count("subagent"), "short": count("short"),
                    "automated": count("automated"), "fork_copies": count("fork_copy")},
        "unreadable": count("unknown"), "not_finished": info["not_finished"],
        "warning": risk_warning(oldest, now) if at_risk else "",
    }
    week = [r for r in missed_all if r["mtime"] >= now - 7 * 86400]
    away = [] if quiet else [r for r in rows if r["status"] == "other_folder" and r["mtime"] >= now - ELSEWHERE_DAYS * 86400]
    report["elsewhere_week"] = len(away)     # the number the card and the board both say
    # The only file the start hook reads: counts and ids, no titles, so no chat text reaches the card.
    # A continued session keeps its logged flag, so the hook must not take it off the count for that.
    write_summary(vault, {
        "at": now, "week": len(week), "week_ids": [r["id"] for r in week if not r.get("continued")][:WEEK_IDS],
        "continued_ids": [r["id"] for r in week if r.get("continued")][:WEEK_IDS],
        "elsewhere": len(away), "elsewhere_ids": [r["id"] for r in away][:WEEK_IDS],
        "risk_oldest": oldest, "partial": bool(info["not_finished"])})
    return report


def refresh(vault: Path) -> int:
    """The background run the start hook starts. One at a time; a second one simply leaves."""
    with (state_dir() / "refresh.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return 0
        try:
            os.nice(10)
        except OSError:
            pass
        inventory(vault, budget=REFRESH_SECONDS)
    return 0


# ---------------------------------------------------------------- the weekly journal

def week_bounds(week: str | None, today: dt.date) -> tuple[int, int, dt.date, dt.date]:
    if week:
        m = re.fullmatch(r"(\d{4})-W(\d{2})", week)
        if not m:
            raise ValueError("week must look like 2026-W44")
        year, num = int(m.group(1)), int(m.group(2))
        try:
            monday = dt.date.fromisocalendar(year, num, 1)
            return year, num, monday, monday + dt.timedelta(days=6)
        except (ValueError, OverflowError):
            raise ValueError(f"{week} is not a week the calendar has. It must look like 2026-W44.") from None
    else:
        year, num, _ = today.isocalendar()
        monday = today - dt.timedelta(days=today.weekday())
    return year, num, monday, monday + dt.timedelta(days=6)


def render_journal(vault: Path, week: str | None = None, now: float | None = None) -> tuple[Path, str]:
    """Counted by code from the record. The only titles are those of logged pages: a missed session
    is a number here, because its title comes from a chat and this file is backed up to GitHub."""
    now = time.time() if now is None else now
    today = dt.datetime.fromtimestamp(now).date()
    year, num, monday, sunday = week_bounds(week, today)
    lo, hi = monday.isoformat(), sunday.isoformat()
    inside = lambda d: bool(d) and lo <= str(d) <= hi  # noqa: E731
    pages = [p for p in C.iter_pages(vault) if not getattr(p, "loose", False)]
    me = C.self_slugs(vault)
    logged = sorted((p for p in pages if p.get("type") == "session" and inside(p.get("created"))),
                    key=lambda p: (str(p.get("created")), p.rel))
    tally = {"todo_opened": 0, "todo_closed": 0, "other_opened": 0, "other_closed": 0}
    for p in pages:
        for _, line in C.task_lines(p.body.split("\n")):
            t = C.parse_task(line, me)
            if not t:
                continue
            group = "todo" if t["todo"] else "other"
            tally[group + "_opened"] += inside(t["added"])
            tally[group + "_closed"] += t["closed"] and inside(t["done"])
    rows, info = scan(vault, CLI_SECONDS, now)
    missed = sum(1 for r in rows if r["status"] == "missed" and inside(r["date"]))
    dismissed = sum(1 for r in rows if r["status"] == "dismissed" and inside(r["date"]))
    lines = [f"# Week {year}-W{num:02d} ({lo} to {hi})", "",
             f"Generated {today.isoformat()} by code from your pages and the session files on this Mac. "
             "Do not edit by hand.", "",
             "| What | Count |", "|---|---|",
             f"| Sessions logged | {len(logged)} |",
             f"| Sessions missed (never logged) | {missed} |",
             f"| Sessions you dismissed | {dismissed} |",
             f"| To-dos opened | {tally['todo_opened']} |",
             f"| To-dos closed | {tally['todo_closed']} |",
             f"| Follow-ups opened | {tally['other_opened']} |",
             f"| Follow-ups closed | {tally['other_closed']} |", ""]
    if logged:
        lines += ["## Logged sessions", ""]
        for p in logged:
            title = "(private)" if "{private}" in str(p.get("title")) else clean_title(p.get("title"), 120)
            lines.append(f"- {p.get('created')} - {title}")
        lines.append("")
    lines.append("Opened and closed count only lines that carry an (added) or (done) date. "
                 "A session counts in the week it started.")
    if monday < today - dt.timedelta(days=LOOKBACK_DAYS - 2):
        lines.append("Session files this old may already be deleted, so the missed count can be low.")
    if info["not_finished"]:
        lines.append(f"{info['not_finished']} session file(s) were not read in time, so the missed count can be low.")
    return vault / C.GENERATED / "journal" / f"{year}-W{num:02d}.md", "\n".join(lines) + "\n"


def write_journal(vault: Path, week: str | None = None, now: float | None = None) -> Path:
    path, text = render_journal(vault, week, now)
    C.write_atomic(path, text)
    return path


# ---------------------------------------------------------------- the schedule (only on a person's yes)

def last_due(now: float) -> dt.datetime:
    """The most recent Sunday 17:00 on this Mac's clock."""
    return C.last_weekly_due(now, 17)


def run_if_due(vault: Path, now: float | None = None) -> str | None:
    """launchd starts this at Sunday 17:00, on waking if the Mac slept through it, and at every login.
    So a Mac that was off still gets its run when it comes back, and a login in the same week does
    nothing. The journal is for the week that ended on the missed Sunday, not the week it runs in."""
    if scope_of(vault) == "off":
        return None
    now = time.time() if now is None else now
    due = last_due(now)
    stamp = state_dir() / "last-weekly-run"
    try:
        if due.timestamp() <= float(stamp.read_text().strip()) <= now:     # a stamp in the future is a wrong clock
            return None
    except (OSError, ValueError):
        pass
    refresh(vault)
    year, num, _ = due.date().isocalendar()[:3]
    path = write_journal(vault, f"{year}-W{num:02d}", now)
    C.write_atomic(stamp, str(now))
    return str(path)


PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.cortex.gardener</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>{script}</string>
    <string>gardener</string><string>--if-due</string><string>--quiet</string>
    <string>--vault</string><string>{vault}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>StartCalendarInterval</key><dict><key>Weekday</key><integer>0</integer>
    <key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>{home}/.cortex/gardener/agent.log</string>
  <key>StandardErrorPath</key><string>{home}/.cortex/gardener/agent.log</string>
</dict></plist>
"""


def install_schedule(args) -> int:
    """Setup and upgrade never call this: it runs only when a person has said yes to a weekly run."""
    plist = home() / "Library" / "LaunchAgents" / "com.cortex.gardener.plist"
    if args.off:
        if not os.environ.get("CORTEX_NO_LAUNCHD"):
            try:
                subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)], capture_output=True)
            except OSError:
                pass      # no launchctl, so nothing is loaded
        plist.unlink(missing_ok=True)
        print("The weekly Gardener is off. The start card and 'catch up' still work.")
        return 0
    if not args.yes:
        print("This would run the Gardener every Sunday at 17:00, or as soon as your Mac is back if it was asleep "
              "or off then. It counts your sessions and writes the weekly journal. It does not need the Claude app open. "
              "No AI, nothing sent anywhere. Nothing was changed. Run again with --yes to switch it on.")
        return 0
    vault = C.vault_path(args.vault)
    script = home() / ".cortex" / "engine" / "scripts" / "cortex.py"   # kept current by every session start
    if not script.exists():
        print("Start a session in your coding tool once, then try again: the kit's stable copy is not there yet.")
        return 1
    state_dir()
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(PLIST.format(script=escape(str(script)), vault=escape(str(vault)), home=escape(str(home()))))
    if os.environ.get("CORTEX_NO_LAUNCHD"):
        print("Weekly Gardener file written (test mode: not switched on).")
        return 0
    uid = os.getuid()
    try:
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(plist)], capture_output=True)
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True, text=True)
    except OSError:
        print("Weekly Gardener file written but not switched on: this computer has no launchctl (Mac only).")
        return 1
    if r.returncode != 0:
        print(f"Weekly Gardener file written but could not be switched on: {r.stderr.strip()}")
        return 1
    print("The weekly Gardener is on: every Sunday at 17:00, or as soon as your Mac is back if it was asleep or off then. "
          "It does not need the Claude app open. No AI, nothing sent anywhere.")
    return 0


# ---------------------------------------------------------------- the command

def print_report(rep: dict) -> None:
    if rep["scope"] == "off":
        print("The Gardener is off (gardener_scope: off in kit.yaml).")
        return
    missed, away = rep["missed"], rep["elsewhere"]
    if rep["days_cut"]:
        print(f"Only the last {LOOKBACK_DAYS} days are read, so --days {rep['days_asked']} was cut to {MAX_DAYS}. "
              f"{rep['too_old']} older session file(s) were not read.")
    print(f"Last {rep['window_days']} days: {rep['covered']} session(s) logged or skipped by you, {len(missed)} never logged"
          + (f", {len(away)} elsewhere not checked." if away else "."))
    for r in missed:
        note = ", continued after it was logged" if r["continued"] else ""
        print(f"  {r['date']}  {r['folder']}  \"{r['title']}\"  ({r['users']} messages, {r['source']}{note})  id {r['id']}")
    if missed:
        print("Say 'catch up' to log any of these.")
    if rep["older_missed"]:
        print(f"{rep['older_missed']} older session(s) were never logged too. See them with --days 30.")
    if rep["warning"]:
        print("WARNING: " + rep["warning"])
    if rep["other_folders"]:
        print(f"Not checked: {rep['other_folders']} session(s) in other folders that never mention your cortex. "
              "To count them, set gardener_scope: all in kit.yaml.")
        for r in away[:10]:
            print(f"  {r['date']}  {r['folder']}  \"{r['title']}\"  ({r['users']} messages, {r['source']})  id {r['id']}")
        if len(away) > 10:
            print(f"  and {len(away) - 10} more. Say 'catch up' to go through them.")
    if rep["dismissed"]:
        print(f"Dismissed by you: {rep['dismissed']}.")
    if rep["unreadable"]:
        print(f"Could not understand {rep['unreadable']} transcript file(s). Their format may have changed, "
              "so they are not counted. Say 'send feedback' if this number keeps growing.")
    if rep["not_finished"]:
        print(f"Ran out of time with {rep['not_finished']} file(s) left to read. Run it again to carry on.")
    print(CHAT_NOTE)


def run(args) -> int:
    if args.dismiss or args.undismiss:
        sid = args.dismiss or args.undismiss
        if not ID_RE.match(sid):
            print("That is not a session id.")
            return 2
        set_dismissed(sid, bool(args.dismiss))
        print("Dismissed. It will not come back." if args.dismiss else "Brought back.")
        return 0
    vault = C.vault_path(args.vault)
    if not vault.is_dir():
        print(f"could not read your cortex folder {vault} - it is not there.")
        return 1
    if args.if_due:
        path = run_if_due(vault)
        if not args.quiet:
            print(f"Wrote {path}" if path else "This week's run is already done.")
        return 0
    if args.refresh:
        refresh(vault)
        if not args.journal:
            return 0
    if args.journal:
        try:
            path = write_journal(vault, args.week)
        except ValueError as e:
            print(str(e))
            return 2
        if not args.quiet:
            print(f"Wrote {path.relative_to(vault).as_posix()}")
        return 0
    rep = inventory(vault, days=args.days)
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print_report(rep)
    return 0
