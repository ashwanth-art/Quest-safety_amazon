import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const MARKUP_MIN_PERCENT = 17.0;
const MARKUP_MAX_PERCENT = 35.0;

const scriptDir = dirname(fileURLToPath(import.meta.url));
const productsPath = join(scriptDir, "..", "data", "quest-safety-products-100.json");

const productData = JSON.parse(await readFile(productsPath, "utf8"));

for (const product of productData.records) {
  const cost = roundMoney(product.Cost ?? product.price ?? 0);
  const markupPercent = costMarkupPercent(product);
  const salePrice = roundMoney(cost * (1 + markupPercent / 100));

  product.Cost = cost;
  product.price = salePrice;
  product.costMarkupPercent = markupPercent;
  product.pricingModel = "cost_plus_markup";
  product.CostSource = "original_price";
  product.pricingNote = (
    "Sandbox assumption: original QuestSafety price is used as Cost "
    + "because no separate cost field was provided."
  );
}

productData.sourceType = (
  "Quest-branded products with explicit Cost and cost-based price"
);
productData.pricingModel = {
  CostSource: "original records[].price",
  markupPercentMinimum: MARKUP_MIN_PERCENT,
  markupPercentMaximum: MARKUP_MAX_PERCENT,
  priceFormula: "Cost * (1 + costMarkupPercent / 100)",
};

await writeFile(productsPath, `${JSON.stringify(productData, null, 2)}\n`, "utf8");

console.log(`Updated ${productData.records.length} QuestSafety records with Cost and price fields.`);

function costMarkupPercent(product) {
  const seed = `${product.recordId}:${product.sku}:markup`;
  const basisPoints = stableInt(
    seed,
    Math.round(MARKUP_MIN_PERCENT * 100),
    Math.round(MARKUP_MAX_PERCENT * 100),
  );
  const cents = stableInt(`${seed}:float`, 0, 99) / 100;
  return roundPercent(Math.min(MARKUP_MAX_PERCENT, (basisPoints / 100) + cents));
}

function stableInt(seed, minimum, maximum) {
  const digest = createHash("sha256").update(seed).digest("hex");
  const value = Number.parseInt(digest.slice(0, 8), 16);
  return minimum + (value % (maximum - minimum + 1));
}

function roundMoney(value) {
  return Math.round(Number(value || 0) * 100) / 100;
}

function roundPercent(value) {
  return Math.round(Number(value || 0) * 100) / 100;
}
