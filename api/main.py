"""FastAPI — kpi_daily/facts 를 읽어 대시보드에 서빙. 실행: uvicorn api.main:app --reload"""
from __future__ import annotations

from datetime import date as _date, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from api import auth
from cafe24_ops import config, report_docx
from cafe24_ops.alerts import digest
from cafe24_ops.collectors import channel_status
from cafe24_ops.etl import breakdown, period_report
from cafe24_ops.etl.aggregate import compare, derive, previous_range, sum_range
from cafe24_ops.store import Store

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dashboard"

app = FastAPI(title="cafe24-ops-status", version="0.3.0")
app.add_middleware(auth.PasswordMiddleware)  # DASHBOARD_PASSWORD 설정 시 로그인 요구
_store: Store | None = None


@app.get("/login")
def login_get(next: str = "/") -> Response:
    if not auth._password():
        return RedirectResponse("/", status_code=302)
    return auth.login_page(next)


@app.post("/login")
def login_post(password: str = Form(""), next: str = Form("/")) -> Response:
    if not auth.check_password(password):
        return auth.login_page(next, "비밀번호가 맞지 않습니다")
    return auth.set_cookie(RedirectResponse(next if next.startswith("/") else "/", status_code=303))


@app.get("/logout")
def logout() -> Response:
    r = RedirectResponse("/login", status_code=302)
    r.delete_cookie(auth.COOKIE)
    return r


def store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def _range(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    mn, mx = store().date_bounds()
    if not date_to:
        date_to = mx or _date.today().isoformat()
    if not date_from:
        date_from = (_date.fromisoformat(date_to) - timedelta(days=13)).isoformat()
    if date_from > date_to:
        raise HTTPException(422, "from > to")
    return date_from, date_to


F = Query(None, alias="from")
T = Query(None, alias="to")
CF = Query(None, alias="cmp_from")
CT = Query(None, alias="cmp_to")


def _cmp(f: str, t: str, cf: str | None, ct: str | None) -> tuple[str, str]:
    """비교기간: 지정 없으면 직전 동일 길이."""
    if cf and ct and cf <= ct:
        return cf, ct
    return previous_range(f, t)


@app.get("/health")
def health() -> dict[str, Any]:
    s = store()
    mn, mx = s.date_bounds()
    return {"ok": True, "db": "postgres" if s.is_pg else "sqlite", "mode": s.kv_get("data_mode") or config.mode(),
            "last_run_at": s.kv_get("last_run_at"), "dates": {"min": mn, "max": mx},
            "ga4_creds": bool(config.env("GOOGLE_APPLICATION_CREDENTIALS_JSON")), "ga4_property": bool(config.env("GA4_PROPERTY_ID")),
            "channels": {c["key"]: c["configured"] for c in channel_status(s)}}


@app.get("/api/config")
def api_config() -> dict[str, Any]:
    src = config.sources()
    s = store()
    return {"brand": src.get("brand"), "client_id": src.get("client_id"), "site_url": src.get("site_url"),
            "mall_id": src["shop"].get("mall_id"), "platform": src["shop"].get("platform"),
            "lead_gen": bool(src.get("lead_gen")), "mode": s.kv_get("data_mode") or config.mode(),
            "metrics": config.metrics(), "last_run_at": s.kv_get("last_run_at")}


@app.get("/api/dates")
def api_dates() -> dict[str, Any]:
    mn, mx = store().date_bounds()
    return {"min": mn, "max": mx}


@app.get("/api/channels")
def api_channels() -> list[dict[str, Any]]:
    return channel_status(store())


@app.get("/api/summary")
def api_summary(date_from: str | None = F, date_to: str | None = T, cf: str | None = CF, ct: str | None = CT) -> dict[str, Any]:
    f, t = _range(date_from, date_to)
    pf, pt = _cmp(f, t, cf, ct)
    s = store()
    cur, prev = sum_range(s.kpi_range(f, t)), sum_range(s.kpi_range(pf, pt))
    # 누적 매출 vs 목표 페이스 (월 목표 → 일할)
    target = float((config.metrics().get("targets") or {}).get("monthly_sales") or 0)
    daily_target = target / 30 if target else None
    return {"range": {"from": f, "to": t}, "prev_range": {"from": pf, "to": pt}, "cur": cur, "prev": prev, "compare": compare(cur, prev),
            "target": {"monthly_sales": target, "daily": daily_target}}


@app.get("/api/period-comparison")
def api_period_comparison(date: str | None = None) -> dict[str, Any]:
    if not date:
        date = store().date_bounds()[1] or _date.today().isoformat()
    return breakdown.period_comparison(store(), date)


@app.get("/api/daily")
def api_daily(date_from: str | None = F, date_to: str | None = T) -> list[dict[str, Any]]:
    f, t = _range(date_from, date_to)
    return [{"date": d, **derive(k)} for d, k in sorted(store().kpi_range(f, t).items())]


@app.get("/api/digest")
def api_digest(date: str | None = None) -> dict[str, Any]:
    if not date:
        date = store().date_bounds()[1] or _date.today().isoformat()
    return digest(store(), date)


@app.get("/api/breakdown")
def api_breakdown(date_from: str | None = F, date_to: str | None = T) -> dict[str, Any]:
    f, t = _range(date_from, date_to)
    s = store()
    return {"categories": breakdown.category_sales(s, f, t), "best": breakdown.best_products(s, f, t)}


@app.get("/api/shop/analytics")
def api_shop_analytics(date_from: str | None = F, date_to: str | None = T, cf: str | None = CF, ct: str | None = CT) -> dict[str, Any]:
    f, t = _range(date_from, date_to)
    pf, pt = _cmp(f, t, cf, ct)
    return breakdown.shop_analytics(store(), f, t, pf, pt)


@app.get("/api/ads/channels")
def api_ads_channels(date_from: str | None = F, date_to: str | None = T, cf: str | None = CF, ct: str | None = CT) -> dict[str, Any]:
    f, t = _range(date_from, date_to)
    pf, pt = _cmp(f, t, cf, ct)
    s = store()
    cur = breakdown.ads_by_channel(s, f, t)
    prev = {r["channel"]: r for r in breakdown.ads_by_channel(s, pf, pt)}
    total = sum((r["ad_cost"] or 0) for r in cur) or 1
    for r in cur:
        p = prev.get(r["channel"], {})
        r["prev_ad_cost"], r["prev_roas"], r["prev_ad_conversions"] = p.get("ad_cost"), p.get("roas"), p.get("ad_conversions")
        r["budget_share"] = (r["ad_cost"] or 0) / total * 100
    return {"range": {"from": f, "to": t}, "prev_range": {"from": pf, "to": pt}, "channels": cur,
            "detail": breakdown.channel_detail(s, f, t, pf, pt),
            "trend": breakdown.ads_trend(s, f, t, "ad_cost"), "conv_trend": breakdown.ads_trend(s, f, t, "conversions")}


@app.get("/api/ads/keywords")
def api_ads_keywords(date_from: str | None = F, date_to: str | None = T, channel: str = "naver_powerlink",
                     sort: str = "ad_cost") -> dict[str, Any]:
    f, t = _range(date_from, date_to)
    if channel == "naver_place":
        return {"range": {"from": f, "to": t}, "rows": breakdown.place_report(store(), f, t)}
    if sort not in ("ad_cost", "ad_clicks", "ad_impressions", "ad_conversions", "roas", "ctr"):
        sort = "ad_cost"
    rows = breakdown.keyword_report(store(), f, t, sort=sort, top=300)
    cost = sum(r["ad_cost"] or 0 for r in rows); impr = sum(r["ad_impressions"] or 0 for r in rows); clicks = sum(r["ad_clicks"] or 0 for r in rows)
    return {"range": {"from": f, "to": t}, "rows": rows,
            "kpi": {"keywords": len(rows), "ad_cost": cost, "ad_impressions": impr, "ad_clicks": clicks,
                    "ctr": clicks / impr * 100 if impr else None, "cpc": cost / clicks if clicks else None}}


@app.get("/api/creatives/overview")
def api_creatives(date_from: str | None = F, date_to: str | None = T) -> dict[str, Any]:
    f, t = _range(date_from, date_to)
    rows = breakdown.creatives_overview(store(), f, t)
    cost = sum(r["ad_cost"] or 0 for r in rows); conv = sum(r["ad_conversions"] or 0 for r in rows)
    clicks = sum(r["ad_clicks"] or 0 for r in rows); impr = sum(r["ad_impressions"] or 0 for r in rows)
    best = max(rows, key=lambda r: (r["ad_conversions"] or 0, r["roas"] or 0), default=None)
    return {"range": {"from": f, "to": t}, "rows": rows,
            "kpi": {"live": len(rows), "ad_cost": cost, "ad_conversions": conv, "cpa": cost / conv if conv else None,
                    "ctr": clicks / impr * 100 if impr else None, "cvr": conv / clicks * 100 if clicks else None,
                    "best": {"ad_name": best["ad_name"], "roas": best["roas"], "ad_conversions": best["ad_conversions"]} if best else None}}


@app.get("/api/creatives/trend")
def api_creatives_trend(date_from: str | None = F, date_to: str | None = T) -> dict[str, Any]:
    f, t = _range(date_from, date_to)
    return breakdown.creative_trend(store(), f, t)


@app.get("/api/ga4/site")
def api_ga4_site(date_from: str | None = F, date_to: str | None = T, cf: str | None = CF, ct: str | None = CT) -> dict[str, Any]:
    f, t = _range(date_from, date_to)
    pf, pt = _cmp(f, t, cf, ct)
    s = store()
    return {**breakdown.ga4_site(s, f, t, pf, pt), "channels": breakdown.ga4_channels(s, f, t), "pages": breakdown.ga4_pages(s, f, t),
            "funnel": breakdown.ga4_funnel(s, f, t)}


@app.get("/api/competitors/directory")
def api_competitors_directory() -> list[dict[str, Any]]:
    return breakdown.competitor_directory()


@app.get("/api/competitors/trend")
def api_competitors(date_from: str | None = F, date_to: str | None = T) -> dict[str, Any]:
    f, t = _range(date_from, date_to)
    return breakdown.competitor_trend(store(), f, t)


@app.get("/api/report/weekly")
def api_report_weekly(week: str | None = None) -> dict[str, Any]:
    return period_report.weekly_report(store(), week)


@app.get("/api/report/weekly.docx")
def api_report_weekly_docx(week: str | None = None) -> Response:
    data = period_report.weekly_report(store(), week)
    name = f"weekly-report-{data['range']['from']}.docx"
    return Response(report_docx.build(data), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/report/monthly")
def api_report_monthly(month: str | None = None) -> dict[str, Any]:
    return period_report.monthly_report(store(), month)


@app.get("/api/report/monthly.docx")
def api_report_monthly_docx(month: str | None = None) -> Response:
    data = period_report.monthly_report(store(), month)
    name = f"monthly-report-{data['range']['from'][:7]}.docx"
    return Response(report_docx.build(data), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/logs")
def api_logs(limit: int = 50) -> list[dict[str, Any]]:
    return store().recent_logs(limit)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(DASH / "index.html")


app.mount("/static", StaticFiles(directory=str(DASH)), name="static")


@app.exception_handler(Exception)
async def _err(_, exc: Exception) -> JSONResponse:  # 화면에 원인 표시 (빈 화면 방지)
    return JSONResponse(status_code=500, content={"error": f"{type(exc).__name__}: {exc}"})
