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
const MAX_TASK_LINE = 4000; // a longer line is never a task line, here and in cortex.py
const PY_LINE_BREAKS = /\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/;
const HEADER_KEY_RE = /^(id|title|type|status|created|updated|summary|area|tags|links):\s/;
const ANY_KEY_RE = /^[\p{L}_][\p{L}\p{N}_-]*:(\s|$)/u;
const TASK_HEAD_RE = /^\s*-\s\[([ xX])\]\s+@([a-z0-9-]+)\s+(?=\S)/;
const ONE_META_RE = /^\((?:due|added|done)\s+\d{4}-\d{2}-\d{2}\)$/;
const META_RE = /\((due|added|done)\s+(\d{4}-\d{2}-\d{2})\)/g;
const FENCE_RE = /^(?<indent>[ \t]*)(?<fence>`{3,}|~{3,})(?<rest>[^\n]*)$/;
const LIST_ITEM_RE = /^[ \t]*(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)/;
const PRIVATE_TAG = /\{\s*private\s*\}/i;
const HEADING_RE = /^ {0,3}(#{1,6})[ \t]+/;
const LOOSE_HEADING_RE = /^[ \t>]*(#{1,6})[ \t]*([^]*)/; // for finding a private heading: wider, on purpose
const HTML_HEADING_RE = /^\s*<h([1-6])\b[^>]*>([^]*)/i;
const SETEXT_RE = /^ {0,3}(=+|-+)[ \t]*$/;
const HEADING_TEXT_CHARS = 300;
const INVISIBLE = '\\u200b-\\u200d\\u2060\\ufeff';
const NOTES_TAG_RE = new RegExp(`<[\\s\\\\/${INVISIBLE}]*cortex[\\s_\\-${INVISIBLE}]*notes`, 'gi');

// A refusal or problem to show the person in plain words. Anything else is a real bug.
class UserError extends Error {}

const cmp = (a, b) => Buffer.compare(Buffer.from(String(a)), Buffer.from(String(b))); // Python's string order

function localDate(d = new Date()) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function bareSlug(text) {
  const s = String(text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return s.slice(0, 70).replace(/^-+|-+$/g, '');
}

const slugify = (text) => bareSlug(text) || 'untitled'; // the same as slugify in cortex.py

const LETTERS = { ß: 'ss', æ: 'ae', œ: 'oe', ø: 'o', đ: 'd', ð: 'd', þ: 'th', ł: 'l', ı: 'i', ħ: 'h', ŋ: 'ng' };

// "José Núñez" as plain Latin letters. Other scripts stay as they are.
function plainLetters(text) {
  return String(text).normalize('NFKD').replace(/\p{M}+/gu, '').toLowerCase().replace(/[ßæœøđðþłıħŋ]/g, (c) => LETTERS[c]);
}

// A slug the kit accepts, or '' when the text has nothing to make one from. Never 'untitled'.
const plainSlug = (text) => bareSlug(plainLetters(text));

// Text that repeats anything stored or supplied can never close the notes marker, however it is spelled.
const neutralise = (text) => String(text).replace(NOTES_TAG_RE, '<cortex-notes-text');

// ---------------------------------------------------------------- finding the cortex

function expandHome(p) {
  const home = os.homedir();
  const out = p.replace(/\$\{HOME\}/g, home);
  return out === '~' || out.startsWith('~/') || out.startsWith('~\\') ? path.join(home, out.slice(1)) : out;
}

// Order: ~/.cortex/config.json if present and valid, else the folder set in the extension, else ~/cortex.
// Returns the folder, and how it was chosen, so every message can say so.
function vaultSource() {
  const configFile = path.join(os.homedir(), '.cortex', 'config.json');
  const defaultFolder = path.join(os.homedir(), 'cortex');
  let fromConfig = '';
  try {
    const cfg = JSON.parse(fs.readFileSync(configFile, 'utf8'));
    const v = cfg && typeof cfg.vault === 'string' ? expandHome(cfg.vault.trim()) : '';
    if (v && path.isAbsolute(v)) fromConfig = path.resolve(v);
  } catch (e) { /* missing or broken: fall through to the setting */ }
  const set = expandHome((process.env.CORTEX_FOLDER || '').trim());
  const chosen = set && !set.includes('${') && path.isAbsolute(set) ? path.resolve(set) : '';
  return { where: fromConfig || chosen || defaultFolder, fromConfig, chosen, defaultFolder, configFile, configExists: fs.existsSync(configFile) };
}

const vaultLocation = () => vaultSource().where;

// In plain words, why this folder is the one in use.
function folderReason(src = vaultSource()) {
  if (src.fromConfig) {
    const other = src.chosen && src.chosen !== src.fromConfig && src.chosen !== src.defaultFolder;
    return other ? `set by ${src.configFile}, which wins over the extension's folder setting (${src.chosen})` : `set by ${src.configFile}`;
  }
  const broken = src.configExists ? `${src.configFile} could not be used, so it was ignored; ` : '';
  return `${broken}${src.chosen && src.chosen !== src.defaultFolder ? "from the extension's folder setting" : 'the default folder'}`;
}

function configPointsNowhere(src) {
  return `Your settings file ${src.configFile} says your Cortex is at ${src.where}, but that folder is not there. That file wins over the extension's folder setting, so no other folder was tried. Reconnect the drive that holds the folder, or change or remove that file.`;
}

// The real path of an existing cortex, or a plain refusal.
function requireVault() {
  const src = vaultSource();
  const { where } = src;
  let st;
  try {
    st = fs.statSync(where);
  } catch (e) {
    if (src.fromConfig) throw new UserError(configPointsNowhere(src));
    throw new UserError(`No Cortex found at ${where} (${folderReason(src)}). Say "set up my cortex" and one can be created there.`);
  }
  if (!st.isDirectory()) throw new UserError(`${where} is a file, not a folder, so it cannot hold a Cortex (${folderReason(src)}).`);
  const real = fs.realpathSync.native(where);
  if (!fs.existsSync(path.join(real, 'kit.yaml')) && !fs.existsSync(path.join(real, GENERATED))) {
    throw new UserError(`The folder ${where} has no Cortex in it (${folderReason(src)}). Say "set up my cortex" if it is empty, or point Cortex at the folder that holds your pages.`);
  }
  return real;
}

function isInside(root, target) {
  const rel = path.relative(root, target);
  return rel === '' || (!rel.startsWith('..' + path.sep) && rel !== '..' && !path.isAbsolute(rel));
}

// The files the kit generates repeat page text with nothing hidden: the list of follow-ups, the index,
// the card and the home page. They are never opened or searched here. Case does not matter, because
// on a Mac _CORTEX/FOLLOWUPS.md is the same file as _cortex/followups.md.
function isGenerated(rel) {
  const p = String(rel).replace(/\\/g, '/').replace(/^(\.?\/)+/, '').toLowerCase();
  return p === 'home.md' || p === GENERATED || p.startsWith(`${GENERATED}/`);
}

// ---------------------------------------------------------------- reading one page

function readText(abs) {
  if (fs.statSync(abs).size > MAX_FILE_BYTES) throw new UserError('That file is too large to read here.');
  const raw = fs.readFileSync(abs);
  return new TextDecoder('utf-8', { fatal: true }).decode(raw).replace(/\r\n?/g, '\n');
}

function stripQuotes(s) {
  let from = 0;
  let to = s.length;
  while (from < to && (s[from] === "'" || s[from] === '"')) from += 1;
  while (to > from && (s[to - 1] === "'" || s[to - 1] === '"')) to -= 1;
  return s.slice(from, to);
}

function parseValue(raw) {
  raw = raw.trim();
  if (raw.startsWith('[') && raw.endsWith(']')) {
    const inner = raw.slice(1, -1).trim();
    return inner ? inner.split(',').filter((v) => v.trim()).map((v) => stripQuotes(v.trim())) : [];
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

// True for Private, **Private**, _Private_, [Private], <b>Private</b>: and any heading tagged {private}.
function namesPrivate(title) {
  const t = title.slice(0, HEADING_TEXT_CHARS);
  if (PRIVATE_TAG.test(t)) return true;
  const plain = t.normalize('NFKC').replace(/<[^>]*>/g, ' ').replace(/[*~`\\_]/g, ' ').replace(/^[^\p{L}\p{N}]+/u, '');
  return /^private(?![\p{L}\p{N}])/i.test(plain);
}

function isHeading(line) {
  const m = HEADING_RE.exec(line);
  return m ? m[1].length : 0;
}

// If this line opens a private section: its level, and whether the next line is its underline.
// Finding one is wide on purpose: when in doubt, hide.
function privateHeading(line, next) {
  const head = line.slice(0, MAX_TASK_LINE);
  const m = LOOSE_HEADING_RE.exec(head) || HTML_HEADING_RE.exec(head);
  if (m && namesPrivate(m[2])) return { level: Number(m[1]) || m[1].length, lines: 1 };
  const under = next === undefined ? null : SETEXT_RE.exec(next);
  if (under && head.trim() && namesPrivate(head)) return { level: under[1][0] === '=' ? 1 : 2, lines: 2 };
  return null;
}

// Removes every private section down to the next # heading of the same or a higher level. A heading
// inside a code block does not end one, and neither does an underlined heading, because a --- under a
// line is often just a divider. So nothing below can leak; at worst too much stays hidden.
function withoutPrivateSections(body) {
  const lines = body.split('\n');
  const out = [];
  const hidden = [];
  let level = 0;
  let fence = '';
  let withheld = 0;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const opener = fence ? null : privateHeading(line, lines[i + 1]);
    if (opener) {
      level = level ? Math.min(level, opener.level) : opener.level;
      fence = '';
      withheld += 1;
      hidden.push(...lines.slice(i, i + opener.lines));
      i += opener.lines - 1;
      continue;
    }
    if (!level) {
      out.push(line);
      continue;
    }
    const f = FENCE_RE.exec(line);
    if (fence) {
      if (f && f.groups.fence[0] === fence[0] && f.groups.fence.length >= fence.length && !f.groups.rest.trim()) fence = '';
    } else if (f) {
      fence = f.groups.fence;
    } else if (isHeading(line) && isHeading(line) <= level) {
      level = 0;
      out.push(line);
      continue;
    }
    hidden.push(line);
  }
  return { text: out.join('\n'), hidden, withheld };
}

// Text with private parts removed. Sections first, because a tagged heading opens a section.
function publicText(text) {
  const sections = withoutPrivateSections(text);
  const lines = withoutPrivateLines(sections.text);
  return { text: lines.text, withheld: sections.withheld + lines.withheld };
}

// The page with private parts removed first, so no tool can read, count or match on them. A tagged
// header line keeps its key, so the page still counts, and loses its value.
function publicPage(rel, source) {
  const page = parsePage(rel, source);
  const clean = publicText(page.body);
  page.body = clean.text;
  page.withheld = clean.withheld;
  for (const key of Object.keys(page.meta)) {
    if (PRIVATE_TAG.test([].concat(page.meta[key]).join(' '))) {
      page.meta[key] = '(private)';
      page.withheld += 1;
    }
  }
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
        if (!SKIP_DIRS.has(entry.name) && !entry.name.startsWith('.') && !isGenerated(path.relative(vault, abs))) dirs.push(abs);
        continue;
      }
      if (!entry.name.endsWith('.md') || NOT_PAGES_ANYWHERE.has(entry.name)) continue;
      if (dir === vault && NOT_PAGES_AT_ROOT.has(entry.name)) continue;
      const rel = path.relative(vault, abs).split(path.sep).join('/');
      if (isGenerated(rel)) continue;
      try {
        if (entry.isSymbolicLink()) {
          const real = fs.realpathSync.native(abs);
          if (!isInside(vault, real) || isGenerated(path.relative(vault, real)) || !fs.statSync(abs).isFile()) {
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

// A task line: - [ ] @person what (due D) (added D) (done D) {mine|theirs} {doing}
// The same as task_match in cortex.py. It reads the ends of the line by hand instead of one big
// pattern, so a line of spaces cannot make it work for minutes.
function matchTask(line) {
  if (line.length > MAX_TASK_LINE) return null;
  const head = TASK_HEAD_RE.exec(line);
  if (!head) return null;
  let rest = line.slice(head[0].length).trimEnd();
  if (rest.includes('\n')) return null;
  let doing = false;
  if (rest.endsWith('{doing}')) {
    const inner = rest.slice(0, -7).trimEnd();
    if (inner.endsWith('{mine}') || inner.endsWith('{theirs}')) {
      rest = inner;
      doing = true;
    }
  }
  const owner = rest.endsWith('{mine}') ? 'mine' : rest.endsWith('{theirs}') ? 'theirs' : '';
  if (!owner) return null;
  rest = rest.slice(0, -(owner.length + 2));
  let end = rest.length;
  for (;;) {
    const trimmed = rest.slice(0, end).trimEnd();
    const at = trimmed.lastIndexOf('(');
    if (at === -1 || !ONE_META_RE.test(trimmed.slice(at))) break;
    end = at;
  }
  return { done: head[1], person: head[2], text: rest.slice(0, end), meta: rest.slice(end), owner, doing };
}

function parseTask(line, me) {
  const m = matchTask(line);
  if (!m) return null;
  const dates = {};
  for (const d of m.meta.matchAll(META_RE)) dates[d[1]] = d[2];
  return {
    person: m.person, text: m.text.trim(), owner: m.owner, closed: m.done !== ' ',
    due: dates.due || '', added: dates.added || '', done: dates.done || '', doing: m.doing,
    todo: me.has(m.person) && m.owner === 'mine',
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
const PROPOSAL_FIELD_RE = /^(source|status|name|saved): /;
const PROPOSAL_NOTE = 'Waiting to be filed. Nothing here counts on the card or the board until it is accepted.';

// A chat proposal, or null for any other note. It starts with plain 'source: chat' and
// 'status: proposed' lines and no --- rule, so the kit's build treats it as a loose note: nothing in
// it is validated or counted until cortex_accept files it. A person can edit it by hand, so text in
// other places is kept too: `before` is what comes ahead of the first section, `others` the sections
// with other names.
function parseProposal(text) {
  const lines = text.split('\n');
  const first = lines.findIndex((l) => l.startsWith('## '));
  const top = (first === -1 ? lines : lines.slice(0, first));
  if (!top.includes('source: chat') || !top.includes('status: proposed')) return null;
  const field = (key) => {
    const line = top.find((l) => l.startsWith(`${key}: `));
    return line ? line.slice(key.length + 2).trim() : '';
  };
  const seen = new Set();
  const before = top.filter((l) => {
    const m = PROPOSAL_FIELD_RE.exec(l);
    if (m && !seen.has(m[1])) {
      seen.add(m[1]);
      return false;
    }
    return l.trim() && l !== PROPOSAL_NOTE;
  });
  const sections = Object.create(null);
  for (const name of SECTIONS) sections[name] = [];
  const others = [];
  let current = null;
  for (const line of first === -1 ? [] : lines.slice(first)) {
    if (line.startsWith('## ')) {
      const name = line.slice(3).trim();
      current = sections[name] || { name, lines: [] };
      if (!sections[name]) others.push(current);
    } else if (current && line.trim()) {
      (Array.isArray(current) ? current : current.lines).push(line);
    }
  }
  return { name: field('name'), saved: field('saved'), sections, before, others };
}

module.exports = {
  UserError, GENERATED, MAX_FILE_BYTES, PRIVATE_TAG, PROPOSAL_NOTE, cmp, localDate, slugify, plainLetters, plainSlug, neutralise, vaultLocation, vaultSource,
  folderReason, configPointsNowhere, requireVault, isInside, isGenerated, readText, parseValue, publicPage, publicText, withoutPrivateSections,
  walk, get, parseKit, selfSlugs, parseTask, followups, inboxFiles, parseProposal,
};
