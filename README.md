# Agency Reporting Pipeline

Automated pipeline that pulls ad performance data from Meta, Google Ads, and TikTok, validates it, and combines it into one clean dataset for client reporting.

*All companies and data in this project are fictional.*

## Unified Schema

**Grain:** one row = one ad group, on one platform, on one day.

| Column | Type | Description |
|---|---|---|
| report_date | date | Day the performance data is for |
| platform | string | Ad platform (meta, google, tiktok) |
| account | string | Client account name |
| campaign | string | Campaign name |
| ad_group | string | Ad set / ad group name |
| impressions | integer | Times the ad was shown |
| clicks | integer | Clicks on the ad |
| spend_usd | float | Amount spent, in USD |
| conversions | float | Purchases (float: Google can report fractional conversions) |
| revenue_usd | float | Purchase value, in USD |

## Source Mapping

How each platform's raw fields map to the unified schema.

| Column | Meta | Google Ads | TikTok | Notes |
|---|---|---|---|---|
| report_date | `date_start` | `segments.date` | `dimensions.stat_time_day` | TikTok: cut off " 00:00:00" |
| platform | folder name | folder name | folder name | Not in the data; taken from `data/raw/<platform>` |
| account | `account_name` | `customer.descriptiveName` | `dimensions.advertiser_name` | |
| campaign | `campaign_name` | `campaign.name` | `metrics.campaign_name` | |
| ad_group | `adset_name` | `adGroup.name` | `metrics.adgroup_name` | |
| impressions | `impressions` | `metrics.impressions` | `metrics.impressions` | All text → integer |
| clicks | `inline_link_clicks` | `metrics.clicks` | `metrics.clicks` | All text → integer |
| spend_usd | `spend` | `metrics.costMicros` ÷ 1,000,000 | `metrics.spend` | All text → float |
| conversions | `actions` item where `action_type` = "purchase" → `value` | `metrics.conversions` | `metrics.complete_payment` | Meta & TikTok text → float; Google already a number |
| revenue_usd | `action_values` item where `action_type` = "purchase" → `value` | `metrics.conversionsValue` | `metrics.total_complete_payment_value` | Meta & TikTok text → float; Google already a number |