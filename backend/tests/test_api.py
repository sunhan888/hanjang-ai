import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (800, 1100), "white").save(buf, "JPEG")
    return buf.getvalue()


def test_health():
    body = client.get("/api/health").json()
    assert body["ok"] and body["provider"] == "mock" and body["today"] == "2026-10-20"


def test_upload_poll_delete():
    res = client.post("/api/analyses", files={"image": ("n.jpg", jpeg_bytes(), "image/jpeg")})
    assert res.status_code == 202
    aid = res.json()["id"]
    # TestClient 는 응답 뒤 백그라운드 작업까지 끝낸다
    body = client.get(f"/api/analyses/{aid}").json()
    assert body["status"] == "done" and body["stage"] == "done"
    assert body["result"]["dday"]["days_left"] == 14
    assert body["result"]["fields"]["감경과태료"]["value"] == 96000
    assert client.delete(f"/api/analyses/{aid}").status_code == 204
    assert client.get(f"/api/analyses/{aid}").status_code == 404


def test_bad_image_and_not_found():
    res = client.post("/api/analyses", files={"image": ("x.jpg", b"not an image", "image/jpeg")})
    assert res.status_code == 415 and res.json()["detail"]["code"] == "BAD_IMAGE"
    assert client.get("/api/analyses/not-a-uuid").status_code == 404


def test_frontend_is_served():
    res = client.get("/")
    assert res.status_code == 200 and "한장해결" in res.text
