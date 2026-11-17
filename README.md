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