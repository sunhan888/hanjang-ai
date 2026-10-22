// 한장해결 — 바닐라 JS 한 페이지 앱 (빌드 도구 없음).
// 화면 = 결과 JSON(docs/API.md)을 받아 html`` 문자열을 돌려주는 함수. 상태는 아래 state 하나.
import * as api from './api.js';
import { inspectImage, prepareImage } from './image.js';
import {
  copyText, dateTime, daysText, html, icon, issuerShort, md, mdShort, plateText, raw, shareText, speak, toast, weekday, won, ymd,
} from './ui.js';

const $app = document.getElementById('app');
const $camera = document.getElementById('file-camera');
const $album = document.getElementById('file-album');

const state = {
  file: null,          // 고른 사진 (휴대폰 안에만 있음)
  photoUrl: null,
  inspect: null,
  analyses: new Map(), // id → 마지막 서버 응답
  confirmed: {},       // id → { 항목: 'same' | 'suggestion' }  (화면에서만 쓰고 서버에는 보내지 않음)
  tab: 'pay',
  tabFrom: '',
  showPhoto: false,
  openLaw: new Set(),
};
let pollTimer = null;

// 결과 JSON 의 한국어 키 → 화면 이름·표기
const FIELD_VIEW = [
  ['위반일시', '언제', dateTime],
  ['위반장소', '어디서', (v) => v],
  ['위반차량', '어떤 차', plateText],
  ['위반내용', '무슨 위반', (v) => v],
  ['과태료금액', '원래 금액', won],
  ['감경과태료', '기한 안에 낼 금액', won],
  ['의견진술기한', '마감일', ymd],
  ['가상계좌', '입금 계좌', (v) => v],
  ['발신기관', '보낸 곳', (v) => v],
  ['발행일', '보낸 날', ymd],
  ['증거번호', '단속번호', (v) => v],
  ['문서종류', '문서 종류', (v) => v],
];
const PLAIN = Object.fromEntries(FIELD_VIEW.map(([k, name]) => [k, name]));
const CHECK_ORDER = ['의견진술기한', '감경과태료', '가상계좌', '과태료금액', '위반일시', '발행일',
  '위반차량', '위반장소', '위반내용', '증거번호', '발신기관', '문서종류'];
const AFFECTS_PAYMENT = new Set(['의견진술기한', '감경과태료', '과태료금액', '가상계좌']);

// ---------- 라우터 ----------
const routes = [
  [/^\/$/, home],
  [/^\/guide$/, guide],
  [/^\/confirm$/, confirmPhoto],
  [/^\/reading\/([\w-]+)$/, reading],
  [/^\/result\/([\w-]+)$/, resultScreen],
  [/^\/result\/([\w-]+)\/todo$/, todoScreen],
  [/^\/result\/([\w-]+)\/fields$/, fieldsScreen],
  [/^\/result\/([\w-]+)\/law$/, lawScreen],
  [/^\/error\/([\w-]+)$/, errorScreen],
];
const path = () => location.hash.replace(/^#/, '').split('?')[0] || '/';
const query = () => new URLSearchParams(location.hash.split('?')[1] || '');

function go(to) {
  if (`#${to}` === location.hash) render();
  else location.hash = to;
}

async function render({ focus = true } = {}) {
  clearTimeout(pollTimer);
  const p = path();
  for (const [re, view] of routes) {
    const m = p.match(re);
    if (!m) continue;
    try {
      const out = await view(...m.slice(1));
      if (out && path() === p) paint(out, focus); // 기다리는 사이 다른 화면으로 갔으면 그리지 않는다
    } catch (err) {
      console.error(err);
      paint(errorView('NETWORK'), focus);
    }
    return;
  }
  go('/');
}
const rerender = () => render({ focus: false });

function paint(view, focus) {
  const y = window.scrollY;
  $app.innerHTML = String(view);
  if (focus) {
    window.scrollTo(0, 0);
    const h1 = $app.querySelector('h1');
    if (h1) {
      h1.setAttribute('tabindex', '-1');
      h1.focus({ preventScroll: true });
    }
  } else {
    window.scrollTo(0, y);
  }
}

// ---------- 공통 조각 ----------
function topbar(back) {
  const big = document.documentElement.classList.contains('big');
  const left = back
    ? html`<a class="back" href="#${back[0]}">${icon.back}<span>${back[1]}</span></a>`
    : html`<a class="brand" href="#/">한장해결</a>`;
  return html`<header class="topbar">${left}
    <button class="pill" type="button" data-action="toggle-big" aria-pressed="${big}" aria-label="글자 크기 바꾸기">${big ? '가-' : '가+'}</button>
  </header>`;
}
const tip = (ic, title, sub) => html`<li><span class="tip-icon">${ic}</span><span><strong>${title}</strong><span>${sub}</span></span></li>`;
const holes = () => raw('<span class="holes" aria-hidden="true"><i></i><i></i></span>');

const paperIllust = () => raw(`<svg width="96" height="124" viewBox="0 0 96 124" aria-hidden="true">
  <rect x="14" y="14" width="68" height="96" rx="4" fill="#F7F9FC" stroke="#9AA6B5" stroke-width="1.5"/>
  <rect x="24" y="27" width="48" height="6" rx="3" fill="#15202B"/><rect x="24" y="43" width="40" height="4" rx="2" fill="#B7C1CD"/>
  <rect x="24" y="53" width="44" height="4" rx="2" fill="#B7C1CD"/><rect x="24" y="66" width="21" height="16" rx="2" fill="#DCE3EC"/>
  <rect x="51" y="66" width="21" height="16" rx="2" fill="#DCE3EC"/><rect x="24" y="91" width="30" height="5" rx="2.5" fill="#C2410C"/>
  <path d="M4 20V4H20M76 4H92V20M92 104V120H76M20 120H4V104" fill="none" stroke="#1D4ED8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>`);

const viewfinderIllust = () => raw(`<svg width="300" height="236" viewBox="0 0 300 236" role="img" aria-label="종이 네 모서리를 안내선 안에 맞춘 모습">
  <g transform="rotate(-3 150 118)"><rect x="80" y="14" width="140" height="196" rx="4" fill="#F4F6F8"/>
  <rect x="96" y="34" width="96" height="9" rx="4" fill="#1B2533"/><rect x="96" y="56" width="84" height="6" rx="3" fill="#A9B4C2"/>
  <rect x="96" y="70" width="92" height="6" rx="3" fill="#A9B4C2"/><rect x="96" y="90" width="50" height="34" rx="3" fill="#D5DCE5"/>
  <rect x="154" y="90" width="50" height="34" rx="3" fill="#D5DCE5"/><rect x="96" y="140" width="66" height="8" rx="4" fill="#C2410C"/>
  <rect x="96" y="160" width="100" height="6" rx="3" fill="#A9B4C2"/></g>
  <path d="M62 30V6H86M214 6H238V30M238 206V230H214M86 230H62V206" fill="none" stroke="#8DB7FF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>`);

const otherDocIllust = () => raw(`<svg width="300" height="220" viewBox="0 0 300 220" role="img" aria-label="종류를 알 수 없는 다른 문서">
  <rect x="80" y="14" width="140" height="192" rx="4" fill="#F4F6F8"/><rect x="80" y="14" width="140" height="30" rx="4" fill="#4C6A5A"/>
  <rect x="96" y="60" width="96" height="9" rx="4" fill="#1B2533"/><rect x="96" y="82" width="108" height="6" rx="3" fill="#A9B4C2"/>
  <rect x="96" y="96" width="92" height="6" rx="3" fill="#A9B4C2"/><rect x="96" y="134" width="108" height="40" rx="3" fill="#D5DCE5"/>
  <circle cx="222" cy="52" r="28" fill="#FFF4D6" stroke="#E2A82B" stroke-width="3"/>
  <text x="222" y="64" fill="#4A3200" font-size="34" font-weight="700" text-anchor="middle">?</text></svg>`);

// ---------- 화면 1: 홈 ----------
function home() {
  return html`<main class="screen">
    ${topbar()}
    <section class="hero stack" style="margin-top:1.5rem">
      <h1>고지서 사진 한 장이면<br>할 일을 알려 드려요</h1>
      <p class="lead">언제까지, 얼마를, 어떻게 내면 되는지 쉬운 말로 정리해 드립니다.</p>
    </section>
    <figure class="card doc-hint">${paperIllust()}<figcaption>지금 읽을 수 있는 문서<strong>주정차 위반 과태료 사전통지서</strong></figcaption></figure>
    <div class="actions">
      <button class="btn primary" type="button" data-action="open-guide">${icon.camera}사진 찍기</button>
      <button class="btn" type="button" data-action="open-album">앨범에서 고르기</button>
      <p class="fine">사진은 저장하지 않아요. 결과는 하루 뒤 지워져요.</p>
      ${api.MOCK ? html`<p class="fine">연습 모드(mock): 서버 없이 예시 결과를 보여 줘요.</p>` : ''}
    </div>
  </main>`;
}

// ---------- 화면 2: 촬영 안내 ----------
function guide() {
  return html`<main class="screen">
    ${topbar(['/', '처음으로'])}
    <h1>이렇게 찍어 주세요</h1>
    <div class="viewfinder">${viewfinderIllust()}<p>네 모서리를 파란 선 안에 맞추세요</p></div>
    <ul class="tips">
      ${tip(icon.corners, '종이 전체가 보이게', '모서리가 잘리면 기한을 놓칠 수 있어요')}
      ${tip(icon.sun, '밝은 곳에서, 그림자 없이', '손이나 휴대폰 그림자를 피해 주세요')}
      ${tip(icon.timer, '찍을 때 잠깐 멈추기', '흔들리면 숫자가 번져 보여요')}
    </ul>
    <div class="actions"><button class="btn primary" type="button" data-action="open-camera">${icon.camera}카메라 열기</button></div>
  </main>`;
}

// ---------- 화면 3: 사진 확인 ----------
function confirmPhoto() {
  if (!state.file) {
    go('/');
    return null;
  }
  const ins = state.inspect;
  let checks;
  if (!ins) checks = html`<li class="muted">사진을 살펴보는 중이에요…</li>`;
  else if (ins.issues.length) checks = ins.issues.map((t) => html`<li class="warn">${icon.alert}<span>${t}</span></li>`);
  else {
    checks = [html`<li class="ok">${icon.check}<span style="color:var(--ink)">사진 크기가 충분해요</span></li>`,
      html`<li class="ok">${icon.check}<span style="color:var(--ink)">밝기가 적당해요</span></li>`];
  }
  return html`<main class="screen">
    ${topbar(['/guide', '뒤로'])}
    <h1>이 사진으로 읽을까요?</h1>
    <div class="preview"><img src="${state.photoUrl}" alt="방금 고른 고지서 사진"></div>
    <ul class="checks">${checks}</ul>
    <div class="actions">
      ${ins && ins.error ? '' : html`<button class="btn primary" type="button" data-action="read-photo">이 사진으로 읽기</button>`}
      <button class="btn" type="button" data-action="open-camera">다시 찍기</button>
    </div>
  </main>`;
}

// ---------- 화면 4: 판독 중 ----------
const STAGES = [
  ['reading', '글자를 읽는 중', '종이에 적힌 칸 이름으로 항목을 찾아요'],
  ['checking', '날짜와 금액을 확인하는 중', '날짜 순서와 감경 금액이 맞는지 계산해요'],
  ['planning', '할 일을 정리하는 중', '관련 법 조항을 찾아 근거를 붙여요'],
];

function readingView(stage) {
  const now = stage === 'done' ? 3 : Math.max(0, STAGES.findIndex(([k]) => k === stage));
  return html`<main class="screen">
    <header class="topbar"><span class="brand">한장해결</span></header>
    <h1>고지서를 읽고 있어요</h1>
    <p class="lead">보통 20초 안팎 걸려요. 화면을 끄지 말고 기다려 주세요.</p>
    <ol class="progress" aria-live="polite">
      ${STAGES.map(([, title, sub], i) => html`<li>
        <span class="dot ${i < now ? 'done' : i === now ? 'now' : 'wait'}">${i < now ? icon.check : i + 1}</span>
        <span><strong>${title}</strong><span>${sub}</span>${i === now ? html`<span class="sr-only">진행 중</span>` : ''}</span>
      </li>`)}
    </ol>
    <div class="actions"><a class="btn text" href="#/">그만두고 처음으로</a></div>
  </main>`;
}

function reading(id) {
  const a = state.analyses.get(id);
  startPolling(id);
  return readingView(a ? a.stage : 'reading');
}

function startPolling(id) {
  const begin = Date.now();
  const here = `/reading/${id}`;
  const tick = async () => {
    if (path() !== here) return;
    try {
      const a = await api.getAnalysis(id);
      if (path() !== here) return;
      state.analyses.set(id, a);
      if (a.status === 'done') return go(`/result/${id}`);
      if (a.status === 'failed') {
        return go(`/error/${a.error_code || 'LLM_ERROR'}${a.error_reason ? `?reason=${a.error_reason}` : ''}`);
      }
      paint(readingView(a.stage), false);
    } catch (err) {
      if (err.code === 'NOT_FOUND') return go('/error/NOT_FOUND');
      // 잠깐의 연결 끊김은 다음 폴링에서 다시 시도한다
    }
    if (Date.now() - begin > 90000) return go('/error/TIMEOUT');
    pollTimer = setTimeout(tick, 1500);
    return null;
  };
  clearTimeout(pollTimer);
  pollTimer = setTimeout(tick, 700);
}

// ---------- 결과 불러오기 ----------
async function loadResult(id) {
  let a = state.analyses.get(id);
  if (!a || a.status !== 'done') {
    try {
      a = await api.getAnalysis(id);
    } catch (err) {
      go(`/error/${err.code === 'NOT_FOUND' ? 'NOT_FOUND' : 'NETWORK'}`);
      return null;
    }
    state.analyses.set(id, a);
    if (a.status === 'processing') {
      go(`/reading/${id}`);
      return null;
    }
    if (a.status === 'failed') {
      go(`/error/${a.error_code || 'LLM_ERROR'}`);
      return null;
    }
  }
  return a.result;
}
const cachedResult = (id) => (state.analyses.get(id) || {}).result;

function fieldLabel(k, f) {
  return f.label_seen && !f.label_seen.startsWith('(') ? f.label_seen : PLAIN[k];
}

// ---------- 화면 5: 결과 요약 ----------
function checkCard(id, r, flagged) {
  const k = flagged[0];
  const f = r.fields[k];
  const buttons = f.suggestion
    ? html`<p class="small">종이에 이렇게 적혀 있나요?</p><p class="suggest">${f.suggestion}</p>
      <div class="row-2"><button class="btn primary" type="button" data-action="confirm" data-field="${k}" data-how="suggestion">네, 맞아요</button>
      <button class="btn" type="button" data-action="open-camera">다시 찍기</button></div>`
    : html`<div class="row-2"><button class="btn primary" type="button" data-action="confirm" data-field="${k}" data-how="same">종이와 같아요</button>
      <button class="btn" type="button" data-action="open-camera">다시 찍기</button></div>`;
  return html`<section class="attention" aria-label="확인이 필요한 칸">
    <div class="head"><span class="mark" aria-hidden="true">!</span><span>종이의 '${fieldLabel(k, f)}' 칸을 확인해 주세요</span></div>
    <p>${f.check}</p>
    ${AFFECTS_PAYMENT.has(k) ? '' : html`<p class="small">마감일과 낼 돈은 이 칸과 상관없어서 그대로예요.</p>`}
    ${state.photoUrl ? html`<button class="link-btn" type="button" data-action="open-photo" style="color:var(--attn-ink)">찍은 사진과 같이 보기</button>` : ''}
    ${buttons}
    ${flagged.length > 1 ? html`<a class="link-btn" href="#/result/${id}/fields" style="color:var(--attn-ink)">확인할 칸 ${flagged.length}개 모두 보기</a>` : ''}
  </section>`;
}

function deadlineCard(r) {
  const d = r.dday;
  if (d.state === 'unknown') {
    return html`<section class="deadline unknown" aria-label="마감일">
      <div class="band"><span>마감일</span>${holes()}<span>확인 필요</span></div>
      <div class="body"><p class="left" style="color:var(--attn-ink)">마감일을 읽지 못했어요</p>
      <p class="small muted">종이의 '의견제출기한'이나 '자진납부 기한'을 찾아 주세요.</p></div></section>`;
  }
  const passed = d.state === 'overdue';
  const badge = d.state === 'today' ? '오늘' : passed ? '지남' : `D-${d.days_left}`;
  const dl = r.fields['의견진술기한'] || {};
  let where = '';
  if (dl.label_seen === '(문장)') where = '종이 본문 문장에 적힌 날짜예요';
  else if (dl.label_seen && !dl.label_seen.startsWith('(')) where = `종이의 '${dl.label_seen}' 칸에 적힌 날짜예요`;
  return html`<section class="deadline ${passed ? 'passed' : ''}" aria-label="마감일">
    <div class="band"><span>마감일</span>${holes()}<span>${badge}</span></div>
    <div class="body">
      <p class="date">${mdShort(d.deadline)}</p>
      <p class="left">${weekday(d.deadline)}, ${daysText(d.days_left)}</p>
      <p style="margin-top:.75rem">${passed ? '20% 깎아 주는 기한이 지났어요.' : '이 날까지 내면 20%를 깎아 줘요.'}</p>
      ${passed ? html`<p class="small muted">오늘 ${md(d.today)} 기준으로 계산했어요</p>` : where ? html`<p class="small muted">${where}</p>` : ''}
    </div></section>`;
}

function accountsBlock(accounts, label) {
  if (!accounts || !accounts.length) return html`<p class="muted">계좌를 찾지 못했어요. 종이의 납부 계좌를 확인해 주세요.</p>`;
  const lab = label && !label.startsWith('(') ? ` (종이에는 '${label}')` : '';
  return html`<div class="accounts"><p class="small muted">전용 입금 계좌${lab}</p>
    ${accounts.map((a) => html`<p class="acc">${a.bank} ${a.number}</p>
      <button class="btn outline-action" type="button" data-action="copy" data-value="${a.number.replace(/\D/g, '')}">${a.bank || ''} 계좌번호 복사</button>`)}
  </div>`;
}

function moneyCard(r) {
  const fine = r.fields['과태료금액'].value;
  const red = r.fields['감경과태료'].value;
  const d = r.dday;
  const overdue = d.state === 'overdue';
  let head = '마감일까지 내면';
  if (overdue) head = '이제 낼 돈 (원래 금액)';
  else if (d.state === 'today') head = '오늘 안에 내면';
  else if (d.deadline) head = `${mdShort(d.deadline)}까지 내면`;
  const amount = overdue ? fine : red;
  return html`<section class="card money stack" aria-label="낼 돈">
    <p class="label">${head}</p>
    <p class="amount">${amount !== null && amount !== undefined ? won(amount) : '금액을 찾지 못했어요'}</p>
    ${!overdue && fine && red ? html`<p class="muted small">원래 금액 <s>${won(fine)}</s>에서 ${won(fine - red)}을 깎은 금액이에요</p>` : ''}
    ${overdue ? html`<p class="muted small">원래 금액이 적힌 고지서가 따로 와요. 그 고지서의 계좌로 내세요.</p>`
    : accountsBlock(r.accounts, r.fields['가상계좌'].label_seen)}
  </section>`;
}

const STEP_LINK = { VERIFY: ['fields', '읽은 내용 전체 보기'], PAY: ['pay', '내는 방법 보기'], OBJECT: ['object', '의견 내는 방법 보기'] };
function stepItem(id, s, n) {
  const link = STEP_LINK[s.type];
  let a = '';
  if (link) {
    const href = link[0] === 'fields' ? `#/result/${id}/fields` : `#/result/${id}/todo?tab=${link[0]}`;
    a = html`<a class="link-btn" href="${href}">${link[1]}</a>`;
  }
  return html`<li><span class="num">${n}</span><span><strong>${s.title}</strong><p>${s.body}</p>${a}</span></li>`;
}

async function resultScreen(id) {
  const r = await loadResult(id);
  if (!r) return null;
  const conf = state.confirmed[id] || {};
  const flagged = CHECK_ORDER.filter((k) => r.fields[k] && r.fields[k].check && !conf[k]);
  const fixed = CHECK_ORDER.filter((k) => conf[k] === 'suggestion' && r.fields[k] && r.fields[k].suggestion);
  const steps = r.steps.filter((s) => !['CHECK', 'SCAM', 'REDUCE50'].includes(s.type));
  const reduce = r.steps.find((s) => s.type === 'REDUCE50');
  const scam = r.steps.find((s) => s.type === 'SCAM');
  return html`<main class="screen">
    ${topbar()}
    <section class="identity"><p>${issuerShort(r.issuer)}에서 보낸</p><h1>과태료 사전 안내문이에요</h1></section>
    ${flagged.length ? checkCard(id, r, flagged) : ''}
    ${fixed.map((k) => html`<p class="ok-note">${icon.check}<span>확인한 값으로 바꿨어요. ${PLAIN[k]}: ${r.fields[k].suggestion}</span></p>`)}
    ${deadlineCard(r)}
    ${moneyCard(r)}
    <section class="stack" aria-label="할 일">
      <h2>${r.dday.state === 'overdue' ? '이제 이렇게 하시면 돼요' : '이렇게 하시면 돼요'}</h2>
      <ol class="steps">${steps.map((s, i) => stepItem(id, s, i + 1))}</ol>
      ${reduce ? html`<a class="dashed" href="#/result/${id}/todo?tab=reduce"><strong>${reduce.title}</strong><span>${reduce.body}</span></a>` : ''}
    </section>
    ${scam ? html`<section class="info">${icon.shield}<span><strong>${scam.title}.</strong> ${scam.body}</span></section>` : ''}
    <div class="row-2">
      <button class="btn" type="button" data-action="speak">${icon.speaker}소리로 듣기</button>
      <button class="btn" type="button" data-action="share">${icon.share}가족에게 보내기</button>
    </div>
    <footer class="foot">
      <a class="link-btn" href="#/result/${id}/fields">읽은 내용 전체 보기</a>
      <a class="link-btn" href="#/result/${id}/law">왜 그런지 법에서 확인하기</a>
      <button class="link-btn" type="button" data-action="delete-record">이 결과 지금 지우기</button>
      <p class="small muted">이 화면은 안내이며 법률 자문이 아니에요. 정확한 내용은 고지서에 적힌 문의처에 물어보세요. 결과는 하루 뒤 지워져요.</p>
    </footer>
  </main>`;
}

// ---------- 화면 6: 할 일 자세히 ----------
async function todoScreen(id) {
  const r = await loadResult(id);
  if (!r) return null;
  const want = query().get('tab');
  if (want && ['pay', 'object', 'reduce'].includes(want) && state.tabFrom !== location.hash) {
    state.tab = want;
    state.tabFrom = location.hash;
  }
  const d = r.dday;
  const back = topbar([`/result/${id}`, '결과로']);
  if (d.state === 'overdue') {
    const list = r.steps.filter((s) => ['OVERDUE', 'CALL', 'OBJECT_LATE'].includes(s.type));
    return html`<main class="screen">${back}<h1>할 일 자세히</h1><ol class="steps">${list.map((s, i) => stepItem(id, s, i + 1))}</ol></main>`;
  }
  const red = r.fields['감경과태료'].value;
  const due = d.state === 'today' ? '오늘 안에' : d.deadline ? `${md(d.deadline)}까지` : '마감일까지';
  const online = /경찰/.test(r.issuer || '') ? '경찰청 교통민원24(이파인)' : '위택스';
  const panels = {
    pay: html`<div class="card money stack"><p class="label">${due}</p><p class="amount">${red ? won(red) : '금액 확인 필요'}</p>
        ${accountsBlock(r.accounts, r.fields['가상계좌'].label_seen)}</div>
      <h2>어디서 낼 수 있나요</h2>
      <ul class="steps">
        <li><span><strong>은행 앱, 인터넷뱅킹</strong><p>위 계좌로 ${red ? won(red) : '깎인 금액'}을 보내요.</p></span></li>
        <li><span><strong>은행 ATM</strong><p>계좌 이체 메뉴에서 같은 계좌를 넣어요.</p></span></li>
        <li><span><strong>${online}</strong><p>과태료를 조회해 같은 금액인지 보고 내요.</p></span></li>
      </ul>
      <p class="info">마감일 밤에는 입금이 막힐 수 있어요. 하루 전까지 내면 안전해요.</p>
      <p class="small muted">깎인 금액을 내면 이 과태료 절차는 끝나요. 따로 할 일은 없어요. (질서위반행위규제법 제18조)</p>`,
    object: html`<div class="card stack"><p class="label muted">의견을 낼 수 있는 마감</p><p style="font-size:2rem;font-weight:700;line-height:1.25">${due}</p></div>
      <h2>이럴 때 의견을 내요</h2>
      <ul class="plain-list"><li>단속 내용을 인정할 수 없을 때</li><li>그때 급한 사정이 있었을 때</li></ul>
      <h2>이렇게 내요</h2>
      <p>고지서에 적힌 방법(우편, 팩스, 방문, 누리집)으로 의견서와 증빙을 보내요.</p>
      <section class="attention"><div class="head">먼저 알아 두세요</div>
        <p>의견을 내면 보통 20% 감경은 받지 못해요. 받아들여지면 과태료가 없어지고, 받아들여지지 않으면 원래 금액이 부과돼요.</p></section>
      <p class="small muted">근거: 질서위반행위규제법 제16조(사전통지와 의견 제출)</p>`,
    reduce: html`<p>아래에 해당하면 과태료를 절반 범위에서 줄일 수 있어요.</p>
      <ul class="steps">
        <li><span><strong>기초생활수급자</strong></span></li><li><span><strong>한부모가족 보호대상자</strong></span></li>
        <li><span><strong>장애의 정도가 심한 장애인</strong></span></li><li><span><strong>국가유공자 상이등급 1~3급</strong></span></li>
        <li><span><strong>미성년자</strong></span></li>
      </ul>
      <h2>이렇게 신청해요</h2>
      <p>마감일 전에 해당 사실을 보여 주는 증명서를 고지서의 문의처에 내고 감경을 요청해요.</p>
      <p class="info">과태료를 밀린 적이 있으면 해당되지 않아요. 기한 안에 내는 20% 감경과 함께 받을 수 있는지는 기관에 확인해 주세요.</p>
      <p class="small muted">근거: 질서위반행위규제법 시행령 제2조의2</p>`,
  };
  return html`<main class="screen">${back}<h1>할 일 자세히</h1>
    <div class="tabs" role="tablist" aria-label="할 일 종류">
      ${[['pay', '내기'], ['object', '의견 내기'], ['reduce', '더 줄이기']].map(([k, label]) => html`<button type="button" role="tab"
        aria-selected="${state.tab === k}" data-action="tab" data-tab="${k}">${label}</button>`)}
    </div>
    <section role="tabpanel" class="stack">${panels[state.tab] || panels.pay}</section>
  </main>`;
}

// ---------- 화면 7: 읽은 내용 ----------
function fieldRow(f, conf, k, name, fmt) {
  let where = '';
  if (!f.label_seen) where = f.value === null || f.value === undefined ? '종이에서 못 찾음' : '';
  else if (f.label_seen === '(문장)') where = '본문 문장';
  else if (f.label_seen.startsWith('(')) where = f.label_seen.slice(1, -1);
  else where = `종이 칸: ${f.label_seen}`;
  const empty = f.value === null || f.value === undefined || f.value === '';
  const value = conf[k] === 'suggestion' && f.suggestion ? f.suggestion : empty ? null : fmt(f.value);
  return html`<li><span class="meta"><span>${name}</span><span>${where}</span></span>
    ${value ? html`<span class="val">${value}</span>` : html`<span class="val none">찾지 못했어요</span>`}
    ${f.check && !conf[k] ? html`<span class="why">${f.check}${f.suggestion ? ` 혹시 ${f.suggestion} 아닌가요?` : ''}</span>` : ''}
  </li>`;
}

async function fieldsScreen(id) {
  const r = await loadResult(id);
  if (!r) return null;
  const conf = state.confirmed[id] || {};
  const flagged = FIELD_VIEW.filter(([k]) => r.fields[k] && r.fields[k].check && !conf[k]).length;
  return html`<main class="screen">${topbar([`/result/${id}`, '결과로'])}
    <h1>종이에서 읽은 내용</h1>
    <p class="lead">종이에 적힌 칸 이름을 같이 적었어요. 종이와 하나씩 맞춰 보세요.</p>
    ${flagged ? html`<p class="attention" style="flex-direction:row;align-items:center"><span class="mark" aria-hidden="true">!</span>확인이 필요한 칸이 ${flagged}개 있어요</p>`
    : html`<p class="ok-note">${icon.check}<span>12개 항목이 서로 맞는지 확인했어요</span></p>`}
    ${state.photoUrl ? html`<button class="btn" type="button" data-action="toggle-photo" aria-expanded="${state.showPhoto}">${state.showPhoto ? '사진 접기' : '찍은 사진과 같이 보기'}</button>` : ''}
    ${state.photoUrl && state.showPhoto ? html`<img class="photo" src="${state.photoUrl}" alt="찍은 고지서 사진">` : ''}
    <ul class="fields">${FIELD_VIEW.map(([k, name, fmt]) => fieldRow(r.fields[k] || {}, conf, k, name, fmt))}</ul>
    ${r.notes && r.notes.length ? html`<p class="small muted">${r.notes.join(' ')}</p>` : ''}
    <div class="actions"><button class="btn" type="button" data-action="open-camera">다르게 읽혔다면 다시 찍기</button></div>
  </main>`;
}

// ---------- 화면 8: 법령 근거 ----------
async function lawScreen(id) {
  const r = await loadResult(id);
  if (!r) return null;
  return html`<main class="screen">${topbar([`/result/${id}`, '결과로'])}
    <h1>왜 그런지 법으로 보기</h1>
    <p class="lead">이 고지서에 해당하는 조항만 골랐어요.</p>
    ${r.citations.map((c) => {
    const open = state.openLaw.has(c.id);
    return html`<article class="card law">
        <span class="where">${c.law} ${c.article}</span>
        <strong>${c.plain}</strong>
        <button class="link-btn" type="button" data-action="toggle-law" data-id="${c.id}" aria-expanded="${open}">${open ? '원문 접기' : '원문 보기'}</button>
        ${open ? html`<p class="excerpt">${c.excerpt}</p>` : ''}
      </article>`;
  })}
    <p class="small muted">법 원문 전체는 <a href="https://www.law.go.kr" target="_blank" rel="noopener">국가법령정보센터</a>에서 볼 수 있어요.</p>
  </main>`;
}

// ---------- 화면 9: 다시 찍기·못 읽는 문서·오류 ----------
const ERRORS = {
  UNREADABLE: {
    blur: ['글자가 흐려서 읽기 어려워요', '숫자를 잘못 읽으면 마감일과 금액이 틀릴 수 있어서 선명한 사진이 필요해요.'],
    cut: ['종이 일부가 잘렸어요', '마감일과 계좌가 적힌 부분까지 사진에 들어와야 정확히 알려 드릴 수 있어요.'],
    glare: ['빛이 반사돼 글자가 안 보여요', '조명이 비치지 않게 각도를 조금 바꿔서 찍어 주세요.'],
  },
  UNSUPPORTED: ['아직 읽을 수 없는 문서예요', '지금은 주정차 위반 과태료 사전통지서만 읽을 수 있어요. 급하다면 문서에 적힌 문의처에 전화해 물어보세요.'],
  BAD_IMAGE: ['이 사진 형식은 읽을 수 없어요', '카메라로 다시 찍어 주세요.'],
  TOO_LARGE: ['사진이 너무 커요', '카메라로 다시 찍거나 다른 사진을 골라 주세요.'],
  TIMEOUT: ['판독이 오래 걸리고 있어요', '잠시 뒤 다시 시도해 주세요.'],
  NOT_FOUND: ['결과가 지워졌어요', '결과는 하루가 지나면 지워져요. 사진을 다시 찍어 주세요.'],
};

function errorView(code, reason) {
  let text = ERRORS[code] || ['잠시 뒤 다시 시도해 주세요', '인터넷 연결이나 서버에 문제가 생겼어요.'];
  if (code === 'UNREADABLE') text = ERRORS.UNREADABLE[reason] || ERRORS.UNREADABLE.blur;
  const photoProblem = ['UNREADABLE', 'BAD_IMAGE', 'TOO_LARGE'].includes(code);
  const canRetry = !photoProblem && !['UNSUPPORTED', 'NOT_FOUND'].includes(code) && state.file;
  let main;
  if (code === 'UNSUPPORTED') main = html`<button class="btn primary" type="button" data-action="open-album">다른 사진 고르기</button>`;
  else main = html`<button class="btn ${canRetry ? '' : 'primary'}" type="button" data-action="open-camera">${icon.camera}다시 찍기</button>`;
  return html`<main class="screen">${topbar(['/', '처음으로'])}
    <div class="illust">${code === 'UNSUPPORTED' ? otherDocIllust() : viewfinderIllust()}</div>
    <h1>${text[0]}</h1>
    <p class="lead">${text[1]}</p>
    ${code === 'UNREADABLE' ? html`<ul class="tips">${tip(icon.corners, '종이 전체가 들어오게', '조금 멀리서, 네 모서리가 보이게')}${tip(icon.sun, '밝은 곳에서, 그림자 없이', '손이나 휴대폰 그림자를 피해 주세요')}</ul>` : ''}
    <div class="actions">
      ${canRetry ? html`<button class="btn primary" type="button" data-action="read-photo">다시 시도하기</button>` : ''}
      ${main}
      <a class="btn" href="#/">처음으로</a>
    </div>
  </main>`;
}
function errorScreen(code) {
  return errorView(code, query().get('reason'));
}

// ---------- 사진 고르기·보내기 ----------
async function onFile(e) {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  if (state.photoUrl) URL.revokeObjectURL(state.photoUrl);
  Object.assign(state, { file, photoUrl: URL.createObjectURL(file), inspect: null, showPhoto: false });
  go('/confirm');
  try {
    state.inspect = await inspectImage(file);
  } catch {
    state.inspect = { error: true, issues: ['이 사진은 읽을 수 없는 형식이에요. 카메라로 다시 찍어 주세요.'] };
  }
  if (path() === '/confirm') rerender();
}

async function startReading(btn) {
  if (!state.file) {
    go('/');
    return;
  }
  btn.disabled = true;
  btn.textContent = '사진을 보내는 중…';
  try {
    const { blob } = await prepareImage(state.file);
    const a = await api.createAnalysis(blob);
    state.analyses.set(a.id, a);
    go(`/reading/${a.id}`);
  } catch (err) {
    go(`/error/${err.code || 'NETWORK'}`);
  }
}

function toggleBig() {
  const on = document.documentElement.classList.toggle('big');
  try { localStorage.setItem('hanjang.big', on ? '1' : '0'); } catch { /* 저장 못 해도 이번 화면에는 적용 */ }
  rerender();
}

// ---------- 이벤트 (한 곳에서 위임) ----------
$app.addEventListener('click', async (e) => {
  const el = e.target.closest('[data-action]');
  if (!el) return;
  const id = (path().match(/^\/result\/([\w-]+)/) || [])[1];
  const act = el.dataset.action;
  if (act === 'open-guide') go('/guide');
  else if (act === 'open-camera') { $camera.value = ''; $camera.click(); }
  else if (act === 'open-album') { $album.value = ''; $album.click(); }
  else if (act === 'read-photo') await startReading(el);
  else if (act === 'toggle-big') toggleBig();
  else if (act === 'copy') {
    toast((await copyText(el.dataset.value)) ? '계좌번호를 복사했어요' : '복사하지 못했어요. 번호를 길게 눌러 복사해 주세요.');
  } else if (act === 'speak') {
    const r = cachedResult(id);
    if (r && !speak(r.summary)) toast('이 휴대폰에서는 소리로 읽을 수 없어요');
  } else if (act === 'share') {
    const r = cachedResult(id);
    if (!r) return;
    const how = await shareText({ title: '과태료 안내', text: r.summary, url: location.href });
    if (how === 'copied') toast('내용과 링크를 복사했어요. 메신저에 붙여 넣으세요');
    else if (how === 'failed') toast('보내지 못했어요');
  } else if (act === 'tab') {
    state.tab = el.dataset.tab;
    rerender();
  } else if (act === 'toggle-photo') {
    state.showPhoto = !state.showPhoto;
    rerender();
  } else if (act === 'open-photo') {
    state.showPhoto = true;
    go(`/result/${id}/fields`);
  } else if (act === 'toggle-law') {
    const k = el.dataset.id;
    if (state.openLaw.has(k)) state.openLaw.delete(k);
    else state.openLaw.add(k);
    rerender();
  } else if (act === 'confirm') {
    state.confirmed[id] = { ...(state.confirmed[id] || {}), [el.dataset.field]: el.dataset.how };
    toast(el.dataset.how === 'suggestion' ? '확인한 값으로 바꿨어요' : '확인했어요');
    rerender();
  } else if (act === 'delete-record') {
    if (!window.confirm('이 결과를 지금 지울까요?')) return;
    try { await api.deleteAnalysis(id); } catch { /* 이미 지워졌으면 그대로 */ }
    state.analyses.delete(id);
    toast('결과를 지웠어요');
    go('/');
  }
});
$camera.addEventListener('change', onFile);
$album.addEventListener('change', onFile);
window.addEventListener('hashchange', () => render());

try {
  if (localStorage.getItem('hanjang.big') === '1') document.documentElement.classList.add('big');
} catch { /* 저장소를 못 쓰는 브라우저 */ }
if (!location.hash) history.replaceState(null, '', '#/');
render();
