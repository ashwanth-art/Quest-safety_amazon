# QuestSafety Amazon Seller Discovery MVP

Combined FastAPI backend and template frontend for deciding which QuestSafety SKUs should be pushed, repriced, reviewed, and monitored on Amazon.

## Login

```text
quest / 12345678
admin / 12345678
analyst / 12345678
```

`/` opens `/login`. After login the app opens `/pipeline`. Login and logout clear the current in-memory run so Review and Dashboard stay empty until Pipeline is run again.

## Run Locally

```powershell
python -m pip install -r requirements.txt
python main.py
```

Open:

```text
http://127.0.0.1:8000/login
```

## Data Used

The MVP is dynamic from the local sandbox JSON files:

```text
data/quest-safety-products-100.json
data/amazon-competitor-candidates-500.json
```

QuestSafety product fields used:

```text
sku, asin, name, brand, category, imageUrl, Cost, price
```

Amazon competitor fields used:

```text
sellerName, brand, category, fulfillmentType, estimatedPrice,
estimatedMonthlyRevenue, matchConfidence
```

## Core Business Rules

The MVP checks three main gates:

```text
Monthly revenue must be at least $2,000
Contribution margin must be at least 20%
Quest must be able to be lowest or competitive FBA seller
```

Why these gates exist:

- Revenue threshold checks whether the Amazon opportunity is large enough to matter.
- Margin threshold protects QuestSafety from pushing products that sell but lose money.
- FBA competitiveness checks whether Quest can compete against the lowest FBA offer after fees.
- Risk analysis prevents risky products from being auto-pushed when category, margin, or match confidence needs human review.

## Fee Assumptions

The sandbox files do not include a full Amazon fee table, so the MVP estimates fees:

```text
Referral fee rate = 15%
Estimated FBA fee = min(max(recommended price * 8%, 4.35), 18.00)
Prep cost = category based, commonly $1.25 in the sandbox
```

Why:

- Referral fee is Amazon's selling commission.
- FBA fee estimates fulfillment and handling.
- Prep cost estimates Quest-side packaging, labeling, or handling.

## Recommended Price Formula

The backend calculates a margin-safe Amazon price:

```text
recommended price =
(QuestSafety Cost + estimated FBA fee + prep cost)
/
(1 - referral fee rate - target margin rate)
```

Because FBA fee depends on recommended price, the backend iterates until the price and fee are stable.

Then the backend compares the recommended price against the lowest FBA competitor:

```text
recommended price <= lowest FBA competitor price
```

If the price protects margin and stays competitive, the product can be pushed or repriced.

## Pipeline Page

The Pipeline page runs all QuestSafety SKUs against the competitor sandbox.

### Candidate Flow

```text
Discovered = number of QuestSafety SKUs scanned
Margin-qualified = SKUs where margin gate passed
Risk-categorized = SKUs scored by risk engine
Approved & listed = SKUs where decision.action is not HUMAN_REVIEW
Routed to Review = SKUs where decision.action is HUMAN_REVIEW
```

Rates:

```text
Margin rate = margin-qualified / discovered * 100
Approval rate = approved & listed / risk-categorized * 100
```

Why:

- It shows how many products moved from catalog scan to approved Amazon push.
- It also shows how many need Review before any Amazon action.

### Data Discovery Cards

Prophet 21 catalog:

```text
SKU count = QuestSafety product count from JSON
Cost coverage = products with Cost / products scanned * 100
Sync cadence = Hourly
```

Amazon marketplace scan:

```text
Candidate count = Amazon competitor records used
Match rate = products with ASIN / products scanned * 100
Unmatched = products scanned - products with ASIN
Scan cadence = Daily
```

`Sync cadence` is display metadata for the intended production system. In this MVP the app reads local JSON files. Prophet 21 is shown as hourly because ERP product/cost/inventory data can refresh often. Amazon marketplace scan is shown as daily because competitor scans are usually slower and depend on API limits.

### Pipeline Summary

```text
Products analyzed = total results in latest run
Push candidates = decision.action != HUMAN_REVIEW
Monthly revenue = sum(monthlyRevenue for all analyzed products)
Weighted margin =
  sum(monthlyRevenue * contributionMarginPercent)
  /
  sum(monthlyRevenue)
```

Why:

- Monthly revenue estimates total opportunity.
- Weighted margin gives more influence to high-revenue SKUs.

### Listing Queue

Each product card shows:

```text
SKU
decision label
product image/name/category
research score
monthly revenue
margin
risk level
```

Cards are sorted by research score so the strongest Amazon opportunities appear first.

### Decision Studio

For the selected SKU the page shows:

```text
recommended Amazon price
projected margin
estimated monthly units
competitors
decision gates
risk analysis
why this decision
Amazon push suggestion
```

The recommendation is only a suggestion in this MVP. No real Amazon payload is sent.

## Review Page

Review uses only the latest Pipeline run.

### Review Count

```text
Review count = products where decision.action == HUMAN_REVIEW
```

This is the same count used in the Pipeline header, Review header, and Dashboard header.

### High-Risk Queue

```text
High-risk queue =
  decision.action == HUMAN_REVIEW
  and riskAnalysis.level == HIGH
```

The detail panel explains:

```text
why the SKU was routed
risk factors
decision gates
margin and pricing
competitor context
agent recommendation
```

Why:

- High-risk products may have thin margin, low revenue quality, category risk, low ASIN confidence, or FBA competitiveness issues.
- A human should approve or reject before listing changes.

### Medium-Risk Batch Approval

```text
Batch review =
  decision.action == HUMAN_REVIEW
  and riskAnalysis.level != HIGH
```

This includes medium-risk SKUs and any low-risk SKUs that still failed a decision gate.

When the user clicks `Approve selected`:

```text
POST /api/research/approve
selected records become PUSH_TO_AMAZON
review count decreases
dashboard live products increase
```

Why:

- Medium and non-high review items can be approved in a batch when economics are acceptable.
- Only selected rows are approved.

### Decision History

Decision history sorts recent products by research score and shows whether they were:

```text
auto-listed
approved from review
routed to review
rejected because margin is below floor
```

## Dashboard Page

Dashboard uses approved products from the latest Pipeline run.

```text
Approved product = decision.action != HUMAN_REVIEW
```

### KPI Cards

Products live on Amazon:

```text
count(approved products)
```

Revenue YTD:

```text
approved monthly run-rate * 6
```

Revenue growth:

```text
prior month revenue = current monthly run-rate * 0.955
growth percent =
  (current monthly run-rate - prior month revenue)
  /
  prior month revenue
  * 100
```

Blended margin:

```text
sum(approved monthlyRevenue * contributionMarginPercent)
/
sum(approved monthlyRevenue)
```

Why:

- Products live measures catalogue progress.
- Revenue YTD estimates year-to-date Amazon impact.
- Growth gives a simple trend signal.
- Blended margin checks whether the approved catalogue is profitable after weighting by revenue.

### Revenue & Catalogue Growth Chart

The chart is an MVP visual trend:

```text
monthly revenue trend = approved monthly run-rate * month factor
products live trend = approved product count * month factor
```

Month factors create a Jan-to-Jun progression. The SVG chart uses a fixed visual axis:

```text
Revenue axis = $0K to $300K
Products axis = 0 to 900
```

The KPI cards and product table are the source of truth for actual values. The chart is normalized so the demo dashboard remains readable and looks like a performance dashboard.

### Live Catalogue By Risk Tier

The donut chart groups approved products:

```text
Low = approved products where riskAnalysis.level == LOW
Medium = approved products where riskAnalysis.level == MEDIUM
High = approved products where riskAnalysis.level == HIGH
```

Slice size:

```text
risk slice degrees = risk count / approved count * 360
```

Why:

- It shows whether the live catalogue is mostly low-risk or whether risky products are being pushed.

### Top-Performing Added Products

```text
rows = approved products sorted by monthlyRevenue descending
Revenue YTD per row = monthlyRevenue * 6
Growth = sandbox trend based on research score
Approved via =
  Review if approvalStatus == APPROVED_BY_USER
  Batch if risk level is MEDIUM
  Auto otherwise
```

Why:

- It shows which approved SKUs are expected to drive the most Amazon revenue.

## Worked SKU Example

Example SKU from the current sandbox run:

```text
SKU = QS-HARNESS-001
Product = QuestSafety Safety Harness Storage Bag
ASIN = B0QSU00021
Category = Fall Protection
QuestSafety Cost = $27.50
Current QuestSafety price = $32.48
Recommended Amazon price = $57.98
Required margin = 20.0%
Target margin = 27.41%
Lowest FBA competitor = $65.76
Estimated units = 100
```

Step 1: Estimate Amazon referral fee.

```text
Referral fee = recommended price * 15%
Referral fee = $57.98 * 0.15
Referral fee = $8.70
```

Step 2: Estimate FBA fee.

```text
FBA fee = min(max(recommended price * 8%, 4.35), 18.00)
FBA fee = min(max($57.98 * 0.08, 4.35), 18.00)
FBA fee = min(max($4.64, $4.35), $18.00)
FBA fee = $4.64
```

Step 3: Add prep cost.

```text
Prep cost = $1.25
```

Step 4: Calculate profit per unit.

```text
Profit =
recommended price
- QuestSafety Cost
- referral fee
- FBA fee
- prep cost

Profit = $57.98 - $27.50 - $8.70 - $4.64 - $1.25
Profit = $15.89
```

Step 5: Calculate contribution margin.

```text
Contribution margin =
profit / recommended price * 100

Contribution margin = $15.89 / $57.98 * 100
Contribution margin = 27.41%
```

Step 6: Calculate monthly revenue.

```text
Monthly revenue = recommended price * estimated units
Monthly revenue = $57.98 * 100
Monthly revenue = $5,798
```

Step 7: Check gates.

```text
Revenue gate:
$5,798 >= $2,000 = pass

Margin gate:
27.41% >= 20.0% = pass

FBA competitiveness gate:
$57.98 <= $65.76 lowest FBA competitor = pass
```

Step 8: Risk and decision.

```text
Risk level = LOW
Decision = Reprice & Push
Reason = revenue, margin, FBA competitiveness, and risk checks pass
```

This SKU is recommended because it can be priced below the lowest FBA competitor while still keeping margin above the 20% requirement.

## API Endpoints

```text
GET  /health
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/session
POST /api/research/analyze
GET  /api/research/current
POST /api/research/clear
POST /api/research/approve
POST /api/amazon-metrics/summary
POST /api/amazon-metrics/ask
```
