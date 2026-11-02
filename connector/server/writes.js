'use strict';
// Every write the extension can make. Nothing here edits or deletes an existing page, takes a path
// from the caller, runs a command or calls the network. New files use exclusive create.
const fs = require('fs');
const path = require('path');
const V = require('./vault');

const { UserError, get } = V;
const MAX_PROPOSAL_BYTES = 20 * 1024;
const MAX_WRITES_PER_HOUR = 20;
const TODO_FILE = 'chat-todos';
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const RESERVED_AREAS = new Set(['people', 'organisations', 'sources', 'inbox', 'node-modules', 'cortex']);
const IGNORABLE_IN_EMPTY_FOLDER = new Set(['.DS_Store', '.localized', 'Thumbs.db', 'desktop.ini']);
const BACKUP_NOTE = 'Backup is not set up: these pages exist only on this computer. To get backup, open the Code tab of the Claude desktop app, install the Cortex plugin and ask it to set up backups for this folder.';

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
    .replace(/^\[([^\]]*)\]$/, '$1') // a title that is all brackets would read as a list in a page header
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

// One task line in the kit's grammar: - [ ] @person what (due D) (added D) {owner}
function taskLine(item, me) {
  if (item === null || typeof item !== 'object' || Array.isArray(item)) throw new UserError('A to-do must have separate fields: what, person, due, owner.');
  for (const key of Object.keys(item)) {
    if (!['what', 'person', 'due', 'owner'].includes(key)) throw new UserError(`A to-do has no field called "${key}".`);
  }
  const what = text(item, 'what', 300).replace(/[{}]/g, '');
  if (/\((?:due|added|done)\s+\d{4}-\d{2}-\d{2}\)/.test(what)) throw new UserError('Put the date in the "due" field, not inside "what".');
  if (item.owner !== 'mine' && item.owner !== 'theirs') throw new UserError('"owner" must be "mine" (the person owes it) or "theirs" (someone owes it to them).');
  const person = item.person === undefined || item.person === '' ? 'me' : slug(item.person, '"person"');
  if (item.owner === 'theirs' && me.has(person)) throw new UserError('A "theirs" item needs the name of the person who owes it, like alex-rivera.');
  if (item.due !== undefined && item.due !== '' && (typeof item.due !== 'string' || !isRealDate(item.due))) {
    throw new UserError(`"due" must be a real date written YYYY-MM-DD (got ${JSON.stringify(item.due).slice(0, 40)}).`);
  }
  const line = `- [ ] @${person} ${what}${item.due ? ` (due ${item.due})` : ''} (added ${V.localDate()}) {${item.owner}}`;
  if (!V.FOLLOWUP_RE.test(line)) throw new UserError('That to-do could not be written as a valid line. Nothing was saved.');
  return line;
}

// ---------------------------------------------------------------- writing inside the cortex

// Each folder on the way must be a real folder; a symlink anywhere is refused.
function realDir(vault, rel) {
  let current = vault;
  for (const part of rel.split('/').filter(Boolean)) {
    current = path.join(current, part);
    let st = null;
    try {
      st = fs.lstatSync(current);
    } catch (e) {
      if (e.code !== 'ENOENT') throw e;
    }
    if (!st) fs.mkdirSync(current);
    else if (!st.isDirectory()) throw new UserError(`${rel} is not a plain folder inside your Cortex, so nothing was saved there.`);
  }
  return current;
}

// Exclusive create; on a name clash try -2, -3 and so on. Returns the stem it used.
function createUnique(vault, relDir, stem, render, taken = () => false) {
  const dir = realDir(vault, relDir);
  for (let n = 1; n < 1000; n += 1) {
    const name = n === 1 ? stem : `${stem}-${n}`;
    if (taken(name)) continue;
    try {
      fs.writeFileSync(path.join(dir, `${name}.md`), render(name), { flag: 'wx' });
      return name;
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
    }
  }
  throw new UserError('Could not find a free file name. Nothing was saved.');
}

function checkSize(content) {
  const size = Buffer.byteLength(content);
  if (size > MAX_PROPOSAL_BYTES) {
    throw new UserError(`That is too large to save (${Math.ceil(size / 1024)} KB; the most is ${MAX_PROPOSAL_BYTES / 1024} KB). Nothing was saved. Shorten it.`);
  }
}

const PROPOSAL_NOTE = 'Waiting to be filed. Nothing here counts on the card or the board until it is accepted.';

function proposalTop(name) {
  return ['source: chat', 'status: proposed', `name: ${name}`, `saved: ${V.localDate()}`, '', PROPOSAL_NOTE, ''];
}

// ---------------------------------------------------------------- cortex_todo_add

function todoAdd(args) {
  const vault = V.requireVault();
  checkRate();
  const line = taskLine(args, V.selfSlugs(vault));
  const dir = realDir(vault, 'inbox');
  const file = path.join(dir, `${TODO_FILE}.md`);
  const start = [...proposalTop('To-dos added from chat'), '## Follow-ups', ''].join('\n');
  let existed = true;
  try {
    const st = fs.lstatSync(file);
    if (!st.isFile()) throw new UserError('inbox/chat-todos.md is not a plain file, so nothing was added.');
    checkSize(`${V.readText(file)}${line}\n`);
  } catch (e) {
    if (e.code !== 'ENOENT') throw e;
    existed = false;
  }
  if (!existed) {
    try {
      fs.writeFileSync(file, start, { flag: 'wx' });
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
    }
  }
  const nofollow = fs.constants.O_NOFOLLOW || 0;
  const fd = fs.openSync(file, fs.constants.O_WRONLY | fs.constants.O_APPEND | nofollow);
  try {
    fs.writeSync(fd, `${line}\n`);
  } finally {
    fs.closeSync(fd);
  }
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
  const tasks = items.map((f) => taskLine(f, me));
  const lines = [...proposalTop(title), '## Summary', '', summary, ''];
  if (decisions.length) lines.push('## Decisions', '', ...decisions.map((d) => `- ${d}`), '');
  if (tasks.length) lines.push('## Follow-ups', '', ...tasks, '');
  if (openQuestions.length) lines.push('## Open questions', '', ...openQuestions.map((q) => `- ${q}`), '');
  const content = lines.join('\n');
  checkSize(content);
  const stem = createUnique(vault, 'inbox', `chat-${V.localDate()}-${V.slugify(title).slice(0, 50).replace(/-+$/, '')}`, () => content);
  recordWrite();
  return `Saved to your inbox as "${stem}". It is not filed yet, so it does not count on your card or board. Say "accept ${stem}" with an area to file it.`;
}

// ---------------------------------------------------------------- cortex_accept

function personPage(personSlug) {
  const title = personSlug.split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');
  const date = V.localDate();
  return `---\nid: person-${personSlug}\ntitle: ${title}\ntype: person\nstatus: active\ncreated: ${date}\nupdated: ${date}\ntags: []\nlinks: []\nsource: chat\nsummary: Named in a saved chat. Say who they are.\n---\n\n# ${title}\n\n## Who they are\n\n## History\n\n## Open follow-ups\n`;
}

function accept(args) {
  const vault = V.requireVault();
  checkRate();
  const id = slug(args.id, '"id"');
  const area = slug(args.area, '"area"');
  const thing = args.thing === undefined || args.thing === '' ? '' : slug(args.thing, '"thing"');

  const inboxAbs = path.join(vault, 'inbox', `${id}.md`);
  let st = null;
  try {
    realDir(vault, 'inbox');
    st = fs.lstatSync(inboxAbs);
  } catch (e) {
    if (e instanceof UserError) throw e;
  }
  if (!st || !st.isFile()) throw new UserError(`There is nothing called "${id}" in your inbox. Ask what is in your inbox to see the ids.`);
  const proposal = V.parseProposal(V.readText(inboxAbs));
  if (!proposal) throw new UserError(`"${id}" is an imported note, not a saved chat. Those are filed from the sorting desk in the Code tab.`);

  const read = V.walk(vault);
  const areas = read.pages.filter((p) => get(p, 'type') === 'area').map((p) => get(p, 'area'));
  if (!areas.includes(area)) throw new UserError(`There is no area called "${area}". Your areas: ${areas.join(', ') || 'none yet'}.`);
  let base = `${area}/sessions`;
  if (thing) {
    const inArea = read.pages.filter((p) => get(p, 'type') === 'thing' && get(p, 'area') === area && p.rel.split('/').length === 4);
    const match = inArea.find((p) => p.rel.split('/')[2] === thing);
    if (!match) {
      const known = inArea.map((p) => p.rel.split('/')[2]).join(', ') || 'none yet';
      throw new UserError(`There is no "${thing}" in ${area}. Known there: ${known}. Leave the thing out to file it under the area.`);
    }
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
  const names = [...new Set(tasks.map((l) => V.parseTask(l, me).person))].filter((p) => !me.has(p));
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

  const title = clean(proposal.name) || id;
  const summaryLines = sections.Summary.map(clean).filter(Boolean);
  const pageSummary = summaryLines.join(' ').slice(0, 200) || `${title}, saved from a chat.`;
  const date = isRealDate(proposal.saved) ? proposal.saved : V.localDate();
  const body = [`# ${title}`, ''];
  body.push('## What happened', '', ...(summaryLines.length ? summaryLines : [`${title}, saved from a chat.`]), '');
  const bullets = (name) => sections[name].map(clean).filter(Boolean).map((l) => `- ${l}`);
  if (bullets('Decisions').length) body.push('## Decisions', '', ...bullets('Decisions'), '');
  if (tasks.length || otherFollowups.length) body.push('## Follow-ups', '', ...tasks, ...otherFollowups.map((l) => `- ${l}`), '');
  if (bullets('Open questions').length) body.push('## Open / next', '', ...bullets('Open questions'), '');

  // Everything is checked. Add the people, keep the proposal under sources/, then write the page.
  for (const name of newPeople) createOnce(vault, 'people', name, personPage(name));
  const month = date.slice(0, 7);
  const sourceDir = realDir(vault, `sources/${month}`);
  let sourceRel = '';
  for (let n = 1; n < 1000 && !sourceRel; n += 1) {
    const name = n === 1 ? `${id}.md` : `${id}-${n}.md`;
    try {
      fs.linkSync(inboxAbs, path.join(sourceDir, name)); // unlike a rename, this never overwrites
      fs.unlinkSync(inboxAbs);
      sourceRel = `sources/${month}/${name}`;
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
    }
  }
  if (!sourceRel) throw new UserError('Could not keep a copy of the proposal. Nothing was filed.');

  const ids = new Set(read.pages.map((p) => get(p, 'id')));
  const idFor = (name) => (thing ? `session-${area}-${thing}-${name}` : `session-${area}-${name}`);
  const render = (name) => ['---', `id: ${idFor(name)}`, `title: ${title}`, 'type: session', `area: ${area}`,
    ...(thing ? [`thing: ${thing}`] : []), 'status: active', `created: ${date}`, `updated: ${V.localDate()}`,
    'tags: []', 'links: []', 'source: chat', `sources: [${sourceRel}]`, `summary: ${pageSummary}`, '---', '', ...body].join('\n');
  let stem;
  try {
    stem = createUnique(vault, base, `${date}-${V.slugify(title)}`, render, (name) => ids.has(idFor(name)));
  } catch (e) {
    fs.linkSync(path.join(vault, sourceRel), inboxAbs); // put the proposal back
    fs.unlinkSync(path.join(vault, sourceRel));
    throw e;
  }
  recordWrite();
  const extras = newPeople.length ? ` New person page(s): ${newPeople.map((n) => `people/${n}.md`).join(', ')}.` : '';
  return `Filed "${title}" as ${base}/${stem}.md (id ${idFor(stem)}). ${tasks.length} follow-up(s) now count on your card and board.${extras} The saved proposal moved to ${sourceRel}.`;
}

function createOnce(vault, relDir, name, content) {
  fs.writeFileSync(path.join(realDir(vault, relDir), `${name}.md`), content, { flag: 'wx' });
}

// ---------------------------------------------------------------- cortex_setup

function setup(args) {
  const where = V.vaultLocation();
  let exists = false;
  try {
    const st = fs.statSync(where);
    if (!st.isDirectory()) throw new UserError(`${where} is a file, not a folder. Choose a folder in the extension's settings.`);
    exists = true;
  } catch (e) {
    if (e.code !== 'ENOENT') throw e;
  }
  if (exists && fs.readdirSync(where).some((n) => !IGNORABLE_IN_EMPTY_FOLDER.has(n))) {
    throw new UserError(`${where} already has files in it, so setup will not touch it. If it is your Cortex, you are already set up. To start a new one, choose an empty folder in the extension's settings.`);
  }
  checkRate();
  const name = text(args, 'name', 80).replace(/[{}]/g, '');
  if (!Array.isArray(args.areas) || !args.areas.length) throw new UserError('"areas" must list at least one area, like Personal or Work.');
  if (args.areas.length > 12) throw new UserError('Please start with 12 areas or fewer.');
  const areas = args.areas.map((a, i) => {
    const title = text({ area: a }, 'area', 60);
    const areaSlug = V.slugify(title);
    if (RESERVED_AREAS.has(areaSlug)) throw new UserError(`"${title}" is a name Cortex keeps for itself. Pick another area name (item ${i + 1}).`);
    return { title, slug: areaSlug };
  });
  const slugs = areas.map((a) => a.slug);
  if (new Set(slugs).size !== slugs.length) throw new UserError('Two areas would get the same folder name. Make them different.');

  fs.mkdirSync(where, { recursive: true });
  const vault = fs.realpathSync(where);
  const templates = path.join(__dirname, 'templates');
  const template = (file) => fs.readFileSync(path.join(templates, file), 'utf8');
  const write = (rel, content) => {
    fs.mkdirSync(path.dirname(path.join(vault, rel)), { recursive: true });
    fs.writeFileSync(path.join(vault, rel), content, { flag: 'wx' });
  };
  const fill = (tpl, values) => tpl.replace(/\{\{(\w+)\}\}/g, (all, key) => (key in values ? values[key] : all));
  const date = V.localDate();
  const marker = /cortex:begin (v[\d.]+)/.exec(template('AGENTS.md'));
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
    name, vault, kit_version: marker ? marker[1].slice(1) : '0.0.0', setup_date: date, areas: slugs.join(', '),
    collections_lines: slugs.map((s) => `collections_${s}: []`).join('\n'), github: 'no',
  }));
  recordWrite();
  return `Your Cortex is ready at ${vault}, with these areas: ${slugs.join(', ')}.\n${BACKUP_NOTE}\nAsk for your card to see it. When a chat is worth keeping, say "save this chat".`;
}

module.exports = { todoAdd, saveChat, accept, setup, TODO_FILE };
