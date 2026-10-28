"""대시보드 비밀번호 보호 (서버 버전).

환경변수 DASHBOARD_PASSWORD 가 비어 있으면 보호 없음. 설정되면:
- GET /login 로그인 화면, POST /login 검증 → 30일 서명 쿠키
- 그 외 경로(/health 제외)는 쿠키 없으면 HTML → /login 리다이렉트, /api → 401
- 자동화용: 헤더 X-Dashboard-Password 로도 통과 (api-smoke 워크플로)
비밀번호 자체는 저장하지 않고 PBKDF2 해시 + HMAC 서명만 사용한다.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from cafe24_ops import config

COOKIE = "ops_auth"
MAX_AGE = 60 * 60 * 24 * 30


def _password() -> str:
    return config.env("DASHBOARD_PASSWORD")


def _secret() -> bytes:
    # 비밀번호에서 파생한 서버 비밀 (비밀번호가 바뀌면 모든 쿠키 무효)
    return hashlib.pbkdf2_hmac("sha256", _password().encode(), b"cafe24-ops-status", 50_000)


def _token(exp: int) -> str:
    sig = hmac.new(_secret(), str(exp).encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def _valid(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    exp, sig = token.split(".", 1)
    try:
        if int(exp) < time.time():
            return False
    except ValueError:
        return False
    return hmac.compare_digest(hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest(), sig)


def check_password(pw: str) -> bool:
    return bool(_password()) and hmac.compare_digest(pw.encode(), _password().encode())


LOGIN_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand} 운영 대시보드 — 로그인</title><style>
:root{{color-scheme:light dark}} body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#16213a;font:15px/1.5 -apple-system,"Pretendard","Apple SD Gothic Neo",system-ui,sans-serif}}
.box{{background:#fff;color:#0f172a;border-radius:14px;padding:28px 28px 22px;width:min(92vw,360px);box-shadow:0 10px 40px rgba(0,0,0,.3)}}
h1{{font-size:18px;margin:0 0 4px}} p{{margin:0 0 16px;color:#64748b;font-size:13px}}
input{{width:100%;box-sizing:border-box;font:inherit;padding:10px 12px;border:1px solid #cbd5e1;border-radius:8px;margin-bottom:10px}}
button{{width:100%;font:inherit;font-weight:700;padding:10px;border:0;border-radius:8px;background:#2a78d6;color:#fff;cursor:pointer}}
.err{{color:#d12f2f;font-size:13px;margin:0 0 8px}}
</style></head><body><form class="box" method="post" action="/login"><h1>{brand} 운영 대시보드</h1><p>비밀번호를 입력하세요</p>
{err}<input type="password" name="password" placeholder="비밀번호" autofocus autocomplete="current-password"><input type="hidden" name="next" value="{next}">
<button type="submit">들어가기</button></form></body></html>"""


def login_page(next_url: str = "/", err: str = "") -> HTMLResponse:
    brand = html.escape(config.sources().get("brand", ""))
    e = f'<p class="err">{html.escape(err)}</p>' if err else ""
    return HTMLResponse(LOGIN_HTML.format(brand=brand, err=e, next=html.escape(next_url or "/")))


class PasswordMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _password():
            return await call_next(request)
        path = request.url.path
        if path in ("/health", "/login") or path.startswith("/static/"):
            return await call_next(request)
        if _valid(request.cookies.get(COOKIE)):
            return await call_next(request)
        hdr = request.headers.get("x-dashboard-password")
        if hdr and check_password(hdr):
            return await call_next(request)
        if path.startswith("/api/"):
            return JSONResponse({"error": "로그인이 필요합니다", "login": "/login"}, status_code=401)
        return RedirectResponse(f"/login?next={path}", status_code=302)


def set_cookie(resp: Response) -> Response:
    exp = int(time.time()) + MAX_AGE
    resp.set_cookie(COOKIE, _token(exp), max_age=MAX_AGE, httponly=True, samesite="lax", secure=False)
    return resp
