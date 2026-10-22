// 서버 호출. 주소 뒤에 ?mock 을 붙이면 서버 없이 mock/*.json 으로 모든 화면을 돌려 볼 수 있다.
//   ?mock            정상 (D-14)
//   ?mock=check      확인 필요 (위반 일시 연도 오독)
//   ?mock=today      마감 당일
//   ?mock=overdue    기한 지남
//   ?mock=blur | cut | unsupported | error   실패 화면
// mock/*.json 은 backend/scripts/make_mock_results.py 가 실제 파이프라인으로 만든다.

const params = new URLSearchParams(location.search);
export const MOCK = params.has('mock') ? (params.get('mock') || 'ok') : null;
const BASE = (window.HANJANG_API_BASE || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(code, message, status = 0, reason = null) {
    super(message);
    this.code = code;
    this.status = status;
    this.reason = reason;
  }
}

async function parse(res) {
  if (res.ok) return res.status === 204 ? null : res.json();
  let detail = {};
  try { detail = (await res.json()).detail || {}; } catch { detail = {}; }
  throw new ApiError(detail.code || `HTTP_${res.status}`, detail.message || '서버와 연결이 원활하지 않아요.', res.status);
}

async function call(path, options) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, options);
  } catch {
    throw new ApiError('NETWORK', '인터넷 연결을 확인해 주세요.');
  }
  return parse(res);
}

export function createAnalysis(blob) {
  if (MOCK) return mock.create();
  const fd = new FormData();
  fd.append('image', blob, 'notice.jpg');
  return call('/api/analyses', { method: 'POST', body: fd });
}

export function getAnalysis(id) {
  if (MOCK) return mock.get(id);
  return call(`/api/analyses/${encodeURIComponent(id)}`);
}

export function deleteAnalysis(id) {
  if (MOCK) return Promise.resolve(null);
  return call(`/api/analyses/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

// ---- mock ----
const FAIL = {
  blur: { error_code: 'UNREADABLE', error_reason: 'blur', error_message: '사진의 글자를 읽기 어려워요.' },
  cut: { error_code: 'UNREADABLE', error_reason: 'cut', error_message: '사진의 글자를 읽기 어려워요.' },
  unsupported: { error_code: 'UNSUPPORTED', error_message: '아직 읽을 수 없는 문서예요.' },
  error: { error_code: 'LLM_ERROR', error_message: '판독 중 문제가 생겼어요.' },
};
const FILE = { ok: 'result', check: 'result-check', today: 'result-today', overdue: 'result-overdue' };

const mock = {
  started: new Map(),
  async create() {
    const id = `00000000-0000-4000-8000-${String(Date.now()).slice(-12).padStart(12, '0')}`;
    this.started.set(id, Date.now());
    return { id, status: 'processing', stage: 'reading' };
  },
  async get(id) {
    const t0 = this.started.get(id) ?? Date.now() - 60000; // 공유 링크로 바로 열어도 결과가 보이게
    const sec = (Date.now() - t0) / 1000;
    const base = { id, created_at: new Date(t0).toISOString(), expires_at: new Date(t0 + 864e5).toISOString() };
    if (sec < 1.5) return { ...base, status: 'processing', stage: 'reading' };
    if (sec < 3) return { ...base, status: 'processing', stage: 'checking' };
    if (sec < 4.2) return { ...base, status: 'processing', stage: 'planning' };
    if (FAIL[MOCK]) return { ...base, status: 'failed', ...FAIL[MOCK] };
    const res = await fetch(`mock/${FILE[MOCK] || FILE.ok}.json`);
    return { ...base, status: 'done', stage: 'done', result: await res.json() };
  },
};
