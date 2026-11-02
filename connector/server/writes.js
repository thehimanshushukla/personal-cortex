'use strict';
// Every write the extension can make. Nothing here edits or deletes an existing page, takes a path
// from the caller, runs a command or calls the network. A new file is written in full under a temporary
// name, then linked to its real name, which never overwrites. A write with several steps undoes the
// earlier ones when a later one fails, and only then says what happened.
const fs = require('fs');
const path = require('path');
const V = require('./vault');

const { UserError, get, SLUG_RE } = V;
const MAX_PROPOSAL_BYTES = 20 * 1024;
const MAX_WRITES_PER_HOUR = 20;
const TODO_FILE = 'chat-todos';
const RESERVED_AREAS = new Set(['people', 'organisations', 'sources', 'inbox', 'node-modules', 'cortex']);
const IGNORABLE_IN_EMPTY_FOLDER = new Set(['.DS_Store', '.localized', 'Thumbs.db', 'desktop.ini']);
const BACKUP_NOTE = 'Backup is not set up: these pages exist only on this computer. To add backup, open the Code tab of the Claude desktop app, install the Cortex plugin and say "set up my cortex". It finds this folder and only offers to set up the backup, which needs a free GitHub account.';
const LOCK_NAME = '.chat-write.lock.tmp'; // *.tmp is in the cortex's .gitignore
const LOCK_WAIT_MS = 3000;
const LOCK_STALE_MS = 30000;
const LOCK_FUTURE_MS = 2000; // a lock dated further ahead than clocks can differ here has a wrong time, so it can never age

// ---------------------------------------------------------------- rate limit

let recentWrites = [];

function checkRate() {
  const hourAgo = Date.now() - 3600000;
  recentWrites = recentWrites.filter((t) => t > hourAgo);
  if (recentWrites.length >= MAX_WRITES_PER_HOUR) {
    throw new UserError(`Cortex saved ${MAX_WRITES_PER_HOUR} times in the last hour, which is its limit. Nothing was saved. Try again later.`);
  }
}
const recordWrite = () => recentWrites.push(Date.now());

// ---------------------------------------------------------------- checking what comes in

// One short line of plain text. Line breaks of every kind become spaces, and markup that would give the
// line a meaning at the start (a list, a task, a heading, a code block, a rule) is removed.
function oneLine(value) {
  return String(value)
    .replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^(?:[\s\-*+#>`~=_|]+|\[\s*[xX]?\s*\])+/, '')
    .replace(/^\[(.*)\]$/, '$1') // a title that starts and ends in brackets would read as a list in a page header
    .trim();
}

function text(args, field, max) {
  const value = args[field];
  if (typeof value !== 'string') throw new UserError(`"${field}" must be text.`);
  const out = oneLine(value);
  if (!/[\p{L}\p{N}]/u.test(out)) throw new UserError(`"${field}" needs some words in it.`);
  if (out.length > max) throw new UserError(`"${field}" is too long (${out.length} characters; the most is ${max}). Shorten it.`);
  return out;
}

function list(args, field, itemMax, countMax) {
  const value = args[field];
  if (value === undefined) return [];
  if (!Array.isArray(value)) throw new UserError(`"${field}" must be a list.`);
  if (value.length > countMax) throw new UserError(`"${field}" has ${value.length} items; the most is ${countMax}.`);
  return value.map((item, i) => text({ [`${field} item ${i + 1}`]: item }, `${field} item ${i + 1}`, itemMax));
}

function isRealDate(s) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const [y, m, d] = s.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d;
}

function slug(value, what) {
  if (typeof value !== 'string' || value.length > 70 || !SLUG_RE.test(value)) {
    throw new UserError(`${what} must be lowercase words joined by hyphens, like alex-rivera.`);
  }
  return value;
}

// Claude naturally writes "Priya Nair", "José Núñez" or "@priya-nair": turn any of them into the slug.
function personSlug(value) {
  // Names only: a path, a line break or a task line is refused, not tidied into a slug.
  const name = typeof value === 'string' ? V.plainLetters(value).replace(/\u2019/g, "'") : '';
  if (name.length > 70 || !/^@?[a-z0-9][a-z0-9' .-]*$/.test(name)) {
    throw new UserError('A follow-up needs a person\'s name that can be written in Latin letters, like Alex Rivera or José Núñez. For a name in another script, give its Latin spelling.');
  }
  return V.plainSlug(name.replace(/^@/, ''));
}

// The person's own name as a plain slug. cortex.py makes "José" into jos-, so this form is not one of its own.
const plainSelf = (vault) => V.plainSlug(V.parseKit(vault).name || '');

// One task line in the kit's grammar: - [ ] @person what (due D) (added D) {owner}
function taskLine(item, me, self) {
  if (item === null || typeof item !== 'object' || Array.isArray(item)) throw new UserError('A to-do must have separate fields: what, person, due, owner.');
  for (const key of Object.keys(item)) {
    if (!['what', 'person', 'due', 'owner'].includes(key)) throw new UserError(`A to-do has no field called "${key}".`);
  }
  const what = text(item, 'what', 300).replace(/[{}]/g, '');
  if (/\((?:due|added|done)\s+\d{4}-\d{2}-\d{2}\)/.test(what)) throw new UserError('Put the date in the "due" field, not inside "what".');
  if (item.owner !== 'mine' && item.owner !== 'theirs') throw new UserError('"owner" must be "mine" (the person owes it) or "theirs" (someone owes it to them).');
  let person = item.person === undefined || item.person === '' ? 'me' : personSlug(item.person);
  if (self && person === self && !me.has(person)) person = 'me';
  if (item.owner === 'theirs' && me.has(person)) throw new UserError('A "theirs" item needs the name of the person who owes it, like alex-rivera.');
  if (item.due !== undefined && item.due !== '' && (typeof item.due !== 'string' || !isRealDate(item.due))) {
    throw new UserError(`"due" must be a real date written YYYY-MM-DD (got ${JSON.stringify(item.due).slice(0, 40)}).`);
  }
  const line = `- [ ] @${person} ${what}${item.due ? ` (due ${item.due})` : ''} (added ${V.localDate()}) {${item.owner}}`;
  if (!V.parseTask(line, me)) throw new UserError('That to-do could not be written as a valid line. Nothing was saved.');
  return line;
}

// ---------------------------------------------------------------- writing inside the cortex

// Runs a write that may have several steps. Each step adds to `undo` what would reverse it. On any failure
// the steps are reversed, and the message says what really happened: `nothing` when all went back,
// and which files are left when something would not.
function guarded(nothing, work) {
  const undo = [];
  try {
    return work(undo);
  } catch (e) {
    const left = [];
    for (const [name, reverse] of undo.reverse()) {
      try {
        reverse();
      } catch (err) {
        if (err.code !== 'ENOENT') left.push(name);
      }
    }
    const after = left.length
      ? `Cortex could not undo everything. Please delete these by hand: ${left.join(', ')}. Everything else went back as it was.`
      : nothing;
    if (e instanceof UserError) {
      if (!left.length) throw e;
      throw new UserError(`${e.message} ${after}`);
    }
    process.stderr.write(`cortex: write failed: ${e && e.stack}\n`);
    throw new UserError(`${whyWriteFailed(e)} ${after}`);
  }
}

function whyWriteFailed(e) {
  if (['ENOSPC', 'EDQUOT', 'EFBIG'].includes(e.code)) return 'The disk is full, or the file limit was reached.';
  if (['EACCES', 'EPERM', 'EROFS'].includes(e.code)) return 'This computer did not allow writing to that folder.';
  return 'A file could not be written.';
}

// Only one server at a time may change the inbox: the app can run two, and a to-do added while its
// file is being filed would otherwise be lost. A lock left by a crash goes stale, and so does one dated in the future.
function withInboxLock(dir, work) {
  const lock = path.join(dir, LOCK_NAME);
  const giveUp = Date.now() + LOCK_WAIT_MS;
  for (;;) {
    try {
      fs.closeSync(fs.openSync(lock, 'wx'));
      break;
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
    }
    try {
      const age = Date.now() - fs.statSync(lock).mtimeMs;
      if (age > LOCK_STALE_MS || age < -LOCK_FUTURE_MS) {
        fs.unlinkSync(lock);
        continue;
      }
    } catch (e) {
      if (e.code !== 'ENOENT') throw e;
      continue;
    }
    if (Date.now() > giveUp) throw new UserError('Cortex is busy saving something else, perhaps in another window. Nothing was saved. Try again in a moment.');
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 25);
  }
  try {
    return work();
  } finally {
    try { fs.unlinkSync(lock); } catch (e) { /* it may have gone stale and been removed */ }
  }
}

// Each folder on the way must be a real folder; a symlink anywhere is refused.
function realDir(vault, rel, undo = []) {
  let current = vault;
  for (const part of rel.split('/').filter(Boolean)) {
    current = path.join(current, part);
    let st = null;
    try {
      st = fs.lstatSync(current);
    } catch (e) {
      if (e.code !== 'ENOENT') throw e;
    }
    if (!st) {
      fs.mkdirSync(current);
      const made = current;
      undo.push([path.relative(vault, made), () => fs.rmdirSync(made)]);
    } else if (!st.isDirectory()) throw new UserError(`${rel} is not a plain folder inside your Cortex, so nothing was saved there.`);
  }
  return current;
}

// A file system with no hard links gets a copy instead. Either way an existing name is never overwritten.
function linkNew(from, to) {
  try {
    fs.linkSync(from, to);
  } catch (e) {
    if (!['EPERM', 'ENOTSUP', 'ENOSYS', 'EOPNOTSUPP'].includes(e.code)) throw e;
    try {
      fs.copyFileSync(from, to, fs.constants.COPYFILE_EXCL);
    } catch (err) {
      if (err.code !== 'EEXIST') {
        try { fs.unlinkSync(to); } catch (gone) { /* it never appeared */ }
      }
      throw err;
    }
  }
}

// The whole file or nothing, and never over an existing file (EEXIST).
function writeNew(abs, content) {
  const tmp = path.join(path.dirname(abs), `.${path.basename(abs)}.${process.pid}.${Date.now()}.tmp`);
  try {
    const fd = fs.openSync(tmp, 'wx');
    try {
      fs.writeFileSync(fd, content);
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    linkNew(tmp, abs);
  } finally {
    try { fs.unlinkSync(tmp); } catch (e) { /* it was never made */ }
  }
}

// On a name clash try -2, -3 and so on. Returns the stem it used.
function createUnique(vault, relDir, stem, render, taken = () => false, undo = []) {
  const dir = realDir(vault, relDir, undo);
  for (let n = 1; n < 1000; n += 1) {
    const name = n === 1 ? stem : `${stem}-${n}`;
    if (taken(name)) continue;
    const abs = path.join(dir, `${name}.md`);
    try {
      writeNew(abs, render(name));
      undo.push([path.relative(vault, abs), () => fs.unlinkSync(abs)]);
      return name;
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
    }
  }
  throw new UserError('Could not find a free file name. Nothing was saved.');
}

function checkSize(content, what = 'That', fix = 'Shorten it.') {
  const size = typeof content === 'number' ? content : Buffer.byteLength(content);
  if (size > MAX_PROPOSAL_BYTES) {
    throw new UserError(`${what} is too large to save (${Math.ceil(size / 1024)} KB; the most is ${MAX_PROPOSAL_BYTES / 1024} KB). Nothing was saved. ${fix}`);
  }
}

const TODOS_FULL = ['Your to-do list in the inbox', `File it first: say "accept ${TODO_FILE}" with an area. The next to-do then starts a new list.`];

function proposalTop(name) {
  return ['source: chat', 'status: proposed', `name: ${name}`, `saved: ${V.localDate()}`, '', V.PROPOSAL_NOTE, ''];
}

// ---------------------------------------------------------------- cortex_todo_add

function todoAdd(args) {
  const vault = V.requireVault();
  checkRate();
  const line = taskLine(args, V.selfSlugs(vault), plainSelf(vault));
  const nothing = 'The to-do was not added.';
  guarded(nothing, (undo) => withInboxLock(realDir(vault, 'inbox', undo), () => {
    const file = path.join(vault, 'inbox', `${TODO_FILE}.md`);
    let added = `${line}\n`;
    let st = null;
    try {
      st = fs.lstatSync(file);
    } catch (e) {
      if (e.code !== 'ENOENT') throw e;
    }
    if (st) {
      if (!st.isFile()) throw new UserError('inbox/chat-todos.md is not a plain file, so nothing was added.');
      if (st.size > MAX_PROPOSAL_BYTES) checkSize(st.size, ...TODOS_FULL); // decided before reading a file that may be huge
      const old = V.readText(file);
      const lastSection = old.split('\n').filter((l) => l.startsWith('## ')).pop();
      if (lastSection !== '## Follow-ups') added = `\n## Follow-ups\n\n${added}`; // edited by hand: stay out of its other sections
      if (old && !old.endsWith('\n')) added = `\n${added}`; // never glue two lines together
      checkSize(`${old}${added}`, ...TODOS_FULL);
    } else {
      writeNew(file, [...proposalTop('To-dos added from chat'), '## Follow-ups', ''].join('\n'));
      undo.push([`inbox/${TODO_FILE}.md`, () => fs.unlinkSync(file)]);
    }
    // Written at the end by position: the lock keeps other servers out, and a failed write can be taken back.
    const fd = fs.openSync(file, fs.constants.O_WRONLY | (fs.constants.O_NOFOLLOW || 0));
    try {
      const size = fs.fstatSync(fd).size;
      const bytes = Buffer.from(added);
      try {
        for (let done = 0; done < bytes.length;) done += fs.writeSync(fd, bytes, done, bytes.length - done, size + done);
        fs.fsyncSync(fd);
      } catch (e) {
        fs.ftruncateSync(fd, size); // no half a line left behind
        throw e;
      }
    } finally {
      fs.closeSync(fd);
    }
  }));
  recordWrite();
  return `Added to your inbox, not yet on your card or board:\n${line}\nSay "accept ${TODO_FILE}" with an area to file it.`;
}

// ---------------------------------------------------------------- cortex_save_chat

function saveChat(args) {
  const vault = V.requireVault();
  checkRate();
  const title = text(args, 'title', 120);
  const summary = text(args, 'summary', 2000);
  const decisions = list(args, 'decisions', 500, 30);
  const openQuestions = list(args, 'open_questions', 500, 30);
  const me = V.selfSlugs(vault);
  if (args.followups !== undefined && !Array.isArray(args.followups)) throw new UserError('"followups" must be a list.');
  const items = args.followups || [];
  if (items.length > 30) throw new UserError(`"followups" has ${items.length} items; the most is 30.`);
  const tasks = items.map((f) => taskLine(f, me, plainSelf(vault)));
  const lines = [...proposalTop(title), '## Summary', '', summary, ''];
  if (decisions.length) lines.push('## Decisions', '', ...decisions.map((d) => `- ${d}`), '');
  if (tasks.length) lines.push('## Follow-ups', '', ...tasks, '');
  if (openQuestions.length) lines.push('## Open questions', '', ...openQuestions.map((q) => `- ${q}`), '');
  const content = lines.join('\n');
  checkSize(content);
  // The id is shown wherever the proposal is listed, so a private title must not become part of it.
  const titleSlug = V.PRIVATE_TAG.test(title) ? 'private' : (V.plainSlug(title) || 'untitled').slice(0, 50).replace(/-+$/, '');
  const stem = guarded('Nothing was saved.', (undo) => createUnique(vault, 'inbox', `chat-${V.localDate()}-${titleSlug}`, () => content, undefined, undo));
  recordWrite();
  return `Saved to your inbox as "${stem}". It is not filed yet, so it does not count on your card or board. Say "accept ${stem}" with an area to file it.`;
}

// ---------------------------------------------------------------- cortex_accept

function personPage(personSlug) {
  const title = personSlug.split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');
  const date = V.localDate();
  return `---\nid: person-${personSlug}\ntitle: ${title}\ntype: person\nstatus: active\ncreated: ${date}\nupdated: ${date}\ntags: []\nlinks: []\nsource: chat\nsummary: Named in a saved chat. Say who they are.\n---\n\n# ${title}\n\n## Who they are\n\n## History\n\n## Open follow-ups\n`;
}

// Where in the cortex a saved chat can go. The name comes from a page, so it counts only if that page
// really is <name>/_index.md, which also means it cannot be a path out of the folder.
function findArea(read, asked) {
  const areas = read.pages.filter((p) => get(p, 'type') === 'area').map((p) => ({ name: String(get(p, 'area')), rel: p.rel }));
  const listed = areas.map((a) => a.name).join(', ') || 'none yet';
  const wanted = typeof asked === 'string' ? asked.trim() : '';
  const exact = areas.find((a) => a.name === wanted);
  const found = exact || areas.find((a) => a.name.toLowerCase() === wanted.toLowerCase() || a.name === V.plainSlug(wanted));
  if (!wanted || !found) throw new UserError(`There is no area called "${oneLine(wanted).slice(0, 80)}". Your areas: ${listed}.`);
  if (found.name.includes('/') || found.rel !== `${found.name}/_index.md`) {
    throw new UserError(`The area "${found.name}" has its page at ${found.rel}, not at ${found.name}/_index.md, so nothing can be filed under it. Move that page, or choose another area: ${listed}.`);
  }
  return found.name;
}

function accept(args) {
  const vault = V.requireVault();
  checkRate();
  const id = slug(args.id, '"id"');
  const nothingHere = `There is nothing called "${id}" in your inbox. Ask what is in your inbox to see the ids.`;
  let inboxSt = null;
  try {
    inboxSt = fs.lstatSync(path.join(vault, 'inbox'));
  } catch (e) {
    if (e.code !== 'ENOENT') throw e;
  }
  if (!inboxSt) throw new UserError(nothingHere);
  const nothing = `Nothing was filed, and "${id}" is still in your inbox.`;
  return guarded(nothing, (undo) => withInboxLock(realDir(vault, 'inbox'), () => {
    const inboxAbs = path.join(vault, 'inbox', `${id}.md`);
    let st = null;
    try {
      st = fs.lstatSync(inboxAbs);
    } catch (e) {
      if (e.code !== 'ENOENT') throw e;
    }
    if (!st || !st.isFile()) throw new UserError(nothingHere);
    if (st.size > V.MAX_FILE_BYTES) throw new UserError(`"${id}" is too large to file here (the most is ${V.MAX_FILE_BYTES / 1024 / 1024} MB). ${nothing}`);
    // Private sections are kept apart from here on, so they can only end up inside the page's own private section.
    const split = V.withoutPrivateSections(V.readText(inboxAbs));
    const proposal = V.parseProposal(split.text);
    if (!proposal) throw new UserError(`"${id}" is an imported note, not a saved chat. Those are filed from the sorting desk in the Code tab.`);

    const read = V.walk(vault);
    const area = findArea(read, args.area);
    let base = `${area}/sessions`;
    let thing = '';
    if (args.thing !== undefined && args.thing !== '') {
      const inArea = read.pages.filter((p) => get(p, 'type') === 'thing' && get(p, 'area') === area && p.rel.split('/').length === 4);
      const named = (p) => p.rel.split('/')[2];
      const asked = String(args.thing).trim();
      const match = inArea.find((p) => named(p) === asked) || inArea.find((p) => named(p).toLowerCase() === asked.toLowerCase() || named(p) === V.plainSlug(asked));
      if (!match) {
        const known = inArea.map(named).join(', ') || 'none yet';
        throw new UserError(`There is no "${oneLine(asked).slice(0, 80)}" in ${area}. Known there: ${known}. Leave the thing out to file it under the area.`);
      }
      thing = named(match);
      base = `${match.rel.split('/').slice(0, 3).join('/')}/sessions`;
    }

    // Re-read everything from the file: it may have been edited since it was saved.
    const me = V.selfSlugs(vault);
    const clean = (l) => oneLine(l);
    const { sections } = proposal;
    const tasks = [];
    const otherFollowups = [];
    for (const line of sections['Follow-ups']) {
      const task = V.parseTask(line, me);
      if (task && SLUG_RE.test(task.person)) tasks.push(line);
      else if (clean(line)) otherFollowups.push(clean(line));
    }
    // A task tagged {private} is hidden: it never makes a people page and is never named in a reply.
    const isPublic = (l) => !V.PRIVATE_TAG.test(l);
    const names = [...new Set(tasks.filter(isPublic).map((l) => V.parseTask(l, me).person))].filter((p) => !me.has(p));
    const peopleKnown = new Set(read.pages.filter((p) => p.rel.startsWith('people/')).map((p) => path.basename(p.rel, '.md')));
    for (const name of names) {
      if (read.loose.some((p) => p.rel === `people/${name}.md`)) {
        throw new UserError(`people/${name}.md has no header, and your Cortex would reject a follow-up naming them. Give that page a header first. Nothing was filed.`);
      }
      if (read.skipped.includes(`people/${name}.md`)) {
        throw new UserError(`people/${name}.md could not be read, and your Cortex would reject a follow-up naming them. Fix that page first. Nothing was filed.`);
      }
    }
    const newPeople = names.filter((n) => !peopleKnown.has(n));
    // The build stops on a task line naming someone with no page. So a hidden task like that stays on the
    // page as a plain private line, which the build and the board do not count, until that person has a page.
    const canCount = (l) => {
      const who = V.parseTask(l, me).person;
      return isPublic(l) || me.has(who) || peopleKnown.has(who) || names.includes(who);
    };
    const kept = tasks.filter(canCount);
    const asNotes = tasks.filter((l) => !canCount(l)).map(clean);
    const hiddenCount = tasks.length - tasks.filter(isPublic).length;

    // A private title or summary line must not reach the page header. The line itself stays in the body, still tagged.
    const title = (isPublic(proposal.name) && clean(proposal.name)) || id;
    const summaryLines = sections.Summary.map(clean).filter(Boolean);
    const pageSummary = summaryLines.filter(isPublic).join(' ').slice(0, 200).trim() || `${title}, saved from a chat.`;
    const date = isRealDate(proposal.saved) ? proposal.saved : V.localDate();
    const bullets = (list) => list.map(clean).filter(Boolean).map((l) => `- ${l}`);
    const body = [`# ${title}`, ''];
    if (bullets(proposal.before).length) body.push('## Notes', '', ...bullets(proposal.before), '');
    body.push('## What happened', '', ...(summaryLines.length ? summaryLines : [`${title}, saved from a chat.`]), '');
    if (bullets(sections.Decisions).length) body.push('## Decisions', '', ...bullets(sections.Decisions), '');
    if (tasks.length || otherFollowups.length) body.push('## Follow-ups', '', ...kept, ...[...asNotes, ...otherFollowups].map((l) => `- ${l}`), '');
    if (bullets(sections['Open questions']).length) body.push('## Open / next', '', ...bullets(sections['Open questions']), '');
    // Other sections carry across as plain text: their lines cannot become tasks or end a section.
    for (const other of proposal.others) body.push(`## ${clean(other.name) || 'Notes'}`, '', ...bullets(other.lines), '');
    if (bullets(split.hidden).length) body.push('## Private', '', ...bullets(split.hidden), '');

    // Everything is checked. Add the people, keep a copy of the proposal under sources/, write the page, and
    // only then take the proposal out of the inbox. Any failure on the way undoes the steps before it.
    for (const name of newPeople) createPerson(vault, name, undo);
    const month = date.slice(0, 7);
    const sourceDir = realDir(vault, `sources/${month}`, undo);
    let sourceRel = '';
    for (let n = 1; n < 1000 && !sourceRel; n += 1) {
      const name = n === 1 ? `${id}.md` : `${id}-${n}.md`;
      const kept = path.join(sourceDir, name);
      try {
        linkNew(inboxAbs, kept);
        sourceRel = `sources/${month}/${name}`;
        undo.push([sourceRel, () => fs.unlinkSync(kept)]);
      } catch (e) {
        if (e.code !== 'EEXIST') throw e;
      }
    }
    if (!sourceRel) throw new UserError(`Could not keep a copy of the proposal. ${nothing}`);

    const ids = new Set(read.pages.map((p) => get(p, 'id')));
    const idFor = (name) => (thing ? `session-${area}-${thing}-${name}` : `session-${area}-${name}`);
    const render = (name) => ['---', `id: ${idFor(name)}`, `title: ${title}`, 'type: session', `area: ${area}`,
      ...(thing ? [`thing: ${thing}`] : []), 'status: active', `created: ${date}`, `updated: ${V.localDate()}`,
      'tags: []', 'links: []', 'source: chat', `sources: [${sourceRel}]`, `summary: ${pageSummary}`, '---', '', ...body].join('\n');
    const stem = createUnique(vault, base, `${date}-${V.plainSlug(title) || 'untitled'}`, render, (name) => ids.has(idFor(name)), undo);
    fs.unlinkSync(inboxAbs);

    recordWrite();
    const extras = newPeople.length ? ` New person page(s): ${newPeople.map((n) => `people/${n}.md`).join(', ')}.` : '';
    const counted = tasks.filter(isPublic).filter(V.isOpenFollowup).length;
    const privateNote = hiddenCount ? ` ${hiddenCount} private item(s) stay on the page and are not named here.` : '';
    const notCounted = asNotes.length ? ` ${asNotes.length} of them name(s) someone with no page, so those lines are plain private notes and do not count as follow-ups until that person has a page.` : '';
    return `Filed "${title}" as ${base}/${stem}.md (id ${idFor(stem)}). ${counted} follow-up(s) now count on your card and board.${privateNote}${notCounted}${extras} The saved proposal moved to ${sourceRel}.`;
  }));
}

function createPerson(vault, name, undo) {
  const abs = path.join(realDir(vault, 'people', undo), `${name}.md`);
  try {
    writeNew(abs, personPage(name));
    undo.push([`people/${name}.md`, () => fs.unlinkSync(abs)]);
  } catch (e) {
    if (e.code !== 'EEXIST') throw e; // someone made it a moment ago: it is there, and it stays
  }
}

// ---------------------------------------------------------------- cortex_setup

// Makes a folder and any missing parents, each one undoable.
function makeDirs(dir, undo) {
  if (fs.existsSync(dir)) return;
  makeDirs(path.dirname(dir), undo);
  fs.mkdirSync(dir);
  undo.push([dir, () => fs.rmdirSync(dir)]);
}

function setup(args) {
  const src = V.vaultSource();
  const { where } = src;
  const reason = V.folderReason(src);
  let exists = false;
  try {
    const st = fs.statSync(where);
    if (!st.isDirectory()) throw new UserError(`${where} is a file, not a folder (${reason}), so it cannot hold a Cortex.`);
    exists = true;
  } catch (e) {
    if (e.code !== 'ENOENT') throw e;
  }
  if (!exists && src.fromConfig) throw new UserError(V.configPointsNowhere(src));
  if (exists && fs.readdirSync(where).some((n) => !IGNORABLE_IN_EMPTY_FOLDER.has(n))) {
    const state = fs.existsSync(path.join(where, 'kit.yaml')) ? 'If it is your Cortex, you are already set up.' : 'It has no finished Cortex in it (no kit.yaml).';
    const change = src.fromConfig ? `To use another folder, change or remove ${src.configFile} first.` : "To start a new one, choose an empty folder in the extension's settings.";
    throw new UserError(`${where} (${reason}) already has files in it, so setup will not touch it. ${state} ${change}`);
  }
  checkRate();
  const rawName = typeof args.name === 'string' ? args.name.trim() : '';
  if (rawName.startsWith('[') && rawName.endsWith(']')) throw new UserError('Please give your name as plain words, with no brackets around it.');
  const name = text(args, 'name', 80).replace(/[{}]/g, '');
  if (V.parseValue(name) !== name) throw new UserError('Please give your name as plain words, with no quotes or brackets around it.');
  if (!Array.isArray(args.areas) || !args.areas.length) throw new UserError('"areas" must list at least one area, like Personal or Work.');
  if (args.areas.length > 12) throw new UserError('Please start with 12 areas or fewer.');
  const areas = args.areas.map((a, i) => {
    const title = text({ area: a }, 'area', 60);
    const areaSlug = V.plainSlug(title);
    if (!areaSlug) throw new UserError(`"${title}" cannot become a folder name, because folder names use Latin letters and numbers. Please give that area a name with some, like Work (item ${i + 1}).`);
    if (RESERVED_AREAS.has(areaSlug)) throw new UserError(`"${title}" is a name Cortex keeps for itself. Pick another area name (item ${i + 1}).`);
    return { title, slug: areaSlug };
  });
  const slugs = areas.map((a) => a.slug);
  if (new Set(slugs).size !== slugs.length) throw new UserError('Two areas would get the same folder name. Make them different.');

  const nothing = `Everything it had created was removed, so you can try again. Nothing is set up yet at ${where}.`;
  return guarded(nothing, (undo) => {
    makeDirs(where, undo);
    const vault = fs.realpathSync.native(where);
    const templates = path.join(__dirname, 'templates');
    const template = (file) => fs.readFileSync(path.join(templates, file), 'utf8');
    const write = (rel, content) => {
      const abs = path.join(vault, rel);
      makeDirs(path.dirname(abs), undo);
      writeNew(abs, content);
      undo.push([abs, () => fs.unlinkSync(abs)]);
    };
    const fill = (tpl, values) => tpl.replace(/\{\{(\w+)\}\}/g, (all, key) => (key in values ? values[key] : all));
    const date = V.localDate();
    const marker = /cortex:begin (v[\d.]+)/.exec(template('AGENTS.md'));
    const version = marker ? marker[1].slice(1) : '0.0.0';
    for (const folder of ['people', 'organisations', 'sources', 'inbox', V.GENERATED]) write(`${folder}/.gitkeep`, '');
    for (const file of ['AGENTS.md', 'CLAUDE.md', 'GEMINI.md']) write(file, template(file));
    write('.gitignore', template('gitignore'));
    for (const area of areas) {
      write(`${area.slug}/_index.md`, fill(template('area_index.md'), {
        area: area.slug, title: area.title, date, summary: `What I keep under ${area.title}.`,
        collections: 'Nothing yet. Projects and other things you track get their own folders here.',
      }));
      write(`${area.slug}/meetings/.gitkeep`, '');
    }
    write('kit.yaml', fill(template('kit.yaml'), {
      name, vault, kit_version: version, setup_date: date, areas: slugs.join(', '),
      collections_lines: slugs.map((s) => `collections_${s}: []`).join('\n'), github: 'no',
    }));
    // The same pointer file the plugin's own setup writes, so the plugin finds this folder. Never over one that exists.
    let pointer = `${src.configFile} already exists and could not be used, so it was left as it is. The Cortex plugin will not find this folder until that file is fixed.`;
    if (src.fromConfig) pointer = `The folder is ${reason}.`;
    else if (!src.configExists) {
      makeDirs(path.dirname(src.configFile), undo);
      writeNew(src.configFile, `${JSON.stringify({ vault, kit_version: version })}\n`);
      undo.push([src.configFile, () => fs.unlinkSync(src.configFile)]);
      pointer = `Cortex also wrote ${src.configFile} so the Cortex plugin can find this folder. From now on that file decides which folder is used, and the extension's folder setting is ignored.`;
    }
    recordWrite();
    return `Your Cortex is ready at ${vault}, with these areas: ${slugs.join(', ')}.\n${pointer}\n${BACKUP_NOTE}\nAsk for your card to see it. When a chat is worth keeping, say "save this chat".`;
  });
}

module.exports = { todoAdd, saveChat, accept, setup, TODO_FILE };
