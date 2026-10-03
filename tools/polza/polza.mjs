#!/usr/bin/env node
// Polza.ai media CLI: balance, model catalog with prices, media generation.
// Uses only documented endpoints: GET /v2/balance, GET /v1/models/catalog,
// POST /v1/media, GET /v1/media/{id}. Run via ./polza (sets proxy env).
//
// Paid calls (gen) are a dry run unless --yes is passed.

import { mkdir, writeFile, appendFile } from 'node:fs/promises';
import { dirname, join, resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const API = process.env.POLZA_API_BASE || 'https://api.polza.ai/api';
const KEY = process.env.POLZA_AI_API_KEY;
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const OUT_DIR = process.env.POLZA_OUT_DIR || join(REPO, 'generated');
const LOG = join(OUT_DIR, 'polza-log.jsonl');

const HELP = `polza — Polza.ai media CLI

  polza balance                         баланс и доступная сумма (₽)
  polza models [--type image|video|tts|music|stt] [--search q] [--limit N]
                                        модели, отсортированные по цене
  polza price <model> [--param k=v ...] цена и параметры модели
  polza gen <model> --prompt "..." [--param k=v ...] [--image path|url ...]
            [--out file] [--yes]        генерация (без --yes — только показать цену)
  polza status <id>                     статус задачи

Файлы → ${OUT_DIR}, журнал → ${LOG}`;

function parseArgs(argv) {
  const pos = [], opt = { param: [], image: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) { pos.push(a); continue; }
    const k = a.slice(2);
    if (k === 'yes' || k === 'help') { opt[k] = true; continue; }
    const v = argv[++i];
    if (Array.isArray(opt[k])) opt[k].push(v); else opt[k] = v;
  }
  return { pos, opt };
}

async function api(method, path, body, auth = true) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth && KEY) headers.Authorization = `Bearer ${KEY}`;
  const r = await fetch(API + path, { method, headers, body: body && JSON.stringify(body) });
  const text = await r.text();
  let data; try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!r.ok) {
    const e = data.error || {};
    throw new Error(`HTTP ${r.status} ${e.code || ''}: ${e.message || text.slice(0, 300)}`);
  }
  return data;
}

const rub = x => (x == null ? '?' : `${Number(x).toFixed(2)} ₽`);

function parseParams(list) {
  const p = {};
  for (const kv of list) {
    const i = kv.indexOf('=');
    if (i < 0) throw new Error(`--param ожидает k=v, получено: ${kv}`);
    const k = kv.slice(0, i), v = kv.slice(i + 1);
    p[k] = v === 'true' ? true : v === 'false' ? false : /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : v;
  }
  return p;
}

// Price for given params: per_request, or the most specific matching tier.
function priceFor(model, params) {
  const pr = model.top_provider?.pricing || model.pricing;
  if (!pr) return { cost: null, label: 'нет данных о цене' };
  if (pr.per_request != null) return { cost: Number(pr.per_request), label: 'за запрос' };
  if (pr.tiers) {
    const match = pr.tiers.filter(t => t.conditions.every(c => {
      const [k, v] = c.split('=');
      return String(params[k] ?? defaultOf(model, k)) === v;
    }));
    match.sort((a, b) => b.conditions.length - a.conditions.length);
    const t = match[0] ?? pr.tiers.find(t => !t.conditions.length);
    if (t) return { cost: Number(t.cost_rub), label: t.conditions.join(', ') || 'базовый тариф' };
  }
  return { cost: null, label: JSON.stringify(pr).slice(0, 200) };
}

function defaultOf(model, k) {
  return (model.parameters || model.top_provider?.parameters || {})[k]?.default;
}

function minPrice(model) {
  const pr = model.top_provider?.pricing || model.pricing || {};
  if (pr.per_request != null) return Number(pr.per_request);
  if (pr.tiers?.length) return Math.min(...pr.tiers.map(t => Number(t.cost_rub)));
  return null;
}

async function findModel(id) {
  const d = await api('GET', `/v1/models/catalog?search=${encodeURIComponent(id)}&limit=50`, null, false);
  const m = d.data.find(m => m.id === id);
  if (!m) throw new Error(`модель ${id} не найдена (похожие: ${d.data.slice(0, 5).map(m => m.id).join(', ') || '—'})`);
  return m;
}

async function toMediaRef(src) {
  if (/^https?:\/\//.test(src)) return { type: 'url', data: src };
  const { readFile } = await import('node:fs/promises');
  const ext = extname(src).slice(1).toLowerCase().replace('jpg', 'jpeg');
  const b64 = (await readFile(src)).toString('base64');
  return { type: 'base64', data: `data:image/${ext || 'png'};base64,${b64}` };
}

async function cmdBalance() {
  const b = await api('GET', '/v2/balance');
  console.log(`Баланс: ${rub(b.amount)}  доступно: ${rub(b.available)}  резерв: ${rub(b.reservedAmount)}  потрачено всего: ${rub(b.spentAmount)}`);
}

async function cmdModels(opt) {
  const q = new URLSearchParams({ sortBy: 'price', sortOrder: 'asc', limit: opt.limit || '20' });
  if (opt.type) q.set('type', opt.type);
  if (opt.search) q.set('search', opt.search);
  const d = await api('GET', `/v1/models/catalog?${q}`, null, false);
  for (const m of d.data) {
    const p = minPrice(m);
    console.log(`${(p == null ? '?' : 'от ' + rub(p)).padEnd(14)} ${m.type.padEnd(6)} ${m.id}  — ${m.name}`);
  }
  console.log(`(${d.data.length} из ${d.meta?.total ?? '?'})`);
}

async function cmdPrice(id, opt) {
  const m = await findModel(id);
  const params = parseParams(opt.param);
  const { cost, label } = priceFor(m, params);
  console.log(`${m.id} (${m.name}, ${m.type}): ${rub(cost)} — ${label}`);
  console.log('Параметры:', JSON.stringify(m.parameters || m.top_provider?.parameters, null, 2));
}

async function cmdGen(id, opt) {
  if (!opt.prompt) throw new Error('нужен --prompt');
  const m = await findModel(id);
  const input = { prompt: opt.prompt, ...parseParams(opt.param) };
  // Fill required params that have defaults (e.g. aspect_ratio).
  for (const [k, spec] of Object.entries(m.parameters || {})) {
    if (spec?.required && input[k] == null && spec.default != null) input[k] = spec.default;
  }
  if (opt.image.length) input.images = await Promise.all(opt.image.map(toMediaRef));
  const { cost, label } = priceFor(m, input);
  console.log(`Модель: ${m.id} (${m.name})\nЦена: ${rub(cost)} (${label})\nInput: ${JSON.stringify({ ...input, images: input.images?.length })}`);
  if (!opt.yes) { console.log('\nПробный прогон — деньги не списаны. Добавьте --yes для генерации.'); return; }

  const b = await api('GET', '/v2/balance');
  if (cost != null && Number(b.available) < cost) throw new Error(`недостаточно средств: доступно ${rub(b.available)}, нужно ${rub(cost)}`);

  let t = await api('POST', '/v1/media', { model: m.id, input });
  console.log(`Задача ${t.id}: ${t.status}`);
  const interval = m.type === 'video' ? 8000 : 4000;
  const deadline = Date.now() + (m.type === 'video' ? 20 : 5) * 60_000;
  while (!['completed', 'failed'].includes(t.status)) {
    if (Date.now() > deadline) throw new Error(`таймаут, проверьте позже: polza status ${t.id}`);
    await new Promise(r => setTimeout(r, interval));
    t = await api('GET', `/v1/media/${t.id}`);
    process.stdout.write(`… ${t.status}\n`);
  }
  if (t.status === 'failed') throw new Error(`генерация не удалась: ${JSON.stringify(t.error)}`);

  const urls = [t.data?.url, ...(Array.isArray(t.data) ? t.data.map(x => x.url) : []), ...(t.data?.urls || [])].filter(Boolean);
  await mkdir(OUT_DIR, { recursive: true });
  const files = [];
  for (const [i, url] of urls.entries()) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`не удалось скачать ${url}: HTTP ${r.status}`);
    const ext = extname(new URL(url).pathname) || '.bin';
    const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const file = opt.out && urls.length === 1 ? resolve(opt.out)
      : join(OUT_DIR, `${stamp}_${m.id.replace(/\W+/g, '-')}${urls.length > 1 ? '_' + i : ''}${ext}`);
    await mkdir(dirname(file), { recursive: true });
    await writeFile(file, Buffer.from(await r.arrayBuffer()));
    files.push(file);
    console.log(`Сохранено: ${file}`);
  }
  const spent = t.usage?.cost_rub ?? t.usage?.cost ?? cost;
  await appendFile(LOG, JSON.stringify({ date: new Date().toISOString(), id: t.id, model: m.id, prompt: opt.prompt, input: { ...input, images: input.images?.length }, cost_rub: spent, files, urls }) + '\n');
  console.log(`Списано: ${rub(spent)}. Запись добавлена в ${LOG}`);
}

async function cmdStatus(id) {
  console.log(JSON.stringify(await api('GET', `/v1/media/${id}`), null, 2));
}

const { pos, opt } = parseArgs(process.argv.slice(2));
const [cmd, arg] = pos;
try {
  if (!cmd || opt.help) console.log(HELP);
  else if (cmd === 'balance') await cmdBalance();
  else if (cmd === 'models') await cmdModels(opt);
  else if (cmd === 'price') await cmdPrice(arg, opt);
  else if (cmd === 'gen') await cmdGen(arg, opt);
  else if (cmd === 'status') await cmdStatus(arg);
  else { console.log(HELP); process.exitCode = 2; }
} catch (e) {
  console.error('Ошибка:', e.message);
  process.exitCode = 1;
}
