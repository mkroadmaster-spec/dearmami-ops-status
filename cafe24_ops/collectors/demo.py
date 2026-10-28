"""데모 데이터 생성기 — 실 자격증명 없이 대시보드 틀을 채운다 (CAFE24_OPS_MODE=demo).

업체 설정(config/metrics.yaml 의 category_groups, sources.yaml 의 brand/competitors)을 읽어
그 업체의 카테고리·상품·경쟁사 이름으로 생성한다. 날짜를 시드로 쓰므로 같은 날짜는 항상 같은 값.
"""
from __future__ import annotations

import random
from datetime import date as _date
from functools import lru_cache

from .. import config
from .base import Fact, fact

AD_CHANNELS = {"meta": 0.42, "naver_powerlink": 0.28, "naver_place": 0.05, "google": 0.15, "kakao": 0.10}
_CPC = {"meta": 650, "naver_powerlink": 900, "naver_place": 500, "google": 780, "kakao": 560}
_ROAS = {"meta": 3.4, "naver_powerlink": 4.8, "naver_place": 2.0, "google": 3.0, "kakao": 2.4}
_ADJ = ["베이직", "플레어", "와이드", "린넨", "코튼", "스트라이프", "크롭", "롱", "테이퍼드", "플리츠"]


@lru_cache(maxsize=1)
def products() -> list[tuple[str, str, str]]:
    """[(product_no, 상품명, 카테고리)] — 업체 category_groups 에서 생성 (최대 10개)."""
    groups = config.metrics().get("category_groups") or {"상의": ["티셔츠", "셔츠"], "하의": ["팬츠", "스커트"]}
    out: list[tuple[str, str, str]] = []
    i = 0
    for group, names in groups.items():
        for name in (names or [])[:2]:
            out.append((str(1001 + i), f"{_ADJ[i % len(_ADJ)]} {name}", name))
            i += 1
            if len(out) >= 10:
                return out
    return out or [("1001", "베이직 상품", "기타")]


def keywords() -> list[str]:
    brand = config.sources().get("brand", "브랜드")
    kws = [brand, f"{brand} 원피스", f"{brand} 후기"]
    kws += [f"{p[2]} 추천" for p in products()[:4]]
    return kws


def competitors() -> list[str]:
    return config.competitor_names() or ["경쟁사A", "경쟁사B"]


def _rng(d: str, salt: str) -> random.Random:
    return random.Random(f"{d}:{salt}")


def _day_factor(d: str) -> float:
    dt = _date.fromisoformat(d)
    wd = dt.weekday()
    base = 1.0 + (0.25 if wd in (4, 5) else 0.0) - (0.15 if wd == 1 else 0.0)
    base *= 1.0 + 0.1 * (1 - (dt.day - 1) / 30)  # 월초 상승
    return base


def cafe24(d: str) -> list[Fact]:
    r = _rng(d, "cafe24")
    f = _day_factor(d)
    orders = int(r.gauss(55, 9) * f)
    aov = r.gauss(52000, 6000)
    gross = orders * aov
    new_ratio = r.uniform(0.35, 0.5)
    mobile_ratio = r.uniform(0.68, 0.8)
    new_orders = round(orders * new_ratio)
    out = [
        fact(d, "cafe24", "gross_sales", gross),
        fact(d, "cafe24", "orders", orders),
        fact(d, "cafe24", "new_orders", new_orders),
        fact(d, "cafe24", "returning_orders", orders - new_orders),
        fact(d, "cafe24", "mobile_sales", gross * mobile_ratio),
        fact(d, "cafe24", "pc_sales", gross * (1 - mobile_ratio)),
        fact(d, "cafe24", "mobile_orders", round(orders * mobile_ratio)),
        fact(d, "cafe24", "pc_orders", orders - round(orders * mobile_ratio)),
        fact(d, "cafe24", "canceled_orders", int(r.uniform(0, 4))),
        fact(d, "cafe24", "reviews", int(r.uniform(2, 9))),
        fact(d, "cafe24", "new_sales", gross * new_ratio * r.uniform(0.9, 1.1)),
        fact(d, "cafe24", "returning_sales", gross * (1 - new_ratio * r.uniform(0.9, 1.1))),
        fact(d, "cafe24", "soldout_products", 38 + int(r.uniform(-3, 4))),
    ]
    prods = products()
    weights = [r.uniform(0.5, 1.5) for _ in prods]
    tot = sum(weights)
    for (no, name, cat), w in zip(prods, weights):
        out.append(fact(d, "cafe24", "product_sales", gross * w / tot, product_no=no, product=name, category=cat))
    return out


def cafe24_analytics(d: str) -> list[Fact]:
    r = _rng(d, "analytics")
    f = _day_factor(d)
    visits = int(r.gauss(2600, 300) * f)
    first = round(visits * r.uniform(0.55, 0.65))
    out = [
        fact(d, "cafe24_analytics", "visit_count", visits),
        fact(d, "cafe24_analytics", "first_visit_count", first),
        fact(d, "cafe24_analytics", "re_visit_count", visits - first),
    ]
    prods = products()
    stuck = prods[min(6, len(prods) - 1)][0]  # 한 상품은 '담을 수 없는 상태'(품절) 신호 — 담기 0
    for no, name, _cat in prods:
        views = int(r.gauss(170, 50) * f)
        carts = 0 if no == stuck else int(views * r.uniform(0.03, 0.12))
        out.append(fact(d, "cafe24_analytics", "product_views", views, product_no=no, product=name))
        out.append(fact(d, "cafe24_analytics", "product_cart_adds", carts, product_no=no, product=name))
    for kw in keywords():
        out.append(fact(d, "cafe24_analytics", "keyword_visits", int(r.uniform(5, 60)), keyword=kw))
    # 상품별 주문/수량 · 유입 도메인 · 광고채널 방문 · 페이지뷰 · 회원/비회원
    for no, name, _cat in prods:
        o = int(r.uniform(1, 9) * f)
        out.append(fact(d, "cafe24_analytics", "product_orders", o, product_no=no, product=name))
        out.append(fact(d, "cafe24_analytics", "product_qty", o + int(r.uniform(0, 3)), product_no=no, product=name))
    for dom, w in (("m.naver.com", 0.3), ("www.google.com", 0.18), ("l.instagram.com", 0.22), ("m.facebook.com", 0.1), ("direct", 0.2)):
        out.append(fact(d, "cafe24_analytics", "domain_visits", int(visits * w * r.uniform(0.8, 1.2)), domain=dom))
    for ch, w in (("네이버 검색광고", 0.35), ("메타 광고", 0.4), ("구글 광고", 0.15), ("카카오 광고", 0.1)):
        out.append(fact(d, "cafe24_analytics", "adpath_visits", int(visits * 0.45 * w * r.uniform(0.8, 1.2)), ad_channel=ch))
    for path, w in (("/", 0.3), ("/product/list.html?cate_no=24", 0.14), ("/product/detail.html?product_no=1001", 0.1),
                    ("/product/detail.html?product_no=1002", 0.08), ("/board/review/list.html", 0.06), ("/order/basket.html", 0.05)):
        out.append(fact(d, "cafe24_analytics", "page_views", int(visits * 3.5 * w * r.uniform(0.8, 1.2)), path=path))
    mo = int(r.uniform(0.55, 0.7) * 55 * f)
    out += [fact(d, "cafe24_analytics", "member_orders", mo, member_type="회원"),
            fact(d, "cafe24_analytics", "member_sales", mo * 54000, member_type="회원"),
            fact(d, "cafe24_analytics", "member_orders", int(55 * f) - mo, member_type="비회원"),
            fact(d, "cafe24_analytics", "member_sales", (int(55 * f) - mo) * 48000, member_type="비회원")]
    return out


def ga4(d: str) -> list[Fact]:
    r = _rng(d, "ga4")
    f = _day_factor(d)
    users = int(r.gauss(2300, 250) * f)  # 카페24 '방문'과 정의가 달라 숫자가 다른 게 정상
    new = round(users * r.uniform(0.6, 0.7))
    out = [
        fact(d, "ga4", "visitors", users),
        fact(d, "ga4", "sessions", int(users * r.uniform(1.15, 1.3))),
        fact(d, "ga4", "pageviews", int(users * r.uniform(3.2, 4.5))),
        fact(d, "ga4", "conversions", int(users * r.uniform(0.018, 0.028))),
        fact(d, "ga4", "new_visitors", new),
        fact(d, "ga4", "returning_visitors", users - new),
        fact(d, "ga4", "avg_session_sec", r.uniform(95, 160)),
    ]
    sess = int(users * 1.2)
    for sm, ch, w in (("naver / cpc", "naver_powerlink", 0.22), ("facebook / paid_social", "meta", 0.2), ("instagram / paid_social", "meta", 0.12),
                      ("google / cpc", "google", 0.1), ("google / organic", "other", 0.12), ("naver / organic", "other", 0.1),
                      ("(direct) / (none)", "other", 0.1), ("kakao / cpc", "kakao", 0.04)):
        n = int(sess * w * r.uniform(0.8, 1.2))
        conv = int(n * r.uniform(0.012, 0.03) * (1.3 if ch == "naver_powerlink" else 1))
        out += [fact(d, "ga4_channel", "sessions", n, source_medium=sm, channel=ch), fact(d, "ga4_channel", "users", int(n * 0.85), source_medium=sm, channel=ch),
                fact(d, "ga4_channel", "conversions", conv, source_medium=sm, channel=ch)]
    for path, w in (("/", 0.28), ("/product/list.html?cate_no=24", 0.12), ("/product/detail.html?product_no=1001", 0.1),
                    ("/product/detail.html?product_no=1003", 0.07), ("/board/review/list.html", 0.05), ("/order/basket.html", 0.05), ("/member/login.html", 0.04)):
        pv = int(users * 3.8 * w * r.uniform(0.8, 1.2))
        out += [fact(d, "ga4_page", "pageviews", pv, path=path), fact(d, "ga4_page", "users", int(pv * 0.6), path=path)]
    # 구매 퍼널 이벤트 — '상품 탐색' 단계가 병목이 되도록
    pv_total = int(users * 3.8)
    steps = [("page_view", pv_total), ("view_item", int(pv_total * r.uniform(0.28, 0.34))), ("click_buy_now", int(pv_total * r.uniform(0.012, 0.02))),
             ("add_to_cart", int(pv_total * r.uniform(0.035, 0.05))), ("view_cart", int(pv_total * r.uniform(0.025, 0.035))),
             ("begin_checkout", int(pv_total * r.uniform(0.016, 0.022))), ("purchase", int(users * r.uniform(0.018, 0.028)))]
    out += [fact(d, "ga4_event", "event_count", n, event=k) for k, n in steps]
    return out


def ads(d: str) -> list[Fact]:
    r = _rng(d, "ads")
    f = _day_factor(d)
    total_cost = r.gauss(620000, 60000) * f
    out: list[Fact] = []
    for ch, share in AD_CHANNELS.items():
        cost = total_cost * share * r.uniform(0.85, 1.15)
        clicks = cost / _CPC[ch]
        ctr = r.uniform(0.008, 0.02)
        out += [
            fact(d, "ads", "ad_cost", cost, channel=ch),
            fact(d, "ads", "impressions", clicks / ctr, channel=ch),
            fact(d, "ads", "clicks", clicks, channel=ch),
            fact(d, "ads", "conversions", clicks * r.uniform(0.012, 0.03), channel=ch),
            fact(d, "ads", "ad_revenue", cost * _ROAS[ch] * r.uniform(0.8, 1.2), channel=ch),
        ]
    return out


def competitor(d: str) -> list[Fact]:
    r = _rng(d, "competitor")
    return [fact(d, "competitor", "trend_ratio", r.uniform(20, 90), brand=b) for b in competitors()]


_CREATIVES = [("c1", "가을 신상 원피스 15초", "브랜드 캠페인"), ("c2", "베스트 3종 캐러셀", "베스트 리타겟팅"), ("c3", "후기 리뷰 영상", "브랜드 캠페인"),
              ("c4", "주말 특가 배너", "프로모션"), ("c5", "니트 코디 이미지", "신상 론칭"), ("c6", "사이즈 가이드 안내", "신상 론칭")]


def _thumb(seed: str) -> str:
    """데모 썸네일 — 색 블록 SVG data URI (외부 이미지 없이)."""
    import base64
    hue = (sum(ord(c) for c in seed) * 37) % 360
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160"><rect width="160" height="160" fill="hsl({hue},45%,70%)"/><rect x="24" y="24" width="112" height="80" rx="6" fill="hsl({hue},40%,55%)"/><rect x="24" y="116" width="80" height="12" rx="3" fill="hsl({hue},30%,40%)"/></svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def creative(d: str) -> list[Fact]:
    r = _rng(d, "creative")
    f = _day_factor(d)
    out: list[Fact] = []
    age = (_date.fromisoformat(d) - _date(2026, 9, 1)).days
    for i, (cid, name, camp) in enumerate(_CREATIVES):
        cost = r.gauss(45000, 9000) * f * (1.4 if i < 2 else 0.8)
        fatigue = max(0.4, 1 - age * (0.012 if i == 0 else 0.004))  # 첫 소재는 피로도 누적(CTR 하락, 빈도 상승)
        clicks = cost / r.uniform(550, 750) * fatigue
        impr = clicks / (r.uniform(0.01, 0.018) * fatigue)
        dims = {"ad_id": cid, "ad_name": name, "campaign": camp, "adset": f"{camp} 세트", "thumbnail_url": _thumb(cid)}
        out += [fact(d, "creative", "ad_cost", cost, **dims), fact(d, "creative", "impressions", impr, **dims),
                fact(d, "creative", "clicks", clicks, **dims), fact(d, "creative", "conversions", clicks * r.uniform(0.012, 0.03), **dims),
                fact(d, "creative", "ad_revenue", cost * r.uniform(2.2, 4.2), **dims),
                fact(d, "creative", "reach", impr / (1.2 + (1 - fatigue) * 3), **dims),
                fact(d, "creative", "frequency", 1.2 + (1 - fatigue) * 3, **dims)]
    return out


def naver_keyword(d: str) -> list[Fact]:
    r = _rng(d, "nkw")
    f = _day_factor(d)
    brand = config.sources().get("brand", "브랜드")
    kws = [(brand, "브랜드", "브랜드 캠페인"), (f"{brand} 원피스", "브랜드", "브랜드 캠페인")] + \
          [(f"{p[2]} 추천", p[2], "파워링크 일반") for p in products()[:6]] + [("중년 여성 의류", "일반", "파워링크 일반"), ("40대 원피스", "일반", "파워링크 일반")]
    out: list[Fact] = []
    for i, (kw, grp, camp) in enumerate(kws):
        cost = r.gauss(18000, 5000) * f * (1.6 if i < 2 else 1)
        clicks = cost / r.uniform(700, 1100)
        dims = {"keyword_id": f"nkw-{i}", "keyword": kw, "adgroup": grp, "campaign": camp}
        out += [fact(d, "naver_keyword", "ad_cost", cost, **dims), fact(d, "naver_keyword", "impressions", clicks / r.uniform(0.01, 0.03), **dims),
                fact(d, "naver_keyword", "clicks", clicks, **dims), fact(d, "naver_keyword", "conversions", clicks * r.uniform(0.02, 0.05), **dims),
                fact(d, "naver_keyword", "ad_revenue", cost * r.uniform(3, 6), **dims)]
    for j, grp in enumerate(("플레이스 본점", "플레이스 쇼룸")):
        cost = r.gauss(12000, 3000) * f
        clicks = cost / 500
        dims = {"adgroup_id": f"grp-p{j}", "adgroup": grp, "campaign": "플레이스 캠페인"}
        out += [fact(d, "naver_place", "ad_cost", cost, **dims), fact(d, "naver_place", "impressions", clicks / 0.02, **dims),
                fact(d, "naver_place", "clicks", clicks, **dims), fact(d, "naver_place", "conversions", clicks * 0.02, **dims),
                fact(d, "naver_place", "ad_revenue", cost * 2, **dims)]
    return out
