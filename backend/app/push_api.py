
"""한장해결AI 2.0 - 웹 푸시 테스트 API"""

import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from pywebpush import WebPushException, webpush

# 로컬 개발 시에만 .env 파일에서 환경변수 읽기
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

router = APIRouter(prefix="/api/push", tags=["push"])

# 테스트 전용 임시 저장소
# 서버가 재시작되면 구독 정보가 사라짐
subscriptions = {}


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    endpoint: str
    keys: PushKeys


@router.get("/public-key")
def get_public_key():
    key = os.getenv("VAPID_PUBLIC_KEY")

    if not key:
        raise HTTPException(
            status_code=503,
            detail="VAPID public key is not configured"
        )

    return {"publicKey": key}


@router.post("/subscribe")
def subscribe(subscription: PushSubscription):
    """아이폰에서 생성한 푸시 구독 정보 등록"""

    parsed = urlparse(subscription.endpoint)
    host = parsed.hostname or ""

    # 알려진 브라우저 푸시 서비스만 허용
    allowed = (
        host in {
            "fcm.googleapis.com",
            "updates.push.services.mozilla.com",
        }
        or host.endswith(".push.apple.com")
    )

    if (
        parsed.scheme != "https"
        or not allowed
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or len(subscription.endpoint) > 2048
        or not 30 <= len(subscription.keys.p256dh) <= 300
        or not 10 <= len(subscription.keys.auth) <= 100
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid push subscription"
        )

    if len(subscriptions) >= 20:
        raise HTTPException(
            status_code=503,
            detail="Test subscription limit reached"
        )

    subscription_id = secrets.token_urlsafe(24)

    subscriptions[subscription_id] = {
        "data": {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.keys.p256dh,
                "auth": subscription.keys.auth,
            },
        },
        "sent": 0,
    }

    return {
        "ok": True,
        "subscription_id": subscription_id
    }


@router.post("/test/{subscription_id}")
def test_push(
    subscription_id: str,
    x_push_test_key: str | None = Header(default=None),
):
    """관리자 인증 후 등록된 기기에 테스트 푸시 발송"""

    expected = os.getenv("PUSH_TEST_KEY")

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Push test is not configured"
        )

    if not x_push_test_key or not secrets.compare_digest(
        x_push_test_key, expected
    ):
        raise HTTPException(
            status_code=403,
            detail="Forbidden"
        )

    record = subscriptions.get(subscription_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found"
        )

    if record["sent"] >= 3:
        raise HTTPException(
            status_code=429,
            detail="Test limit reached"
        )

    private_key = os.getenv("VAPID_PRIVATE_KEY")

    if not private_key:
        raise HTTPException(
            status_code=503,
            detail="VAPID private key is not configured"
        )

    # 테스트 횟수 제한
    record["sent"] += 1

    try:
        webpush(
            subscription_info=record["data"],
            data=json.dumps({
                "url": "/"
            }),
            vapid_private_key=private_key,
            vapid_claims={
                "sub": "https://hanjang-ai-v2.onrender.com"
            },
            ttl=60,
            timeout=10,
        )
    except WebPushException:
        raise HTTPException(
            status_code=502,
            detail="Push service rejected the request"
        )

    return {"ok": True, "message": "Push request sent"}
