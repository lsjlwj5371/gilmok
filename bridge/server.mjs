// 에뮬레이터의 길목 앱과 이 PC의 Claude Code를 잇는 시연용 중계 서버.
// 앱은 10.0.2.2:8787 로 접속하고, 서버는 이 PC 안에서만 열린다.
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const PORT = 8787;
const MAX_BODY = 64 * 1024; // 요청 본문 상한
const MAX_OUT = 1024 * 1024; // Claude 출력 상한
const MAX_RUNNING = 2; // 동시에 띄우는 Claude 프로세스 수
let running = 0;
const MODEL = process.env.GILMOK_MODEL ?? 'sonnet';
const HERE = dirname(fileURLToPath(import.meta.url));
const CACHE_DIR = join(HERE, 'cache');
mkdirSync(CACHE_DIR, { recursive: true });

function findClaude() {
  if (process.env.CLAUDE_BIN) return process.env.CLAUDE_BIN;
  const root = join(homedir(), '.vscode', 'extensions');
  const dirs = readdirSync(root).filter((d) => d.startsWith('anthropic.claude-code-')).sort().reverse();
  for (const d of dirs) {
    const bin = join(root, d, 'resources', 'native-binary', 'claude.exe');
    if (existsSync(bin)) return bin;
  }
  throw new Error('claude 실행 파일을 찾지 못했습니다. CLAUDE_BIN을 지정하세요.');
}
const CLAUDE = findClaude();

function askClaude(system, user) {
  return new Promise((resolve, reject) => {
    const args = ['-p', '--model', MODEL, '--output-format', 'json', '--tools', '',
      '--setting-sources', '', '--strict-mcp-config', '--no-session-persistence',
      '--disable-slash-commands', '--system-prompt', system];
    const child = spawn(CLAUDE, args, { cwd: HERE, windowsHide: true });
    let out = '';
    let err = '';
    const timer = setTimeout(() => { child.kill(); reject(new Error('claude 응답 시간 초과')); }, 45000);
    const cap = () => { if (out.length + err.length > MAX_OUT) child.kill(); };
    child.stdout.on('data', (d) => { out += d; cap(); });
    child.stderr.on('data', (d) => { err += d; cap(); });
    child.on('error', (e) => { clearTimeout(timer); reject(e); });
    child.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0) return reject(new Error(`claude 종료 코드 ${code}: ${err || out}`.slice(0, 400)));
      try {
        const parsed = JSON.parse(out);
        if (parsed.is_error) return reject(new Error(String(parsed.result).slice(0, 400)));
        resolve({ text: parsed.result, costUsd: parsed.total_cost_usd ?? 0 });
      } catch (e) {
        reject(e);
      }
    });
    child.stdin.end(user);
  });
}

async function readBody(req) {
  const chunks = [];
  let size = 0;
  for await (const c of req) {
    size += c.length;
    if (size > MAX_BODY) throw Object.assign(new Error('요청이 너무 큽니다'), { status: 413 });
    chunks.push(c);
  }
  const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (typeof body.system !== 'string' || typeof body.user !== 'string') {
    throw Object.assign(new Error('system, user 문자열이 필요합니다'), { status: 400 });
  }
  return body;
}

function send(res, status, body) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(body));
}

const server = createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/health') return send(res, 200, { ok: true, model: MODEL });
  if (req.method !== 'POST' || req.url !== '/complete') return send(res, 404, { error: 'not found' });
  const started = Date.now();
  try {
    const { system, user } = await readBody(req);
    const key = createHash('sha256').update(`${MODEL}\n${system}\n${user}`).digest('hex').slice(0, 24);
    const file = join(CACHE_DIR, `${key}.json`);
    if (existsSync(file)) {
      const hit = JSON.parse(readFileSync(file, 'utf8'));
      console.log(`[cache] ${Date.now() - started}ms`);
      return send(res, 200, { text: hit.text, cached: true, ms: Date.now() - started });
    }
    if (running >= MAX_RUNNING) return send(res, 429, { error: '처리 중인 요청이 많습니다' });
    running += 1;
    let result;
    try {
      result = await askClaude(system, user);
    } finally {
      running -= 1;
    }
    const { text, costUsd } = result;
    writeFileSync(file, JSON.stringify({ text }));
    console.log(`[claude] ${Date.now() - started}ms $${costUsd.toFixed(4)}`);
    send(res, 200, { text, cached: false, ms: Date.now() - started });
  } catch (e) {
    console.error('[error]', e.message);
    send(res, e.status ?? 502, { error: e.message });
  }
});

server.listen(PORT, '127.0.0.1', () => console.log(`gilmok bridge: http://127.0.0.1:${PORT} (model=${MODEL})`));
