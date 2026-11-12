"""구글 애즈 소재 구조 진단 — 캠페인/광고 유형별 비중, 소재 이미지 조회 가능 여부. 금액은 비중(%)만 출력."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cafe24_ops.clients.ads_google import GoogleAdsClient  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402

g = GoogleAdsClient(Store())


def run(title: str, q: str, fn) -> None:
    print(f"\n===== {title} =====")
    try:
        rows = g.search(q)
        print("rows:", len(rows))
        fn(rows)
    except Exception as e:  # noqa: BLE001
        print("ERROR", str(e)[:600])


def share(rows, keyf):
    c = defaultdict(float)
    for r in rows:
        c[keyf(r)] += float(r.get("metrics", {}).get("costMicros", 0))
    tot = sum(c.values()) or 1
    for k, v in sorted(c.items(), key=lambda x: -x[1]):
        print(f"  {k:<55} 비용비중 {v / tot * 100:5.1f}%")


run("캠페인 유형 (최근 7일)", "SELECT campaign.advertising_channel_type, campaign.advertising_channel_sub_type, metrics.cost_micros "
    "FROM campaign WHERE segments.date DURING LAST_7_DAYS AND metrics.impressions > 0",
    lambda rows: share(rows, lambda r: f"{r['campaign'].get('advertisingChannelType')}/{r['campaign'].get('advertisingChannelSubType', '')}"))
run("광고 유형 (ad_group_ad, 최근 7일)", "SELECT ad_group_ad.ad.type, metrics.cost_micros FROM ad_group_ad "
    "WHERE segments.date DURING LAST_7_DAYS AND metrics.impressions > 0",
    lambda rows: share(rows, lambda r: r["adGroupAd"]["ad"].get("type")))
run("광고 1건 원본 키", "SELECT ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.ad.type, ad_group_ad.ad.image_ad.image_url, "
    "metrics.impressions FROM ad_group_ad WHERE segments.date DURING LAST_7_DAYS AND metrics.impressions > 0",
    lambda rows: [print("  ", json.dumps(r, ensure_ascii=False)[:400]) for r in rows[:3]])
run("광고-애셋 연결 (ad_group_ad_asset_view)", "SELECT ad_group_ad_asset_view.ad_group_ad, ad_group_ad_asset_view.field_type, asset.type, "
    "asset.image_asset.full_size.url, asset.youtube_video_asset.youtube_video_id FROM ad_group_ad_asset_view "
    "WHERE ad_group_ad_asset_view.enabled = TRUE",
    lambda rows: (print("  field_type:", Counter(r["adGroupAdAssetView"].get("fieldType") for r in rows).most_common(12)),
                  print("  asset.type:", Counter(r["asset"].get("type") for r in rows).most_common(8)),
                  [print("  ", json.dumps(r, ensure_ascii=False)[:400]) for r in rows[:3]]))
run("실적 최대화 애셋그룹 (asset_group, 최근 7일)", "SELECT asset_group.id, asset_group.name, metrics.cost_micros, metrics.impressions "
    "FROM asset_group WHERE segments.date DURING LAST_7_DAYS AND metrics.impressions > 0",
    lambda rows: print("  asset groups:", len(rows)))
run("애셋그룹-이미지 (asset_group_asset)", "SELECT asset_group.id, asset_group_asset.field_type, asset.type, asset.image_asset.full_size.url, "
    "asset.youtube_video_asset.youtube_video_id FROM asset_group_asset WHERE asset_group_asset.status = 'ENABLED'",
    lambda rows: print("  field_type:", Counter(r["assetGroupAsset"].get("fieldType") for r in rows).most_common(12)))
