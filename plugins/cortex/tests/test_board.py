"""Tests for the board and inbox (0.4.0).

The server runs in-process on a background thread against a temp vault made with 'cortex.py new';
requests go through urllib like a browser's would. Nothing touches the real ~/.cortex: HOME is a
temp folder and 'open' is replaced by a recorder.
Run: python3 -m pytest plugins/cortex/tests -q
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
CORTEX = SCRIPTS / "cortex.py"
sys.path.insert(0, str(SCRIPTS))
import board as B  # noqa: E402
import cortex as C  # noqa: E402

WED = dt.date(2026, 10, 28)   # a Wednesday; this week's Friday is 30 Oct


@pytest.fixture()
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    vault = home / "cortex"
    (home / ".cortex").mkdir(parents=True)
    vault.mkdir()
    (home / ".cortex" / "config.json").write_text(json.dumps({"vault": str(vault)}))
    e = dict(os.environ, HOME=str(home), CORTEX_CONFIG=str(home / ".cortex" / "config.json"))
    for k in ("CORTEX_HOOKS",):
        e.pop(k, None)
    subprocess.run(["git", "init", "-q", "-b", "main", str(vault)], check=True)
    subprocess.run(["git", "-C", str(vault), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(vault), "config", "user.name", "Test"], check=True)
    monkeypatch.setattr(B, "today", lambda: WED)
    monkeypatch.setenv("HOME", str(home))   # undo copies and board.json go to the temp HOME
    return {"home": home, "vault": vault, "env": e}


def run(env, *args):
    return subprocess.run([sys.executable, str(CORTEX), *args], capture_output=True, text=True, env=env["env"])


def make(env, *args) -> Path:
    r = run(env, "new", *args, "--json")
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout)
    path = Path(info["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(info["content"].replace("summary: ", "summary: test page", 1))
    return path


def seed(env, lines: str, newline: str = "\n") -> Path:
    make(env, "area", "--area", "acme", "--title", "Acme")
    make(env, "thing", "--area", "acme", "--collection", "projects", "--title", "Pilot project")
    make(env, "person", "--title", "Alex Rivera")
    s = make(env, "session", "--area", "acme", "--thing", "pilot-project", "--title", "Kickoff")
    text = s.read_text() + "\n## Follow-ups\n\n" + lines
    s.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return s


@pytest.fixture()
def srv(env):
    opened = []
    board = B.Board(env["vault"], opener=lambda target: (opened.append(target), (True, ""))[1])
    server = B.start_in_thread(board)
    server.opened = opened
    yield server
    server.shutdown()
    server.server_close()


def call(server, method, path, body=None, token=True, host=None, origin=True, ctype="application/json"):
    headers = {}
    if token:
        headers["Cookie"] = f"{server.cookie}={server.token if token is True else token}"
    if host:
        headers["Host"] = host
    if method == "POST":
        if origin:
            headers["Origin"] = f"http://127.0.0.1:{server.port}" if origin is True else origin
        headers["Content-Type"] = ctype
    data = json.dumps(body or {}).encode() if method == "POST" else None
    req = urllib.request.Request(f"http://127.0.0.1:{server.port}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw, code, hdrs = r.read(), r.status, r.headers
    except urllib.error.HTTPError as e:
        raw, code, hdrs = e.read(), e.code, e.headers
    try:
        return code, json.loads(raw), hdrs
    except ValueError:
        return code, raw.decode(), hdrs


def state(server):
    code, s, _ = call(server, "GET", "/api/state")
    assert code == 200, s
    return s


def item(s, text):
    hits = [i for i in s["items"] if i["text"] == text]
    assert len(hits) == 1, [i["text"] for i in s["items"]]
    return hits[0]


def move(server, it, to):
    return call(server, "POST", "/api/move", {"id": it["id"], "sha": it["sha"], "to": to})


# ---------------------------------------------------------------- grammar

OLD_RE = re.compile(
    r"^\s*-\s\[(?P<done>[ xX])\]\s+@(?P<person>[a-z0-9-]+)\s+(?P<text>.*?)"
    r"(?:\s*\(due\s+(?P<due>\d{4}-\d{2}-\d{2})\))?\s*\{(?P<owner>mine|theirs)\}\s*$")


@pytest.mark.parametrize("line", [
    "- [ ] @alex-rivera send roadmap (due 2020-01-01) {theirs}",
    "- [x] @alex-rivera old item {mine}",
    "  - [ ] @me book the room {mine}",
    "- [ ] @me x (due 2026-01-01) later {mine}",
    "- [ ] @me check (due 2026-01-01){mine}  ",
    "- [ ] @me {mine}",
    "- [ ] @me no owner",
])
def test_old_lines_parse_exactly_as_before(line):
    old, new = OLD_RE.match(line), C.parse_task(line)
    assert bool(old) == bool(new)
    if old:
        assert (new["person"], new["text"], new["due"], new["owner"], new["closed"]) == \
               (old.group("person"), old.group("text").strip(), old.group("due") or "", old.group("owner"),
                old.group("done") != " ")


def test_new_grammar_parts_any_order():
    t = C.parse_task("- [x] @alex-rivera ship it (added 2026-10-01) (done 2026-10-20) (due 2026-10-09) {theirs} {doing}")
    assert t["text"] == "ship it" and t["due"] == "2026-10-09" and t["added"] == "2026-10-01"
    assert t["done"] == "2026-10-20" and t["doing"] and t["closed"] and t["owner"] == "theirs"
    t = C.parse_task("- [ ] @me x {doing} {mine}")   # {doing} counts only after the owner
    assert t["text"] == "x {doing}" and not t["doing"]


def test_build_accepts_new_grammar_without_warnings(env):
    s = seed(env, "- [ ] @me plan (due 2026-11-02) (added 2026-10-20) {mine} {doing}\n"
                  "- [x] @alex-rivera sent (done 2026-10-27) {theirs}\n")
    r = run(env, "build")
    assert r.returncode == 0, r.stdout
    assert "standard shape" not in r.stdout
    items = C.followups(*[C.load_all(env["vault"])[0]], me={"me"})
    plan = [i for i in items if i["text"] == "plan"][0]
    assert plan["doing"] and plan["added"] == "2026-10-20"
    assert s.read_text().splitlines()[plan["line"] - 1] == plan["raw"]


def test_card_points_overdue_to_board(env):
    seed(env, "- [ ] @me late thing (due 2020-01-01) {mine}\n")
    assert run(env, "build").returncode == 0
    assert "1 overdue - say 'show my board' to open them." in (env["vault"] / "_cortex/card.md").read_text()


def test_columns_and_precedence(env, srv):
    seed(env, "- [ ] @me late (due 2026-10-01) {mine}\n"
              "- [ ] @me soon (due 2026-11-03) {mine}\n"
              "- [ ] @me someday {mine}\n"
              "- [ ] @me busy (due 2026-10-01) {mine} {doing}\n"
              "- [ ] @alex-rivera owes (due 2026-10-01) {theirs}\n"
              "- [x] @me finished (due 2026-10-01) (done 2026-10-27) {mine} {doing}\n"
              "- [x] @me long ago (done 2026-09-01) {mine}\n")
    cols = {i["text"]: i["column"] for i in state(srv)["items"]}
    assert cols == {"late": "overdue", "soon": "week", "someday": "later", "busy": "doing",
                    "owes": "waiting", "finished": "done"}


# ---------------------------------------------------------------- moves

def lines_of(path):
    return path.read_text().splitlines()


def test_every_move(env, srv):
    s = seed(env, "- [ ] @me plan the day (added 2026-10-20) {mine}\n"
                  "- [ ] @alex-rivera send deck (due 2026-10-01) {theirs}\n"
                  "- [ ] @alex-rivera call back {mine}\n")
    it = item(state(srv), "plan the day")
    assert move(srv, it, "week")[0] == 200
    assert "- [ ] @me plan the day (added 2026-10-20) (due 2026-10-30) {mine}" in lines_of(s)
    assert move(srv, item(state(srv), "plan the day"), "doing")[0] == 200
    assert "- [ ] @me plan the day (added 2026-10-20) (due 2026-10-30) {mine} {doing}" in lines_of(s)
    assert move(srv, item(state(srv), "plan the day"), "later")[0] == 200
    assert "- [ ] @me plan the day (added 2026-10-20) {mine}" in lines_of(s)
    assert move(srv, item(state(srv), "plan the day"), "done")[0] == 200
    assert "- [x] @me plan the day (added 2026-10-20) (done 2026-10-28) {mine}" in lines_of(s)
    assert move(srv, item(state(srv), "plan the day"), "later")[0] == 200  # out of Done reopens
    assert "- [ ] @me plan the day (added 2026-10-20) {mine}" in lines_of(s)
    code, r, _ = move(srv, item(state(srv), "plan the day"), "waiting")
    assert code == 400 and "Who is it waiting on?" in r["message"]
    code, r, _ = move(srv, item(state(srv), "plan the day"), "overdue")
    assert code == 400 and "comes from the date" in r["message"]
    # every move but Waiting keeps the owner: "Alex owes me" never becomes "I owe Alex"
    for to in ("week", "later", "doing"):
        code, r, _ = move(srv, item(state(srv), "send deck"), to)
        assert code == 200 and "{theirs}" in [l for l in lines_of(s) if "send deck" in l][0], to
    assert "- [ ] @alex-rivera send deck {theirs} {doing}" in lines_of(s)
    code, r, _ = move(srv, item(state(srv), "send deck"), "week")
    assert "- [ ] @alex-rivera send deck (due 2026-10-30) {theirs}" in lines_of(s)
    assert r["note"] and "Waiting on others" in r["message"] and "owes it" in r["message"]
    assert move(srv, item(state(srv), "call back"), "waiting")[0] == 200
    assert "- [ ] @alex-rivera call back {theirs}" in lines_of(s)
    # the generated files follow every write
    assert "call back" in (env["vault"] / "_cortex/followups.md").read_text()


@pytest.mark.parametrize("today,friday", [(dt.date(2026, 10, 31), "2026-11-06"), (dt.date(2026, 11, 1), "2026-11-06"),
                                          (dt.date(2026, 10, 30), "2026-10-30"), (dt.date(2026, 10, 26), "2026-10-30")])
def test_this_friday(today, friday):
    assert B.this_friday(today).isoformat() == friday


def test_crlf_and_indent_kept(env, srv):
    s = seed(env, "  - [ ] @me tidy up {mine}  \n- [ ] @me other {mine}\n", newline="\r\n")
    before = s.read_bytes()
    assert move(srv, item(state(srv), "tidy up"), "doing")[0] == 200
    after = s.read_bytes()
    assert b"  - [ ] @me tidy up {mine} {doing}  \r\n" in after
    assert after.count(b"\r\n") == before.count(b"\r\n") and b"\n" not in after.replace(b"\r\n", b"")
    assert after.replace(b" {doing}", b"", 1) == before


def test_duplicate_lines_use_occurrence_then_refuse(env, srv):
    s = seed(env, "- [ ] @me send it {mine}\n- [ ] @me send it {mine}\n")
    items = [i for i in state(srv)["items"] if i["text"] == "send it"]
    assert len(items) == 2 and items[0]["id"] != items[1]["id"]
    second = sorted(items, key=lambda i: i["line_no"])[1]
    assert move(srv, second, "doing")[0] == 200
    assert lines_of(s)[-2:] == ["- [ ] @me send it {mine}", "- [ ] @me send it {mine} {doing}"]
    s.write_text(s.read_text() + "- [ ] @me send it {mine}\n")   # page changes: now two identical lines again
    code, r, _ = move(srv, sorted(items, key=lambda i: i["line_no"])[0], "week")
    assert code == 409 and "changed" in r["message"]


def test_page_changed_between_load_and_drop(env, srv):
    s = seed(env, "- [ ] @me write notes {mine}\n- [ ] @me other {mine}\n")
    it = item(state(srv), "write notes")
    s.write_text(s.read_text().replace("## Follow-ups\n", "## Follow-ups\n\n- [ ] @me inserted above {mine}\n"))
    assert move(srv, it, "doing")[0] == 200          # the exact line is still there once: edited in place
    assert "- [ ] @me write notes {mine} {doing}" in lines_of(s)
    other = item(state(srv), "other")
    s.write_text(s.read_text().replace("@me other {mine}", "@me other, reworded {mine}"))
    code, r, _ = move(srv, other, "done")
    assert code == 409 and "reloaded" in r["message"]
    assert "@me other, reworded {mine}" in s.read_text()


def test_validation_failure_rolls_back(env, srv, monkeypatch):
    s = seed(env, "- [ ] @me risky {mine}\n")
    it = item(state(srv), "risky")
    before = s.read_bytes()
    calls = iter([[], [f"{it['page']}: line 9: something broke"]])
    monkeypatch.setattr(B.Board, "_page_errors", lambda self, rel: next(calls))
    code, r, _ = move(srv, it, "done")
    assert code == 422 and "not saved" in r["message"] and "something broke" in r["message"]
    assert s.read_bytes() == before


def test_undo_restores_and_refuses_after_outside_edit(env, srv):
    s = seed(env, "- [ ] @me undo me {mine}\n")
    before = s.read_bytes()
    assert move(srv, item(state(srv), "undo me"), "done")[0] == 200
    assert not (env["vault"] / "_cortex/trash").exists()          # never in the vault (backup)
    assert len(list(B.trash_dir(env["vault"]).iterdir())) == 1
    code, r, _ = call(srv, "POST", "/api/undo")
    assert code == 200 and s.read_bytes() == before
    assert call(srv, "POST", "/api/undo")[0] == 400        # nothing left to undo
    assert move(srv, item(state(srv), "undo me"), "done")[0] == 200
    s.write_text(s.read_text() + "\nedited in Obsidian\n")
    code, r, _ = call(srv, "POST", "/api/undo")
    assert code == 409 and "edited in Obsidian" in s.read_text()


# ---------------------------------------------------------------- security

def test_token_host_origin(env, srv):
    seed(env, "- [ ] @me x {mine}\n")
    assert call(srv, "GET", "/api/state", token=False)[0] == 403
    assert call(srv, "GET", "/api/state", token="wrong")[0] == 403
    assert call(srv, "GET", "/api/state", host="evil.example")[0] == 403
    assert call(srv, "GET", "/api/state", host=f"evil.example:{srv.port}")[0] == 403    # DNS rebinding
    assert call(srv, "GET", "/api/state", host=f"localhost:{srv.port}")[0] == 200
    it = item(state(srv), "x")
    body = {"id": it["id"], "sha": it["sha"], "to": "done"}
    assert call(srv, "POST", "/api/move", body, origin="http://evil.example")[0] == 403
    assert call(srv, "POST", "/api/move", body, origin="null")[0] == 403
    assert call(srv, "POST", "/api/move", body, origin=False)[0] == 403
    assert call(srv, "POST", "/api/move", body, ctype="text/plain")[0] == 415      # no-cors form posts
    code, page, hdrs = call(srv, "GET", f"/?t={srv.token}", token=False)
    assert code == 200 and "<title>Cortex board</title>" in page
    cookie = hdrs["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert "nonce-" in hdrs["Content-Security-Policy"] and "Access-Control-Allow-Origin" not in hdrs


def test_page_never_puts_vault_text_in_html():
    html = (SCRIPTS / "board.html").read_text()
    assert "innerHTML" not in html and "outerHTML" not in html and "insertAdjacentHTML" not in html
    assert "http://" not in html and "https://" not in html      # no CDN, nothing loaded from outside


def test_ids_never_paths(env, srv):
    seed(env, "- [ ] @me x {mine}\n")
    for bad in ("../../etc/passwd", "/etc/passwd", "acme/projects/pilot-project/_index.md", ""):
        assert call(srv, "POST", "/api/move", {"id": bad, "sha": "", "to": "done"})[0] == 404
        assert call(srv, "POST", "/api/open", {"id": bad, "how": "file"})[0] == 404
        assert call(srv, "GET", "/api/item?id=" + urllib.parse.quote(bad))[0] == 404
    assert call(srv, "GET", "/../../etc/passwd")[0] == 404


def test_symlink_out_of_vault_refused(env, srv, tmp_path):
    s = seed(env, "- [ ] @me guarded {mine}\n")
    it = item(state(srv), "guarded")
    outside = tmp_path / "outside.md"
    outside.write_bytes(s.read_bytes())
    s.unlink()
    s.symlink_to(outside)
    code, r, _ = move(srv, it, "done")
    assert code == 403 and "outside your cortex" in r["message"]
    assert "[x]" not in outside.read_text()
    st = state(srv)
    assert not [i for i in st["items"] if i["text"] == "guarded"]
    assert any("outside your cortex" in p for p in st["problems"])


# ---------------------------------------------------------------- Ask Claude

def test_prompt_encoding_round_trip(env, srv):
    text = "pay 50% & fix #3 ❤️ now"
    seed(env, f"- [ ] @me {text} {{mine}}\n")
    it = item(state(srv), text)
    code, r, _ = call(srv, "POST", "/api/open", {"id": it["id"], "how": "claude"})
    assert code == 200 and r["ok"]
    url = srv.opened[-1]
    assert url.startswith("claude://code/new?q=")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert q["q"][0] == it["prompt"] and text in it["prompt"] and "\n" in it["prompt"]
    assert q["folder"][0] == str(env["vault"].resolve())
    for how in ("file", "obsidian"):
        assert call(srv, "POST", "/api/open", {"id": it["id"], "how": how})[0] == 200
    assert srv.opened[-2].endswith(it["page"]) and srv.opened[-2].startswith("/")
    assert srv.opened[-1].startswith("obsidian://open?path=%2F")


def test_prompt_length_bound():
    vault = Path("/Users/alex/my cortex")
    t = {"raw": "- [ ] @me " + "a%&#\u2764" * 6000, "due": "", "owner": "mine", "person": "me"}
    p = B.task_prompt(t, "T%" * 5000, "x/%" * 3000, vault)
    link = B.encoded_link(p, vault)
    assert len(p) <= B.PROMPT_LIMIT and len(link) <= B.URL_LIMIT and p.endswith(B.TASK_ASK)
    assert '..." (from ' in p                                           # the task line shortened, marked
    # escape-heavy text: the encoded link is the binding limit, and the instruction is still whole
    t["raw"] = "%" * 20000
    p = B.task_prompt(t, "Title", "a/b.md", vault)
    assert len(B.encoded_link(p, vault)) <= B.URL_LIMIT and p.endswith(B.TASK_ASK) and "(from Title, a/b.md;" in p
    t["raw"] = "short line"
    assert B.task_prompt(t, "Title", "a/b.md", vault) == (
        'About this item in my cortex: "short line" (from Title, a/b.md; due no date; mine @me).\n' + B.where(vault) + B.TASK_ASK)
    ip = B.inbox_prompt("inbox/" + "%" * 20000 + ".md", "T", vault)
    assert ip.endswith(B.INBOX_ASK) and len(B.encoded_link(ip, vault)) <= B.URL_LIMIT
    for text in ("%" * 20000, "a" * 20000, "\u2764\ufe0f&#\n" * 3000, "ok"):
        link = B.claude_link(text, Path("/Users/alex/my cortex"))
        assert len(link) <= B.URL_LIMIT
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)
        assert text.startswith(q["q"][0]) and q["folder"][0] == "/Users/alex/my cortex"
        assert not re.search(r"%(?![0-9A-F]{2})", link.split("?", 1)[1])     # no half escape anywhere
    assert len(B.claude_link("%" * 20000, Path("/v"))) > B.URL_LIMIT - 3       # fills the room it has
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(B.claude_link("a" * 20000, Path("/v"))).query)
    assert q["q"][0] == "a" * B.PROMPT_LIMIT


# ---------------------------------------------------------------- inbox and failed reads

def test_inbox_lists_loose_unsaved_desk_and_notes(env, srv):
    seed(env, "- [ ] @me x {mine}\n")
    v = env["vault"]
    (v / "acme" / "scribble.md").write_text("thoughts\n- [ ] @me call the bank {mine}\n- [ ] @me two {mine}\n")
    make(env, "note", "--title", "Old OneNote page")
    (v / "_cortex").mkdir(exist_ok=True)
    (v / "_cortex/sorting-desk.md").write_text(
        "| # | Inbox file | Title | Area | Thing | Type | Tags | Links | Confidence | Why |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 1 | inbox/old-onenote-page.md | Old plan | acme | pilot-project | note | a | - | medium | <b>Mentions</b> |\n")
    ib = state(srv)["inbox"]
    assert [(r["rel"], r["tasks"]) for r in ib["loose"]] == [("acme/scribble.md", 2)]
    assert [r["rel"] for r in ib["notes"]] == ["inbox/old-onenote-page.md"]
    assert ib["desk"][0]["title"] == "Old plan" and ib["desk"][0]["why"] == "<b>Mentions</b>"
    assert "acme/scribble.md" in {r["rel"] for r in ib["unsaved"]}
    code, r, _ = call(srv, "POST", "/api/open", {"id": ib["loose"][0]["id"], "how": "claude"})
    assert code == 200 and "help" in urllib.parse.unquote(srv.opened[-1]).lower()
    subprocess.run(["git", "-C", str(v), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(v), "commit", "-qm", "x"], check=True)
    assert state(srv)["inbox"]["unsaved"] == []


def test_inbox_without_git_and_empty(env, srv):
    seed(env, "- [ ] @me x {mine}\n")
    import shutil
    shutil.rmtree(env["vault"] / ".git")
    ib = state(srv)["inbox"]
    assert ib["git"] is False and not any(ib[k] for k in ("desk", "notes", "loose", "unsaved"))


def test_failed_read_says_so(env, srv):
    s = seed(env, "- [ ] @me x {mine}\n")
    s.chmod(0)
    try:
        st = state(srv)
        assert any(p.startswith("could not read " + s.relative_to(env["vault"]).as_posix()) for p in st["problems"])
    finally:
        s.chmod(0o644)
    bad = B.Board(env["vault"] / "gone")
    st = bad.state()
    assert st["ok"] is False and "could not read your cortex folder" in st["problems"][0]


def test_bad_config_gives_plain_message(env):
    (env["home"] / ".cortex" / "config.json").write_text("{not json")
    r = run(env, "board", "--no-browser")
    assert r.returncode != 0 and "not set up yet" in (r.stdout + r.stderr)


# ---------------------------------------------------------------- the real command

def test_command_starts_reuses_and_serves(env):
    seed(env, "- [ ] @me ship the board {mine}\n")
    p = subprocess.Popen([sys.executable, str(CORTEX), "board", "--no-browser"], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=env["env"])
    try:
        url = ""
        for _ in range(2):
            line = p.stdout.readline()
            m = re.search(r"http://127\.0\.0\.1:\d+/\?t=\S+", line)
            url = m.group(0) if m else url
        assert url, p.stderr.read() if p.poll() is not None else "no url"
        info = json.loads((env["home"] / ".cortex" / "board.json").read_text())
        assert info["pid"] == p.pid and oct((env["home"] / ".cortex" / "board.json").stat().st_mode)[-3:] == "600"
        with urllib.request.urlopen(url, timeout=10) as r:
            cookie = r.headers["Set-Cookie"].split(";")[0]
            assert "Your board" in r.read().decode()
        base = url.split("/?")[0]
        req = urllib.request.Request(base + "/api/state", headers={"Cookie": cookie})
        with urllib.request.urlopen(req, timeout=10) as r:
            assert "ship the board" in [i["text"] for i in json.loads(r.read())["items"]]
        again = run(env, "board", "--no-browser")
        assert again.returncode == 0 and "already open" in again.stdout
    finally:
        p.terminate()
        p.wait(timeout=10)
    assert not (env["home"] / ".cortex" / "board.json").exists()


def test_idle_server_exits(env):
    seed(env, "- [ ] @me x {mine}\n")
    server = B.start_in_thread(B.Board(env["vault"]), idle=0.3)
    time.sleep(1.5)
    with pytest.raises(Exception):
        call(server, "GET", "/api/state")
    server.server_close()


# ---------------------------------------------------------------- breaker findings (0.4.0)

def test_later_keeps_a_far_date(env, srv):
    s = seed(env, "- [ ] @me far off (due 2026-12-15) {mine}\n- [ ] @me near (due 2026-11-02) {mine} {doing}\n")
    assert move(srv, item(state(srv), "far off"), "doing")[0] == 200
    assert move(srv, item(state(srv), "far off"), "later")[0] == 200
    assert "- [ ] @me far off (due 2026-12-15) {mine}" in lines_of(s)
    assert move(srv, item(state(srv), "near"), "later")[0] == 200
    assert "- [ ] @me near {mine}" in lines_of(s)


def test_append_during_move_is_never_lost(env, srv, monkeypatch):
    s = seed(env, "- [ ] @me race {mine}\n")
    it = item(state(srv), "race")
    real_errors = B.Board._page_errors

    def append_then_check(self, rel):     # another process appends while the board checks the page
        with open(s, "a") as fh:
            fh.write("- [ ] @me appended elsewhere {mine}\n")
        return real_errors(self, rel)
    monkeypatch.setattr(B.Board, "_page_errors", append_then_check)
    code, r, _ = move(srv, it, "done")
    assert code == 409 and "Nothing was changed" in r["message"]
    assert "appended elsewhere" in s.read_text() and "- [ ] @me race {mine}" in lines_of(s)


def test_rollback_refuses_when_page_changed_meanwhile(env, srv, monkeypatch):
    s = seed(env, "- [ ] @me risky {mine}\n")
    it = item(state(srv), "risky")
    calls = {"n": 0}

    def errors(self, rel):
        calls["n"] += 1
        if calls["n"] == 2:                # after the board's write: someone else edits, and the check fails
            s.write_text(s.read_text() + "\nnewer edit\n")
            return [f"{rel}: boom"]
        return []
    monkeypatch.setattr(B.Board, "_page_errors", errors)
    code, r, _ = move(srv, it, "done")
    assert code == 409 and "newer edit" in s.read_text()


def test_unique_temp_files_and_mode_kept(env, tmp_path):
    d = tmp_path / "gen"
    d.mkdir()
    f = d / "card.md"
    f.write_text("x")
    f.chmod(0o640)
    import threading
    threads = [threading.Thread(target=C.write_atomic, args=(f, f"writer {n}\n" * 2000)) for n in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert f.read_text().startswith("writer ") and oct(f.stat().st_mode)[-3:] == "640"
    assert [p.name for p in d.iterdir()] == ["card.md"]       # no temp left behind


def test_rebuild_failure_is_a_note_not_an_error(env, srv, monkeypatch):
    s = seed(env, "- [ ] @me keep going {mine}\n")
    monkeypatch.setattr(C, "build_outputs", lambda v: (_ for _ in ()).throw(OSError("disk full")))
    code, r, _ = move(srv, item(state(srv), "keep going"), "done")
    assert code == 200 and r["note"] and "catch up at the next build" in r["message"]
    assert "[x] @me keep going" in s.read_text()


def test_trash_keeps_last_20(env, srv):
    seed(env, "- [ ] @me flip {mine}\n")
    for n in range(23):
        assert move(srv, item(state(srv), "flip"), "doing" if n % 2 == 0 else "later")[0] == 200
    assert len(list(B.trash_dir(env["vault"]).iterdir())) == 20
    assert "_cortex/trash/" not in (SCRIPTS.parent / "templates/vault/gitignore").read_text()


def test_read_only_page_refused(env, srv):
    s = seed(env, "- [ ] @me locked {mine}\n")
    before = s.read_bytes()
    s.chmod(0o444)
    try:
        code, r, _ = move(srv, item(state(srv), "locked"), "done")
        assert code == 403 and "read-only" in r["message"] and s.read_bytes() == before
    finally:
        s.chmod(0o644)


def test_unsaved_names_with_spaces_unicode_and_renames(env, srv):
    seed(env, "- [ ] @me x {mine}\n")
    v = env["vault"]
    subprocess.run(["git", "-C", str(v), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(v), "commit", "-qm", "x"], check=True)
    (v / "acme" / "caf\u00e9 notes.md").write_text("hello\n")
    subprocess.run(["git", "-C", str(v), "mv", "people/alex-rivera.md", "people/alex r\u00e9.md"], check=True)
    rels = {r["rel"] for r in state(srv)["inbox"]["unsaved"]}
    assert rels == {"acme/caf\u00e9 notes.md", "people/alex r\u00e9.md"}


def test_fenced_and_header_lines_are_not_tasks(env, srv):
    s = seed(env, "```\n- [ ] @me inside a fence {mine}\n```\n~~~~\n- [ ] @nobody also fenced {mine}\n~~~~\n"
                  "- [ ] @me real one {mine}\n- [ ] @me inside a fence {mine}\n")
    texts = sorted(i["text"] for i in state(srv)["items"])
    assert texts == ["inside a fence", "real one"]
    r = run(env, "build")
    assert r.returncode == 0, r.stdout          # @nobody inside a fence is not checked
    fu = (env["vault"] / "_cortex/followups.md").read_text()
    assert fu.count("inside a fence") == 1 and "also fenced" not in fu
    # the one real 'inside a fence' line is unique among task lines, so a changed page still finds it
    it = item(state(srv), "inside a fence")
    s.write_text(s.read_text() + "\n")
    assert move(srv, it, "doing")[0] == 200
    assert "```\n- [ ] @me inside a fence {mine}\n```" in s.read_text()
    assert "- [ ] @me inside a fence {mine} {doing}" in lines_of(s)


def test_validate_and_followups_agree_on_line_separators(env):
    s = seed(env, "- [ ] @me one\u2028two {mine}\n")
    r = run(env, "build")
    assert r.returncode == 0 and "standard shape" not in r.stdout
    items = C.followups(C.load_all(env["vault"])[0])
    assert [i["text"] for i in items] == ["one\u2028two"]


def test_move_returns_new_id_for_focus(env, srv):
    seed(env, "- [ ] @me focus me {mine}\n")
    code, r, _ = move(srv, item(state(srv), "focus me"), "doing")
    assert code == 200 and r["id"] == item(state(srv), "focus me")["id"]


def test_slow_body_does_not_hold_the_server(env, srv):
    import socket
    sock = socket.create_connection(("127.0.0.1", srv.port))
    sock.sendall((f"POST /api/move HTTP/1.1\r\nHost: 127.0.0.1:{srv.port}\r\nCookie: {srv.cookie}={srv.token}\r\n"
                  f"Origin: http://127.0.0.1:{srv.port}\r\nContent-Type: application/json\r\n"
                  "Content-Length: 500\r\n\r\n{").encode())
    assert B.Handler.timeout == 10
    assert call(srv, "GET", "/api/ping")[0] == 200      # other requests are still served
    sock.close()


def test_stop_closes_the_board(env):
    seed(env, "- [ ] @me x {mine}\n")
    p = subprocess.Popen([sys.executable, str(CORTEX), "board", "--no-browser"], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=env["env"])
    try:
        p.stdout.readline()
        r = run(env, "board", "--stop")
        assert r.returncode == 0 and "Board closed" in r.stdout
        assert p.wait(timeout=10) == 0
        assert "No board is open" in run(env, "board", "--stop").stdout
    finally:
        if p.poll() is None:
            p.kill()


# ---------------------------------------------------------------- re-check findings (0.4.0)

@pytest.mark.parametrize("body,seen", [
    ("```py`x\n- [ ] @me after fake fence {mine}\n", ["after fake fence"]),          # backtick in info: not a fence
    ("    ```\n- [ ] @me after indented code {mine}\n", ["after indented code"]),   # 4+ spaces: code, not a fence
    ("- [ ] @me item {mine}\n    ```\n    - [ ] @me in list fence {mine}\n    ```\n- [ ] @me after {mine}\n",
     ["item", "after"]),                                                             # a fence inside a list item
    ("~~~\n- [ ] @me hidden {mine}\n~~~ not a closer\n~~~\n- [ ] @me shown {mine}\n", ["shown"]),
])
def test_fence_rules(env, srv, body, seen):
    seed(env, body)
    assert sorted(i["text"] for i in state(srv)["items"]) == sorted(seen)
    fu = (env["vault"] / "_cortex/followups.md")
    assert run(env, "build").returncode == 0
    assert sorted(t for t in seen if t in fu.read_text()) == sorted(seen)


def test_unclosed_fence_warns_and_shows(env, srv):
    s = seed(env, "- [ ] @me before {mine}\n```\n- [ ] @me swallowed {mine}\n")
    n = lines_of(s).index("```") + 1
    r = run(env, "build")
    msg = f"code block opened on line {n} is never closed - task lines below it are not counted"
    assert r.returncode == 0 and msg in r.stdout
    st = state(srv)
    assert [i["text"] for i in st["items"]] == ["before"] and any(msg in p for p in st["problems"])
    s.write_text(s.read_text().replace("- [ ] @me swallowed {mine}\n", "no tasks here\n"))
    assert "never closed" not in run(env, "build").stdout          # nothing hidden, nothing to say


def test_lone_cr_line_endings_match_the_build(env, srv):
    s = seed(env, "- [ ] @me first {mine}\n- [ ] @me second {mine}\n", newline="\r")
    before = s.read_bytes()
    st = state(srv)
    items = C.followups(C.load_all(env["vault"])[0])
    assert sorted((i["text"], i["line"]) for i in items) == sorted((i["text"], i["line_no"]) for i in st["items"])
    assert move(srv, item(st, "second"), "doing")[0] == 200
    after = s.read_bytes()
    assert b"\n" not in after and after == before.replace(b"@me second {mine}", b"@me second {mine} {doing}")


def test_skill_table_renders():
    text = (SCRIPTS.parent / "skills/board/SKILL.md").read_text()
    table = re.search(r"\| Moved to .*?\n\n", text, re.S).group(0)
    assert all(l.startswith("|") for l in table.strip().splitlines()) and "| Done |" in table


def test_stop_works_without_the_vault_folder(env):
    seed(env, "- [ ] @me x {mine}\n")
    p = subprocess.Popen([sys.executable, str(CORTEX), "board", "--no-browser"], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=env["env"])
    try:
        p.stdout.readline()
        (env["home"] / ".cortex" / "config.json").write_text(json.dumps({"vault": str(env["home"] / "gone")}))
        r = run(env, "board", "--stop")
        assert r.returncode == 0 and "Board closed" in r.stdout
        assert p.wait(timeout=10) == 0
    finally:
        if p.poll() is None:
            p.kill()


def test_busy_message_prints_the_exact_command(env, tmp_path):
    seed(env, "- [ ] @me x {mine}\n")
    other = tmp_path / "other vault"
    other.mkdir()
    p = subprocess.Popen([sys.executable, str(CORTEX), "--vault", str(other), "board", "--no-browser"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env["env"])
    try:
        p.stdout.readline()
        r = run(env, "board", "--no-browser")
        assert r.returncode == 1 and "different cortex folder" in r.stdout
        cmd = r.stdout.splitlines()[1].strip()
        assert "--vault" in cmd and cmd.endswith("board --stop")
        import shlex
        done = subprocess.run(shlex.split(cmd), capture_output=True, text=True, env=env["env"])
        assert "Board closed" in done.stdout and p.wait(timeout=10) == 0
    finally:
        if p.poll() is None:
            p.kill()


def test_theme_saved_outside_the_vault_and_put_on_the_page(env, srv):
    assert '<html lang="en" data-choice="system">' in call(srv, "GET", "/")[1]
    assert call(srv, "POST", "/api/theme", {"theme": "night"})[0] == 200
    assert (env["home"] / ".cortex" / "board-theme").read_text() == "night"
    code, page, hdrs = call(srv, "GET", "/")
    assert '<html lang="en" data-choice="night">' in page and "font-src 'self'" in hdrs["Content-Security-Policy"]
    assert call(srv, "POST", "/api/theme", {"theme": "system"})[0] == 200
    assert not (env["home"] / ".cortex" / "board-theme").exists()
    assert call(srv, "POST", "/api/theme", {"theme": '"><script>'})[0] == 400


def test_theme_bad_file_falls_back_and_font_is_served_with_the_key_only(env, srv):
    (env["home"] / ".cortex" / "board-theme").write_text('"><script>alert(1)</script>')
    assert 'data-choice="system"' in call(srv, "GET", "/")[1]
    req = urllib.request.Request(f"http://127.0.0.1:{srv.port}/geist.woff2", headers={"Cookie": f"{srv.cookie}={srv.token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 200 and r.read(4) == b"wOF2"
    assert call(srv, "GET", "/geist.woff2", token=False)[0] == 403


def test_ask_claude_prompt_names_the_folder():
    vault = Path("/Users/alex/my cortex")
    t = {"raw": "- [ ] @me call", "due": "", "owner": "mine", "person": "me"}
    for p in (B.task_prompt(t, "Title", "a/b.md", vault), B.inbox_prompt("inbox/n.md", "N", vault),
              B.task_prompt(dict(t, raw="%" * 20000), "T%" * 5000, "x/%" * 3000, vault)):
        assert "My cortex is the folder /Users/alex/my cortex" in p


def test_engine_copy_has_the_version_file(tmp_path, monkeypatch):
    import hooks as H
    monkeypatch.setattr(H, "ENGINE", tmp_path / "engine")
    H.sync_engine()
    assert json.loads((tmp_path / "engine/.claude-plugin/plugin.json").read_text())["version"]
    assert (tmp_path / "engine/scripts/geist.woff2").exists()
