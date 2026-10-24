-- 한장해결AI Supabase 스키마. SQL Editor 에 통째로 붙여 실행한다.
-- 서버는 service_role 키로만 접근한다 (RLS 를 켜고 공개 정책을 만들지 않음 = 브라우저 직접 접근 차단).

-- 1) 판독 결과: 사진은 저장하지 않고 결과 JSON 만 24시간 보관
create table if not exists public.analyses (
  id            uuid primary key,
  status        text not null check (status in ('processing', 'done', 'failed')),
  stage         text check (stage in ('reading', 'checking', 'planning', 'done')),
  result        jsonb,
  error_code    text,
  error_reason  text,
  error_message text,
  created_at    timestamptz not null default now(),
  expires_at    timestamptz not null default now() + interval '24 hours'
);
create index if not exists analyses_expires_at_idx on public.analyses (expires_at);
alter table public.analyses enable row level security;

-- 백엔드 서버에만 판독 결과 접근 권한 부여
grant select, insert, update, delete
on table public.analyses
to service_role;

-- 만료 정리 함수. 서버도 조회할 때 만료된 행을 지우지만, 아무도 안 연 결과까지 지우려면 예약 실행을 건다.
create or replace function public.purge_expired_analyses() returns void
language sql as $$
  delete from public.analyses where expires_at < now();
$$;
-- Database > Extensions 에서 pg_cron 을 켠 뒤 한 번 실행:
-- select cron.schedule('purge-analyses', '0 * * * *', 'select public.purge_expired_analyses()');

-- 2) (선택) 법령 조문: 지금은 backend/app/data/laws.json 을 메모리에서 쓴다.
--    법령이 수십 건으로 늘어 임베딩 검색이 필요해지면 이 표와 pgvector 를 쓴다.
create extension if not exists vector;
create table if not exists public.law_chunks (
  id         text primary key,
  law        text not null,
  article    text not null,
  title      text,
  excerpt    text,
  plain      text,
  source_url text,
  verified   boolean not null default false,
  embedding  vector(1536)   -- 쓰는 임베딩 모델의 차원으로 바꾼다
);
alter table public.law_chunks enable row level security;
