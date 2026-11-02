'use strict';
// The start card, computed from the pages. Follows render_card in plugins/cortex/scripts/cortex.py.
// The only differences are the hints that name things chat cannot do, listed in the tests' golden
// comparison, the "and N more" lines, the line naming the folder, a line counting pages it had to skip,
// and a line counting task lines it hid as private, which cortex.py counts.
const path = require('path');
const V = require('./vault');

const { get, cmp } = V;
const newestFirst = (key) => (a, b) => cmp(key(b), key(a)); // equal items keep their order, like Python's reverse sort

function addDays(iso, days) {
  const [y, m, d] = iso.split('-').map(Number);
  return V.localDate(new Date(y, m - 1, d + days));
}

function lastBackup(vault) {
  try {
    const lines = V.readText(path.join(vault, V.GENERATED, 'backup.log')).split('\n').reverse();
    for (const line of lines) {
      if (line.includes(' pushed') || line.includes(' committed') || line.includes(' nothing to back up')) return line.slice(0, 10);
    }
  } catch (e) { /* no backup yet */ }
  return null;
}

function daysBetween(fromIso, toIso) {
  const at = (iso) => { const [y, m, d] = iso.split('-').map(Number); return Date.UTC(y, m - 1, d); };
  return Math.round((at(toIso) - at(fromIso)) / 86400000);
}

function clip(text, max) {
  const s = String(text);
  if (s.length <= max) return s;
  const cut = s.slice(0, max - 3);
  const last = cut.charCodeAt(cut.length - 1);
  return `${(last >= 0xd800 && last <= 0xdbff ? cut.slice(0, -1) : cut).trimEnd()}...`; // never split a character in two
}

function more(list, shown) {
  return list.length > shown ? [`- and ${list.length - shown} more.`] : [];
}

function render(read, vault, limits) {
  const { pages, loose, skipped } = read;
  const now = V.localDate();
  const kitName = [].concat(V.parseKit(vault).name || '').join(', '); // a name like [Rob] [Vale] reads as a list
  const me = V.selfSlugs(vault);
  const all = V.followups(pages, me);
  const say = (t) => clip(t, limits.clip);
  const wide = (t) => clip(t, limits.clip * 3);
  const lines = [`# Cortex card${kitName ? ` - ${say(kitName)}` : ''}`, '', `As of ${now}.`, wide(`Folder: ${vault} (${V.folderReason()})`), ''];
  const areas = pages.filter((p) => get(p, 'type') === 'area');
  if (areas.length) lines.push(wide(`Areas: ${areas.map((p) => get(p, 'area')).sort(cmp).join(', ')}`), '');
  const things = pages.filter((p) => get(p, 'type') === 'thing' && get(p, 'status') === 'active');
  const sessions = pages.filter((p) => get(p, 'type') === 'session').sort(newestFirst((p) => get(p, 'updated')));
  const lastByThing = new Map();
  for (const s of sessions) {
    const key = `${get(s, 'area')}/${get(s, 'thing')}`;
    if (!lastByThing.has(key)) lastByThing.set(key, s);
  }
  if (things.length) {
    const recency = (t) => {
      const parts = t.rel.split('/');
      const s = lastByThing.get(`${get(t, 'area')}/${parts[parts.length - 2]}`);
      return String(get(s || t, 'updated'));
    };
    const ranked = things.slice().sort(newestFirst(recency));
    lines.push('## Active', '');
    for (const t of ranked.slice(0, limits.active)) {
      lines.push(`- **${say(get(t, 'title'))}** (${say(get(t, 'area'))}, last ${recency(t)}): ${say(get(t, 'summary'))}`);
    }
    lines.push(...more(ranked, limits.active), '');
  }
  for (const [type, label, n] of [['decision', 'Latest decisions', limits.decisions], ['lesson', 'Lessons to remember', limits.lessons]]) {
    const group = pages.filter((p) => get(p, 'type') === type && get(p, 'status') === 'active').sort(newestFirst((p) => get(p, 'updated')));
    if (group.length) {
      lines.push(`## ${label}`, '', ...group.slice(0, n).map((p) => `- ${say(get(p, 'title'))} - ${say(get(p, 'summary'))}`), ...more(group, n), '');
    }
  }
  const soon = addDays(now, 7);
  const byDue = (a, b) => cmp(a.due, b.due);
  const todos = all.filter((i) => i.todo);
  const items = all.filter((i) => !i.todo);
  if (todos.length) {
    lines.push(`## To-dos (${todos.length} open)`, '');
    const due = todos.filter((i) => i.due && i.due <= soon).sort(byDue);
    for (const i of due.slice(0, limits.due)) lines.push(`- ${i.due} - ${i.due < now ? 'OVERDUE: ' : ''}${say(i.text)}`);
    lines.push(...more(due, limits.due));
    if (!due.length) lines.push('- Nothing due in the next 7 days.');
    lines.push('');
  }
  if (items.length) {
    const urgent = items.filter((i) => i.due && i.due <= soon).sort(byDue);
    lines.push(`## Follow-ups (${items.length} open)`, '');
    for (const i of urgent.slice(0, limits.due)) {
      lines.push(`- ${i.due}${i.due < now ? ' - OVERDUE' : ''}: ${i.owner === 'mine' ? 'I owe' : 'owed by'} @${say(i.person)} - ${say(i.text)}`);
    }
    lines.push(...more(urgent, limits.due));
    if (!urgent.length) lines.push('- Nothing due in the next 7 days.');
    lines.push('');
  }
  const overdue = all.filter((i) => i.due && i.due < now).length;
  if (overdue) lines.push(`${overdue} overdue.`, '');
  const hiddenItems = pages.reduce((n, p) => n + p.hiddenTasks, 0);
  if (hiddenItems) lines.push(`${hiddenItems} private item${hiddenItems === 1 ? '' : 's'} not shown.`, '');
  const inbox = V.inboxFiles(vault);
  if (inbox.length) {
    const fromChat = inbox.filter((f) => {
      try { return V.parseProposal(V.readText(path.join(vault, 'inbox', f))); } catch (e) { return false; }
    }).length;
    lines.push(`Inbox: ${inbox.length} note(s) waiting${fromChat ? `, ${fromChat} saved from chat` : ''}. Say 'what is in my inbox'.`, '');
  }
  const looseOutside = loose.filter((p) => !p.rel.startsWith('inbox/'));
  if (looseOutside.length) lines.push(`Loose notes: ${looseOutside.length} with no header.`, '');
  const long = V.overlongTasks(pages);
  if (long.count) {
    const extra = long.rels.length > 3 ? ` and ${long.rels.length - 3} more` : '';
    lines.push(wide(`Not counted: ${long.count} task line${long.count === 1 ? '' : 's'} over 4,000 characters, on ${long.rels.slice(0, 3).join(', ')}${extra}.`), '');
  }
  const lb = lastBackup(vault);
  if (lb && /^\d{4}-\d{2}-\d{2}$/.test(lb)) lines.push(`Last backup: ${lb}${daysBetween(lb, now) > 7 ? ' - more than a week ago' : ''}.`);
  else lines.push('Last backup: none yet.');
  if (!pages.length || (!things.length && !sessions.length)) {
    lines.push('', "This cortex is new. Work as usual, then say 'save this chat' at the end - the next chat starts from here.");
  }
  if (skipped.length) lines.push('', `Skipped ${skipped.length} page(s) that could not be read or have a broken header.`);
  return `${lines.join('\n')}\n`;
}

// From the same list lengths as the Python card down to very short ones. Every line is clipped, and
// everything else goes before the due and overdue items do. The counts are in every tier.
const TIERS = [
  { active: 8, decisions: 5, lessons: 3, due: 6, clip: Infinity },
  { active: 8, decisions: 5, lessons: 3, due: 6, clip: 120 },
  { active: 5, decisions: 3, lessons: 2, due: 6, clip: 100 },
  { active: 3, decisions: 2, lessons: 1, due: 6, clip: 80 },
  { active: 2, decisions: 1, lessons: 1, due: 6, clip: 60 },
  { active: 1, decisions: 1, lessons: 1, due: 6, clip: 40 },
  { active: 0, decisions: 0, lessons: 0, due: 6, clip: 40 },
  { active: 0, decisions: 0, lessons: 0, due: 4, clip: 30 },
  { active: 0, decisions: 0, lessons: 0, due: 2, clip: 25 },
  { active: 0, decisions: 0, lessons: 0, due: 1, clip: 20 },
];

function card(vault, maxBytes) {
  const read = V.walk(vault);
  let text = '';
  for (const limits of TIERS) {
    text = render(read, vault, limits);
    if (Buffer.byteLength(text) <= maxBytes) return text;
  }
  return text;
}

module.exports = { card };
