# QuestSafety Amazon Seller Discovery MVP

This MVP helps QuestSafety decide which products should be pushed, repriced, reviewed, and later measured on Amazon.

It uses local sandbox data only:

- QuestSafety catalogue: `questsafety-spapi-backend/data/quest-safety-products-100.json`
- Amazon competitor candidates: `questsafety-spapi-backend/data/amazon-competitor-candidates-500.json`

## Login

Open the app and sign in:

```text
http://127.0.0.1:8000
```

Demo users:

```text
quest / 12345678
admin / 12345678
analyst / 12345678
```

## Pages

- `Pipeline`: run all QuestSafety SKUs through margin, competitor, and risk checks.
- `Review`: shows high-risk queue, medium-risk batches, and decision history from the latest Pipeline run.
- `Dashboard`: shows catalogue success metrics from products approved by the latest Pipeline run.

Review and Dashboard stay empty until Pipeline has run.

## Run Locally

```powershell
cd questsafety-spapi-backend
python main.py
```

If port `8000` is busy, the app automatically tries the next available local port.

## Render Deploy

```text
Root Directory: questsafety-spapi-backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

## Main Backend Flow

1. Pipeline loads all QuestSafety SKUs.
2. It loads the linked Amazon competitor candidates.
3. It calculates a safe Amazon price for each SKU.
4. It checks revenue, margin, FBA competitiveness, and risk.
5. It stores the latest run in backend memory.
6. Review and Dashboard read that same stored run.

Restarting the backend clears the run, so run Pipeline again.

## What Data Is Actually In The Source

For each QuestSafety product, the JSON has:

```text
Cost
price
costMarkupPercent
sku
amazonAsin
name
category
brand
imageUrl
```

The competitor file has linked Amazon candidate products and brands. It does not contain real live Amazon fees.

So this MVP uses fee assumptions:

```text
Amazon referral fee rate = 15%
Estimated FBA fee = min(max(recommended price * 8%, $4.35), $18.00)
Prep cost = category-based estimate
```

Why:

- Referral fee is Amazon's marketplace selling commission. Amazon normally charges it as a percentage of the final item price.
- FBA fee is the fulfillment cost for pick, pack, ship, handling, and Amazon fulfillment work. The MVP estimates it from price because no product weight/dimension fee table is available in the sandbox JSON.
- Prep cost is a Quest-side handling/prep estimate before sending the item into Amazon/FBA flow.

Important: referral fee and FBA fee are calculated from the recommended Amazon price because Amazon charges fees against the selling price that Quest will actually list.

## Recommended Price Formula

The backend first calculates a target margin price:

```text
targetMarginPercent = requiredMarginPercent + SKU-specific buffer
```

Default:

```text
requiredMarginPercent = 20%
```

The buffer creates a safer target above 20%. It is deterministic for the SKU, so the same SKU gets the same target every run.

Then:

```text
marginSafePrice =
(QuestSafety Cost + estimated FBA fee + prep cost)
/
(1 - referral fee rate - target margin rate)
```

Because FBA fee depends on the price, the backend repeats the calculation until the price stabilizes.

Then it checks competitors:

```text
competitorBeatPrice = lowest FBA competitor - $0.01
candidatePrice = max(current QuestSafety price, minimum viable price, target margin-safe price)

if competitorBeatPrice still protects the required 20% margin:
    recommendedAmazonPrice = min(candidatePrice, competitorBeatPrice)
else:
    recommendedAmazonPrice = max(current QuestSafety price, minimum viable price)
```

## Example 1: Why QU20005 Recommends $209.28

Known source / MVP inputs:

```text
SKU = QU20005
QuestSafety Cost = $106.09
Current QuestSafety Price = $124.98
Required Margin = 20%
Target Margin = 25.71%
Referral Fee Rate = 15%
Prep Cost = $1.25
Lowest FBA Competitor = $215.47
```

The backend solves this:

```text
recommended price =
(Cost + FBA fee + prep cost)
/
(1 - referral fee rate - target margin rate)
```

At `$209.28`:

```text
FBA fee = min(max($209.28 * 8%, $4.35), $18.00)
FBA fee = $16.74

Denominator = 1 - 0.15 - 0.2571
Denominator = 0.5929

Price = ($106.09 + $16.74 + $1.25) / 0.5929
Price = $209.28
```

Then the backend checks competitor pressure:

```text
Lowest FBA competitor = $215.47
Beat competitor by $0.01 = $215.46
Candidate price = $209.28
```

Because `$209.28` is below `$215.46`, Quest can be competitive and still protect margin.

Final economics:

```text
Referral fee = $209.28 * 15% = $31.39
FBA fee = $16.74
Prep cost = $1.25
Profit = $209.28 - $106.09 - $31.39 - $16.74 - $1.25 = $53.81
Margin = $53.81 / $209.28 * 100 = 25.71%
Estimated units = 59
Monthly revenue = $209.28 * 59 = $12,347.52
```

Decision:

```text
Reprice & Push
```

Reason: revenue clears `$2,000`, margin clears `20%`, and the recommended price is competitive against FBA sellers.

## Example 2: QU200055

Known inputs:

```text
QuestSafety Cost = $1,060.90
Current QuestSafety Price = $1,395.19
Required Margin = 20%
Target Margin = 27.43%
Referral Fee Rate = 15%
Prep Cost = $1.25
Lowest FBA Competitor = $2,222.41
```

At the recommended price:

```text
FBA fee = min(max($1,876.24 * 8%, $4.35), $18.00)
FBA fee = $18.00

Denominator = 1 - 0.15 - 0.2743
Denominator = 0.5757

Recommended price = ($1,060.90 + $18.00 + $1.25) / 0.5757
Recommended price = $1,876.24
```

Final economics:

```text
Referral fee = $1,876.24 * 15% = $281.44
Profit = $1,876.24 - $1,060.90 - $281.44 - $18.00 - $1.25 = $514.65
Margin = $514.65 / $1,876.24 * 100 = 27.43%
Monthly revenue = $1,876.24 * 54 units = $101,316.96
```

Decision:

```text
Reprice & Push
```

## Pipeline Calculations

Pipeline cards:

```text
Discovered = count of QuestSafety SKUs analyzed
Margin-qualified = SKUs where contribution margin >= 20%
Risk-categorized = SKUs with risk analysis completed
Approved & listed = SKUs where decision is Push to Amazon or Reprice & Push
Routed to Review = total SKUs - approved/listed SKUs
```

Risk categories:

```text
LOW / MEDIUM / HIGH
```

Risk is based on:

- revenue quality
- margin buffer
- FBA competitiveness
- ASIN match confidence
- category compliance

## Review Page Calculations

Review is generated only from the latest Pipeline run:

```text
High-risk queue = SKUs with riskAnalysis.level == HIGH
Medium-risk batches = SKUs with riskAnalysis.level == MEDIUM
Decision history = latest run sorted by score and decision outcome
```

High-risk items need manual review because Amazon listing risk, ASIN confidence, compliance, or margin/FBA pressure is too sensitive for auto-push.

## Dashboard Calculations

Dashboard uses only products approved by the latest Pipeline run:

```text
Approved products = decision is Push to Amazon or Reprice & Push
Products live on Amazon = count(approved products)
Monthly run-rate revenue = sum(monthlyRevenue for approved products)
Revenue YTD = monthly run-rate revenue * 6
Blended margin = sum(monthlyRevenue * contributionMarginPercent) / sum(monthlyRevenue)
Live catalogue by risk tier = count approved products by LOW / MEDIUM / HIGH
```

Revenue growth is an MVP trend estimate:

```text
Revenue growth = (current run-rate - prior month run-rate estimate) / prior month run-rate estimate * 100
```

The dashboard chart uses deterministic monthly factors so the result is stable for demo:

```text
Monthly revenue bar = approved monthly run-rate * month factor
Products-live line = approved products * cumulative monthly factor
```

This is not a real Amazon settlement report. It is a dynamic MVP forecast based on the latest sandbox pipeline run.
