"""테스트 공통 설정: LLM 없이(mock), 오늘 날짜 고정, 메모리 저장소."""
import os
import sys
from pathlib import Path

os.environ["LLM_PROVIDER"] = "mock"
os.environ["MOCK_DELAY_SEC"] = "0"
os.environ["TODAY"] = "2026-10-20"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["AGENT_LLM_POLISH"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
