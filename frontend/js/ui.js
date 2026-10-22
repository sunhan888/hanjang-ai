// 화면 도구 모음. html`` 는 끼워 넣는 값을 자동으로 이스케이프한다 (판독 결과는 외부 입력이므로).

class Raw { constructor(v) { this.v = v; } toString() { return this.v; } }
export const raw = (v) => new Raw(String(v));
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

function part(v) {
  if (v instanceof Raw) return v.v;
  if (Array.isArray(v)) return v.map(part).join('');
  if (v === null || v === undefined || v === false) return '';
  return esc(v);
}

export function html(strings, ...vals) {
  let out = strings[0];
  vals.forEach((v, i) => { out += part(v) + strings[i + 1]; });
  return new Raw(out);
}

// ---- 알림·복사·음성·공유 ----
let toastTimer;
export function toast(message) {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // http(보안 연결 아님)·오래된 브라우저 대비
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

export function speak(text) {
  if (!('speechSynthesis' in window)) return false;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'ko-KR';
  u.rate = 0.95;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
  return true;
}

export async function shareText({ title, text, url }) {
  if (navigator.share) {
    try {
      await navigator.share({ title, text, url });
      return 'shared';
    } catch (e) {
      if (e && e.name === 'AbortError') return 'cancelled';
    }
  }
  return (await copyText(`${text}\n${url}`)) ? 'copied' : 'failed';
}

// ---- 표기 ----
const WD = '일월화수목금토'; // Date.getDay(): 0 = 일요일
function parseISO(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d);
}
export const won = (n) => (n === null || n === undefined || n === '' ? '' : `${Number(n).toLocaleString('ko-KR')}원`);
export function md(iso) {
  if (!iso) return '';
  const d = parseISO(iso);
  return `${d.getMonth() + 1}월 ${d.getDate()}일(${WD[d.getDay()]})`;
}
export function mdShort(iso) {
  if (!iso) return '';
  const d = parseISO(iso);
  return `${d.getMonth() + 1}월 ${d.getDate()}일`;
}
export const weekday = (iso) => (iso ? `${WD[parseISO(iso).getDay()]}요일` : '');
export const ymd = (iso) => (iso ? `${parseISO(iso).getFullYear()}년 ${md(iso)}` : '');
export function dateTime(v) {
  if (!v) return '';
  const [ds, ts] = String(v).split(' ');
  if (!ts) return ymd(ds);
  const [h, mi] = ts.split(':').map(Number);
  return `${ymd(ds)} ${h < 12 ? '오전' : '오후'} ${h % 12 || 12}시 ${mi}분`;
}
export const plateText = (p) => (p ? String(p).replace(/([가-힣])(\d{4})$/, '$1 $2') : '');
export const issuerShort = (s) => (s ? String(s).replace(/장$/, '') : '기관');
export function daysText(n) {
  if (n === null || n === undefined) return '';
  if (n === 0) return '오늘이 마감일이에요';
  if (n < 0) return `${-n}일 지났어요`;
  if (n % 7 === 0 && n <= 28) return `${n / 7}주 남았어요`;
  return `${n}일 남았어요`;
}

// ---- 아이콘 (선 아이콘, 장식이므로 aria-hidden) ----
const svg = (body, size = 24) => raw(
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" ` +
  `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`,
);
export const icon = {
  back: svg('<path d="M15 5l-7 7 7 7"/>'),
  camera: svg('<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>', 26),
  check: svg('<path d="M5 12.5l4.5 4.5L19 7.5"/>', 26),
  alert: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5v.01"/>', 26),
  corners: svg('<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>'),
  sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
  timer: svg('<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2.5M9 2h6"/>'),
  paper: svg('<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>'),
  speaker: svg('<path d="M11 5L6 9H3v6h3l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>', 22),
  share: svg('<path d="M12 15V3M7.5 7.5L12 3l4.5 4.5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/>', 22),
  shield: svg('<path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6l7-3z"/><path d="M9 12l2 2 4-4"/>', 26),
};
