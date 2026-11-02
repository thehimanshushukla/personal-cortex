#!/usr/bin/env node
'use strict';
// The Cortex chat connector: a local server the Claude desktop app starts. It speaks JSON-RPC, one
// message per line, over stdin and stdout. Node standard library only. It makes no network calls.
const manifest = require('../manifest.json');
const { UserError } = require('./vault');
const { listTools, callTool, isTool } = require('./tools');

const MAX_LINE_CHARS = 1024 * 1024;
const FALLBACK_PROTOCOL = '2025-06-18';

const send = (message) => process.stdout.write(`${JSON.stringify({ jsonrpc: '2.0', ...message })}\n`);
const fail = (id, code, message) => send({ id, error: { code, message } });
const plain = (text, isError = false) => ({ content: [{ type: 'text', text }], ...(isError ? { isError: true } : {}) });

function toolResult(params) {
  try {
    return plain(callTool(params.name, params.arguments || {}));
  } catch (e) {
    if (e instanceof UserError) return plain(e.message, true);
    // Paths in a system error stay on this computer's logs, not in the chat.
    process.stderr.write(`cortex: ${params.name} failed: ${e && e.stack}\n`);
    return plain('Something went wrong reading or writing your Cortex. Nothing else was changed. Try again, and if it repeats, check the folder is still there.', true);
  }
}

function handle(message) {
  const { id, method, params } = message;
  const isRequest = id !== undefined && id !== null;
  if (typeof method !== 'string') return isRequest ? fail(id, -32600, 'Invalid request') : undefined;
  if (!isRequest) return undefined; // notifications need no answer
  switch (method) {
    case 'initialize':
      return send({
        id,
        result: {
          protocolVersion: params && typeof params.protocolVersion === 'string' ? params.protocolVersion : FALLBACK_PROTOCOL,
          capabilities: { tools: {} },
          serverInfo: { name: manifest.name, version: manifest.version },
          instructions: "The person's Cortex: their working record in a folder on this computer. Call cortex_card before your first reply. Ask before saving anything.",
        },
      });
    case 'ping':
      return send({ id, result: {} });
    case 'tools/list':
      return send({ id, result: { tools: listTools() } });
    case 'tools/call':
      if (!params || typeof params.name !== 'string' || !isTool(params.name)) return fail(id, -32602, 'Unknown tool');
      if (params.arguments !== undefined && (params.arguments === null || typeof params.arguments !== 'object' || Array.isArray(params.arguments))) {
        return fail(id, -32602, 'Arguments must be an object');
      }
      return send({ id, result: toolResult(params) });
    default:
      return fail(id, -32601, 'Method not found');
  }
}

function onLine(line) {
  if (!line.trim()) return;
  let message;
  try {
    message = JSON.parse(line);
  } catch (e) {
    fail(null, -32700, 'Parse error');
    return;
  }
  if (message === null || typeof message !== 'object' || Array.isArray(message)) {
    fail(null, -32600, 'Invalid request');
    return;
  }
  handle(message);
}

let buffer = '';
let dropping = false; // inside a line that was too long
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  buffer += chunk;
  let at = buffer.indexOf('\n');
  while (at !== -1) {
    const line = buffer.slice(0, at);
    buffer = buffer.slice(at + 1);
    if (dropping) dropping = false;
    else onLine(line);
    at = buffer.indexOf('\n');
  }
  if (buffer.length > MAX_LINE_CHARS) {
    if (!dropping) fail(null, -32700, 'Message too large');
    dropping = true;
    buffer = '';
  }
});
