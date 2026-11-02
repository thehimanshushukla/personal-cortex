'use strict';
// Reads a cortex folder: finds it, parses pages, finds task lines, hides private parts.
// The parsing follows plugins/cortex/scripts/cortex.py line for line, because both must agree.
const fs = require('fs');
const os = require('os');
const path = require('path');

const GENERATED = '_cortex';
const SKIP_DIRS = new Set(['.git', '.claude', GENERATED, 'sources', '_templates', 'node_modules']);
const NOT_PAGES_ANYWHERE = new Set(['CLAUDE.md', 'README.md']);
const NOT_PAGES_AT_ROOT = new Set(['AGENTS.md', 'GEMINI.md', 'home.md']);
const REQUIRED = ['id', 'title', 'type', 'status', 'created', 'updated', 'summary'];
const MAX_FILE_BYTES = 2 * 1024 * 1024; // a page bigger than this is not read
const PY_LINE_BREAKS = /\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/;
const HEADER_KEY_RE = /^(id|title|type|status|created|updated|summary|area|tags|links):\s/;
const ANY_KEY_RE = /^[\p{L}_][\p{L}\p{N}_-]*:(\s|$)/u;
const FOLLOWUP_RE = /^(?<indent>\s*)-\s\[(?<done>[ xX])\]\s+@(?<person>[a-z0-9-]+)\s+(?<text>[^\n]*?)(?<meta>(?:\s*\((?:due|added|done)\s+\d{4}-\d{2}-\d{2}\))*)\s*\{(?<owner>mine|theirs)\}(?:\s*\{(?<doing>doing)\})?(?<trail>\s*)$/;
const META_RE = /\((due|added|done)\s+(\d{4}-\d{2}-\d{2})\)/g;
const FENCE_RE = /^(?<indent>[ \t]*)(?<fence>`{3,}|~{3,})(?<rest>[^\n]*)$/;
const LIST_ITEM_RE = /^[ \t]*(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)/;
const PRIVATE_TAG = /\{private\}/i;
const HEADING_RE = /^ {0,3}(#{1,6})[ \t]+(.*?)[ \t#]*$/;

// A refusal or problem to show the person in plain words. Anything else is a real bug.
class UserError extends Error {}

const cmp = (a, b) => Buffer.compare(Buffer.from(String(a)), Buffer.from(String(b))); // Python's string order

function localDate(d = new Date()) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function slugify(text) {
  const s = String(text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return s.slice(0, 70).replace(/^-+|-+$/g, '') || 'untitled';
}

// ---------------------------------------------------------------- finding the cortex

function expandHome(p) {
  const home = os.homedir();
  const out = p.replace(/\$\{HOME\}/g, home);
  return out === '~' || out.startsWith('~/') || out.startsWith('~\\') ? path.join(home, out.slice(1)) : out;
}

// Order: ~/.cortex/config.json if present and valid, else the folder set in the extension, else ~/cortex.
function vaultLocation() {
  try {
    const cfg = JSON.parse(fs.readFileSync(path.join(os.homedir(), '.cortex', 'config.json'), 'utf8'));
    const v = cfg && typeof cfg.vault === 'string' ? expandHome(cfg.vault.trim()) : '';
    if (v && path.isAbsolute(v)) return path.resolve(v);
  } catch (e) { /* missing or broken: fall through to the setting */ }
  const set = expandHome((process.env.CORTEX_FOLDER || '').trim());
  if (set && !set.includes('${') && path.isAbsolute(set)) return path.resolve(set);
  return path.join(os.homedir(), 'cortex');
}

// The real path of an existing cortex, or a plain refusal.
function requireVault() {
  const where = vaultLocation();
  let st;
  try {
    st = fs.statSync(where);
  } catch (e) {
    throw new UserError(`No Cortex found at ${where}. Say "set up my cortex" and one can be created there.`);
  }
  if (!st.isDirectory()) throw new UserError(`${where} is a file, not a folder, so it cannot hold a Cortex. Choose a folder in the extension's settings.`);
  const real = fs.realpathSync(where);
  if (!fs.existsSync(path.join(real, 'kit.yaml')) && !fs.existsSync(path.join(real, GENERATED))) {
    throw new UserError(`The folder ${where} has no Cortex in it. Say "set up my cortex" if it is empty, or choose your Cortex folder in the extension's settings.`);
  }
  return real;
}

function isInside(root, target) {
  const rel = path.relative(root, target);
  return rel === '' || (!rel.startsWith('..' + path.sep) && rel !== '..' && !path.isAbsolute(rel));
}

// ---------------------------------------------------------------- reading one page

function readText(abs) {
  const raw = fs.readFileSync(abs);
  return new TextDecoder('utf-8', { fatal: true }).decode(raw).replace(/\r\n?/g, '\n');
}

function parseValue(raw) {
  raw = raw.trim();
  if (raw.startsWith('[') && raw.endsWith(']')) {
    const inner = raw.slice(1, -1).trim();
    return inner ? inner.split(',').filter((v) => v.trim()).map((v) => v.trim().replace(/^['"]+|['"]+$/g, '')) : [];
  }
  if (raw.length >= 2 && raw[0] === raw[raw.length - 1] && (raw[0] === "'" || raw[0] === '"')) return raw.slice(1, -1);
  return raw;
}

function pyLines(text) {
  const lines = text.split(PY_LINE_BREAKS);
  if (lines[lines.length - 1] === '') lines.pop();
  return lines;
}

// Same decisions as read_page in cortex.py. Returns {rel, meta, body, errors, loose}.
function parsePage(rel, source) {
  let text = source.replace(/^\ufeff+/, '');
  const meta = Object.create(null);
  const head = pyLines(text).slice(0, 12).filter((l) => l.trim() && !l.trimStart().startsWith('#'));
  const afterRule = head.length && head[0].trim() === '---' ? head.slice(1, 4) : [];
  const opensHeader = afterRule.length > 0 && (HEADER_KEY_RE.test(afterRule[0])
    || afterRule.slice(0, 2).filter((l) => ANY_KEY_RE.test(l)).length === 2);
  if (opensHeader) text = text.trimStart();
  if (!text.startsWith('---\n') || !opensHeader) {
    let keys = 0;
    for (const l of head) {
      if (l.trim() === '---') break;
      if (HEADER_KEY_RE.test(l)) keys += 1;
    }
    if (keys >= 2 && head.some((l) => l.trim() === '---')) {
      return { rel, meta, body: text, errors: ['header is broken - it must start with a line of just ---'] };
    }
    return { rel, meta, body: text, errors: [], loose: true };
  }
  const end = text.indexOf('\n---', 4);
  if (end === -1) return { rel, meta, body: text, errors: ['frontmatter is not closed with ---'] };
  const errors = [];
  for (const line of pyLines(text.slice(4, end))) {
    if (!line.trim() || line.trimStart().startsWith('#')) continue;
    if (line[0] === ' ' || line[0] === '\t' || line[0] === '-') { errors.push('nested or list-style header line'); continue; }
    if (!line.includes(': ') && !line.trimEnd().endsWith(':')) { errors.push('header line is not key: value'); continue; }
    const at = line.indexOf(':');
    const key = line.slice(0, at).trim();
    if (key in meta) errors.push(`'${key}' appears twice`);
    meta[key] = parseValue(line.slice(at + 1));
  }
  return { rel, meta, body: text.slice(end + 4).replace(/^\n+/, ''), errors };
}

const get = (page, key) => (page.meta[key] === undefined ? '' : page.meta[key]);

// ---------------------------------------------------------------- private parts

function withoutPrivateLines(text) {
  const lines = text.split('\n');
  const kept = lines.filter((l) => !PRIVATE_TAG.test(l));
  return { text: kept.join('\n'), withheld: lines.length - kept.length };
}

// Removes every "## Private" section down to the next heading of the same or a higher level.
// A heading inside a code block in that section does not end it, so nothing below can leak.
function withoutPrivateSections(body) {
  const out = [];
  let level = 0;
  let fence = '';
  let withheld = 0;
  for (const line of body.split('\n')) {
    const h = HEADING_RE.exec(line);
    if (!level) {
      if (h && /^private\b/i.test(h[2])) {
        level = h[1].length;
        fence = '';
        withheld += 1;
      } else {
        out.push(line);
      }
      continue;
    }
    const f = FENCE_RE.exec(line);
    if (fence) {
      if (f && f.groups.fence[0] === fence[0] && f.groups.fence.length >= fence.length && !f.groups.rest.trim()) fence = '';
    } else if (f) {
      fence = f.groups.fence;
    } else if (h && h[1].length <= level) {
      if (/^private\b/i.test(h[2])) { level = h[1].length; withheld += 1; continue; }
      level = 0;
      out.push(line);
    }
  }
  return { text: out.join('\n'), withheld };
}

// The page with private parts removed first, so no tool can read, count or match on them.
function publicPage(rel, source) {
  const lines = withoutPrivateLines(source);
  const page = parsePage(rel, lines.text);
  const sections = withoutPrivateSections(page.body);
  page.body = sections.text;
  page.withheld = lines.withheld + sections.withheld;
  return page;
}

// ---------------------------------------------------------------- reading the whole cortex

// In os.walk order: a folder's files first, then its subfolders, sorted. Never follows a symlinked
// folder. A symlinked file is read only when it really lands inside the cortex.
function walk(vault) {
  const result = { pages: [], loose: [], skipped: [] };
  const visit = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => cmp(a.name, b.name));
    } catch (e) {
      result.skipped.push(path.relative(vault, dir) || '.');
      return;
    }
    const dirs = [];
    for (const entry of entries) {
      const abs = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(entry.name) && !entry.name.startsWith('.')) dirs.push(abs);
        continue;
      }
      if (!entry.name.endsWith('.md') || NOT_PAGES_ANYWHERE.has(entry.name)) continue;
      if (dir === vault && NOT_PAGES_AT_ROOT.has(entry.name)) continue;
      const rel = path.relative(vault, abs).split(path.sep).join('/');
      try {
        if (entry.isSymbolicLink()) {
          if (!isInside(vault, fs.realpathSync(abs)) || !fs.statSync(abs).isFile()) {
            result.skipped.push(rel);
            continue;
          }
        } else if (!entry.isFile()) {
          continue;
        }
        if (fs.statSync(abs).size > MAX_FILE_BYTES) { result.skipped.push(rel); continue; }
        const page = publicPage(rel, readText(abs));
        if (page.loose) result.loose.push(page);
        else if (page.errors.length || REQUIRED.some((k) => !page.meta[k] || !page.meta[k].length)) result.skipped.push(rel);
        else result.pages.push(page);
      } catch (e) {
        result.skipped.push(rel); // unreadable or not text: never stop the whole read
      }
    }
    dirs.forEach(visit);
  };
  visit(vault);
  return result;
}

function parseKit(vault) {
  const out = Object.create(null);
  try {
    for (const line of pyLines(readText(path.join(vault, 'kit.yaml')))) {
      if (line.includes(': ') && !/^[ #-]/.test(line)) {
        const at = line.indexOf(':');
        out[line.slice(0, at).trim()] = parseValue(line.slice(at + 1));
      }
    }
  } catch (e) { /* no kit.yaml */ }
  return out;
}

function selfSlugs(vault) {
  const name = parseKit(vault).name;
  return new Set(name ? ['me', slugify(name)] : ['me']);
}

// ---------------------------------------------------------------- task lines

function parseTask(line, me) {
  const m = FOLLOWUP_RE.exec(line);
  if (!m) return null;
  const dates = {};
  for (const d of m.groups.meta.matchAll(META_RE)) dates[d[1]] = d[2];
  return {
    person: m.groups.person, text: m.groups.text.trim(), owner: m.groups.owner, closed: m.groups.done !== ' ',
    due: dates.due || '', added: dates.added || '', done: dates.done || '', doing: Boolean(m.groups.doing),
    todo: me.has(m.groups.person) && m.groups.owner === 'mine',
  };
}

function expandedLength(s) {
  let col = 0;
  for (const ch of s) col = ch === '\t' ? col + 4 - (col % 4) : col + 1;
  return col;
}

// The lines that can hold a task: outside fenced code blocks, by the same rules as scan_body.
function taskCapableLines(lines) {
  const out = [];
  let fence = '';
  let inList = false;
  for (const line of lines) {
    const m = FENCE_RE.exec(line);
    if (fence) {
      if (m && m.groups.fence[0] === fence[0] && m.groups.fence.length >= fence.length && !m.groups.rest.trim()) fence = '';
      continue;
    }
    if (m && !(m.groups.fence[0] === '`' && m.groups.rest.includes('`')) && (expandedLength(m.groups.indent) < 4 || inList)) {
      fence = m.groups.fence;
      continue;
    }
    if (line.trim()) {
      if (LIST_ITEM_RE.test(line)) inList = true;
      else if (expandedLength(line) < 2) inList = false;
    }
    out.push(line);
  }
  return out;
}

function followups(pages, me) {
  const out = [];
  for (const page of pages) {
    for (const line of taskCapableLines(page.body.split('\n'))) {
      const t = parseTask(line, me);
      if (t && !t.closed) out.push(t);
    }
  }
  return out;
}

// ---------------------------------------------------------------- the inbox

// Regular .md files directly in inbox/. A symlink there is ignored.
function inboxFiles(vault) {
  let entries;
  try {
    const inbox = path.join(vault, 'inbox');
    if (!fs.lstatSync(inbox).isDirectory()) return [];
    entries = fs.readdirSync(inbox, { withFileTypes: true });
  } catch (e) {
    return [];
  }
  return entries.filter((e) => e.isFile() && e.name.endsWith('.md')).map((e) => e.name).sort(cmp);
}

const SECTIONS = ['Summary', 'Decisions', 'Follow-ups', 'Open questions'];

// A chat proposal, or null for any other note. It starts with plain 'source: chat' and
// 'status: proposed' lines and no --- rule, so the kit's build treats it as a loose note: nothing in
// it is validated or counted until cortex_accept files it.
function parseProposal(text) {
  const lines = text.split('\n');
  const first = lines.findIndex((l) => l.startsWith('## '));
  const top = (first === -1 ? lines : lines.slice(0, first));
  if (!top.includes('source: chat') || !top.includes('status: proposed')) return null;
  const field = (key) => {
    const line = top.find((l) => l.startsWith(`${key}: `));
    return line ? line.slice(key.length + 2).trim() : '';
  };
  const sections = Object.create(null);
  for (const name of SECTIONS) sections[name] = [];
  let current = null;
  for (const line of first === -1 ? [] : lines.slice(first)) {
    const name = line.startsWith('## ') ? line.slice(3).trim() : null;
    if (name !== null) current = sections[name] ? name : null;
    else if (current && line.trim()) sections[current].push(line);
  }
  return { name: field('name'), saved: field('saved'), sections };
}

module.exports = {
  UserError, GENERATED, MAX_FILE_BYTES, FOLLOWUP_RE, cmp, localDate, slugify, vaultLocation, requireVault, isInside,
  readText, publicPage, walk, get, parseKit, selfSlugs, parseTask, followups, inboxFiles, parseProposal,
};
