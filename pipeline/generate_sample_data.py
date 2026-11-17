"""
Generate realistic sample ad-platform data for a fictional marketing agency.

Real ad APIs (Meta, Google Ads, TikTok) need live client accounts, so this
script produces raw JSON files shaped like each platform's API response.
Each platform returns data differently on purpose, which is exactly the
problem the pipeline solves:

  * Meta       -> numbers as strings, purchases nested in an `actions` list
  * Google Ads -> camelCase nested objects, cost in micros (1,000,000 = $1)
  * TikTok     -> dimensions/metrics split, timestamps instead of dates

The data also contains seeded problems the pipeline should catch:
  * a duplicate re-pull of one day (Meta)
  * a missing day of data (TikTok)
  * a row where clicks > impressions
  * a row with a missing campaign name
  * a conversion-tracking outage (Google, spend but ~0 conversions)
  * a creative-fatigue spike (Meta, spend up, cost per purchase way up)

All companies, campaigns and numbers are fictional.

Usage:
    python pipeline/generate_sample_data.py --out data/raw --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

START = date(2026, 8, 17)  # Monday
DAYS = 91                  # 13 full weeks, ends Sunday 2026-11-15
END = START + timedelta(days=DAYS - 1)

# Fictional agency clients. aov = average order value in USD.
CLIENTS = {
    "larkspur_coffee": {"name": "Larkspur Coffee", "aov": 38},
    "hollowpine_outfitters": {"name": "Hollowpine Outfitters", "aov": 112},
    "brindle_bone_pets": {"name": "Brindle & Bone Pet Supply", "aov": 54},
    "mesa_glow_skincare": {"name": "Mesa Glow Skincare", "aov": 67},
}

# Baseline behaviour per platform: cost per 1,000 impressions, click-through
# rate, and conversion rate (purchases / clicks).
PLATFORM_BASE = {
    "meta": {"cpm": 11.5, "ctr": 0.011, "cvr": 0.028},
    "google": {"cpm": 24.0, "ctr": 0.035, "cvr": 0.041},
    "tiktok": {"cpm": 7.5, "ctr": 0.008, "cvr": 0.017},
}

CAMPAIGNS = {
    "meta": [("Prospecting - Broad", ["Advantage+ Audience", "Lookalike 1%"]),
             ("Retargeting - 30 Day", ["Site Visitors", "Add to Cart"])],
    "google": [("Search - Brand", ["Brand Exact"]),
               ("Search - Non-Brand", ["Category Terms", "Competitor Terms"]),
               ("Performance Max", ["All Products"])],
    "tiktok": [("Spark Ads - UGC", ["Interest Stack", "Broad 18-44"]),
               ("Retargeting - Video Viewers", ["Viewed 50%+"])],
}

# Weekday multipliers, Monday first. Weekends run a little hotter.
WEEKDAY = [0.95, 0.97, 0.98, 1.0, 1.04, 1.08, 1.06]


def noisy(value: float, rng: random.Random, spread: float = 0.12) -> float:
    return max(0.0, value * rng.gauss(1.0, spread))


_BUDGETS: dict[tuple, float] = {}


def daily_budget(platform, client, campaign, group, is_retargeting) -> float:
    """Each ad group gets one stable daily budget, like a real account."""
    key = (platform, client, campaign, group)
    if key not in _BUDGETS:
        r = random.Random("|".join(key))
        _BUDGETS[key] = r.uniform(15, 60) if is_retargeting else r.uniform(40, 160)
    return _BUDGETS[key]


def simulate_day(rng, platform, client, campaign, group, day_idx, d):
    """Return (impressions, clicks, spend, purchases, revenue) for one ad group-day."""
    base = PLATFORM_BASE[platform]
    is_retargeting = "Retargeting" in campaign or "Brand" in campaign
    budget = daily_budget(platform, client, campaign, group, is_retargeting)
    trend = 1 + 0.004 * day_idx  # budgets slowly scale up over the quarter
    spend = noisy(budget * trend * WEEKDAY[d.weekday()], rng)

    cvr = base["cvr"] * (1.8 if is_retargeting else 1.0)
    ctr = base["ctr"] * (1.4 if is_retargeting else 1.0)

    # --- Seeded anomalies (final week) -------------------------------------
    last_week = d > END - timedelta(days=7)
    if platform == "meta" and client == "hollowpine_outfitters" \
            and campaign.startswith("Prospecting") and d > END - timedelta(days=5):
        spend *= 2.5   # budget pushed up...
        cvr *= 0.45    # ...while the creative stopped converting
    if platform == "google" and client == "mesa_glow_skincare" \
            and END - timedelta(days=3) < d <= END:
        cvr *= 0.03    # conversion tag broke: spend continues, purchases vanish
    if platform == "tiktok" and client == "larkspur_coffee" and last_week:
        cvr *= 1.7     # new UGC creative is working

    impressions = int(spend / noisy(base["cpm"], rng, 0.08) * 1000)
    clicks = int(impressions * noisy(ctr, rng, 0.15))
    purchases = int(round(clicks * noisy(cvr, rng, 0.25)))
    revenue = round(sum(noisy(CLIENTS[client]["aov"], rng, 0.3) for _ in range(purchases)), 2)
    return impressions, clicks, round(spend, 2), purchases, revenue


# --- Platform-specific record shapes ----------------------------------------

def meta_record(client, campaign, adset, d, imp, clk, spend, purch, rev):
    return {
        "account_name": CLIENTS[client]["name"],
        "campaign_name": campaign,
        "adset_name": adset,
        "date_start": d.isoformat(),
        "date_stop": d.isoformat(),
        "impressions": str(imp),
        "inline_link_clicks": str(clk),
        "spend": f"{spend:.2f}",
        "actions": [{"action_type": "link_click", "value": str(clk)},
                    {"action_type": "purchase", "value": str(purch)}],
        "action_values": [{"action_type": "purchase", "value": f"{rev:.2f}"}],
    }


def google_record(client, campaign, adgroup, d, imp, clk, spend, purch, rev):
    return {
        "customer": {"descriptiveName": CLIENTS[client]["name"]},
        "campaign": {"name": campaign},
        "adGroup": {"name": adgroup},
        "segments": {"date": d.isoformat()},
        "metrics": {
            "impressions": str(imp),
            "clicks": str(clk),
            "costMicros": str(int(round(spend * 1_000_000))),
            "conversions": float(purch),
            "conversionsValue": rev,
        },
    }


def tiktok_record(client, campaign, adgroup, d, imp, clk, spend, purch, rev):
    return {
        "dimensions": {"stat_time_day": f"{d.isoformat()} 00:00:00",
                       "advertiser_name": CLIENTS[client]["name"]},
        "metrics": {
            "campaign_name": campaign,
            "adgroup_name": adgroup,
            "impressions": str(imp),
            "clicks": str(clk),
            "spend": f"{spend:.2f}",
            "complete_payment": str(purch),
            "total_complete_payment_value": f"{rev:.2f}",
        },
    }


BUILDERS = {"meta": meta_record, "google": google_record, "tiktok": tiktok_record}


def wrap(platform, rows):
    """Wrap rows the way each API wraps a response page."""
    if platform == "meta":
        return {"data": rows, "paging": {}}
    if platform == "google":
        return {"results": rows}
    return {"code": 0, "message": "OK", "data": {"list": rows, "page_info": {"page": 1}}}


def main(out: Path, seed: int) -> None:
    rng = random.Random(seed)
    files = 0
    missing_day = START + timedelta(days=40)

    for platform, campaigns in CAMPAIGNS.items():
        for client in CLIENTS:
            for i in range(DAYS):
                d = START + timedelta(days=i)

                # Seeded issue: TikTok pull failed for one client on one day.
                if platform == "tiktok" and client == "brindle_bone_pets" and d == missing_day:
                    continue

                rows = []
                for campaign, groups in campaigns:
                    for group in groups:
                        metrics = simulate_day(rng, platform, client, campaign, group, i, d)
                        rows.append(BUILDERS[platform](client, campaign, group, d, *metrics))

                # Seeded issue: bad row where clicks exceed impressions.
                if platform == "google" and client == "brindle_bone_pets" and i == 60:
                    rows[0]["metrics"]["clicks"] = str(int(rows[0]["metrics"]["impressions"]) + 250)
                # Seeded issue: campaign name missing.
                if platform == "tiktok" and client == "hollowpine_outfitters" and i == 22:
                    rows[0]["metrics"]["campaign_name"] = None

                folder = out / platform / f"dt={d.isoformat()}"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{client}.json").write_text(json.dumps(wrap(platform, rows), indent=1))
                files += 1

                # Seeded issue: Meta pull retried and saved twice.
                if platform == "meta" and client == "larkspur_coffee" and i == 30:
                    (folder / f"{client}_retry.json").write_text(json.dumps(wrap(platform, rows), indent=1))
                    files += 1

    print(f"Wrote {files} raw files to {out} ({START} to {END})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    main(args.out, args.seed)
