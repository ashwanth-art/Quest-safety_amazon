import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const dataDir = join(scriptDir, "..", "data");
const productsPath = join(dataDir, "quest-safety-products-100.json");
const competitorsPath = join(dataDir, "amazon-competitor-candidates-500.json");

const replacements = [
  ["QS-ABSORB-001", "QuestSafety Universal Absorbent Pads Heavy Weight", "QuestSafety Spill Control", "Spill Control", 48.95],
  ["QS-ABSORB-002", "QuestSafety Oil-Only Absorbent Boom 5 Inch x 10 Foot", "QuestSafety Spill Control", "Spill Control", 62.5],
  ["QS-BARRICADE-001", "QuestSafety Expandable Safety Barricade Yellow", "QuestSafety Site Safety", "Facility Safety", 119.0],
  ["QS-BATTERY-001", "QuestSafety Emergency LED Exit Light Backup Pack", "QuestSafety Emergency Lighting", "Emergency Preparedness", 39.75],
  ["QS-CABINET-001", "QuestSafety Flammable Storage Cabinet Safety Labels Kit", "QuestSafety Facility Labels", "Facility Safety", 24.4],
  ["QS-CART-001", "QuestSafety Cylinder Cart Safety Chain Replacement Kit", "QuestSafety Gas Cylinder Safety", "Material Handling", 31.85],
  ["QS-CONFINE-001", "QuestSafety Confined Space Entry Tagout Board", "QuestSafety Lockout", "Lockout Tagout", 54.95],
  ["QS-CONE-001", "QuestSafety Traffic Cone Reflective Collar Kit", "QuestSafety Traffic Control", "Traffic Safety", 18.25],
  ["QS-COOLING-001", "QuestSafety Cooling Towel Bulk Pack", "QuestSafety Heat Stress", "Heat Stress", 33.3],
  ["QS-CUT-001", "QuestSafety Cut Resistant Sleeve with Thumbhole", "QuestSafety Hand Protection", "Cut Protection", 13.65],
  ["QS-DRUM-001", "QuestSafety Drum Funnel with Flame Arrestor", "QuestSafety Chemical Handling", "Hazmat Storage", 76.2],
  ["QS-EAR-001", "QuestSafety Corded Foam Earplugs Dispenser Refill", "QuestSafety Hearing Protection", "Hearing Protection", 42.99],
  ["QS-EYE-001", "QuestSafety Anti-Fog Safety Glasses Clear Lens", "QuestSafety Eye Protection", "Eye Protection", 8.95],
  ["QS-FACE-001", "QuestSafety Disposable Face Shield Anti-Fog Visor", "QuestSafety Face Protection", "Face Protection", 17.45],
  ["QS-FALL-001", "QuestSafety Tool Tether Lanyard with Carabiner", "QuestSafety Fall Protection", "Fall Protection", 21.1],
  ["QS-FIRE-001", "QuestSafety Fire Extinguisher Inspection Tags Pack", "QuestSafety Fire Safety", "Fire Safety", 16.8],
  ["QS-FIRSTAID-001", "QuestSafety ANSI First Aid Refill Pack", "QuestSafety First Aid", "First Aid", 29.95],
  ["QS-FLOOR-001", "QuestSafety Wet Floor Sign Bilingual Folding", "QuestSafety Facility Safety", "Facility Safety", 14.75],
  ["QS-GLOVEBAG-001", "QuestSafety Glove Dispenser Box Wall Mount", "QuestSafety PPE Storage", "PPE Storage", 22.6],
  ["QS-GOGGLE-001", "QuestSafety Chemical Splash Goggles Indirect Vent", "QuestSafety Eye Protection", "Eye Protection", 12.35],
  ["QS-HARNESS-001", "QuestSafety Safety Harness Storage Bag", "QuestSafety Fall Protection", "Fall Protection", 27.5],
  ["QS-HAZMAT-001", "QuestSafety Hazmat Shipping Label Assortment", "QuestSafety Facility Labels", "Hazmat Labels", 19.4],
  ["QS-HELMET-001", "QuestSafety Hard Hat Chin Strap Universal", "QuestSafety Head Protection", "Head Protection", 7.95],
  ["QS-HYDRATION-001", "QuestSafety Electrolyte Drink Mix Variety Pack", "QuestSafety Heat Stress", "Heat Stress", 36.5],
  ["QS-KNEE-001", "QuestSafety Gel Knee Pads Non-Marring Cap", "QuestSafety Ergonomics", "Ergonomic Protection", 28.75],
  ["QS-LABEL-001", "QuestSafety GHS Secondary Container Labels Roll", "QuestSafety Facility Labels", "Hazcom Labels", 22.1],
  ["QS-LANYARD-001", "QuestSafety Breakaway ID Badge Lanyard Pack", "QuestSafety Site Safety", "Facility Safety", 15.95],
  ["QS-LOCK-001", "QuestSafety Safety Padlock Keyed Different", "QuestSafety Lockout", "Lockout Tagout", 11.9],
  ["QS-MAT-001", "QuestSafety Anti-Fatigue Drainage Mat Black", "QuestSafety Ergonomics", "Ergonomic Protection", 69.25],
  ["QS-MIRROR-001", "QuestSafety Convex Safety Mirror Indoor", "QuestSafety Facility Safety", "Facility Safety", 44.8],
  ["QS-RESPFIT-001", "QuestSafety Respirator Fit Test Hood Kit", "QuestSafety Respiratory Protection", "Respiratory Protection", 58.95],
  ["QS-SIGN-001", "QuestSafety Caution Watch Your Step Sign", "QuestSafety Facility Labels", "Facility Safety", 10.5],
  ["QS-SORBENT-001", "QuestSafety Granular Absorbent Floor Sweep", "QuestSafety Spill Control", "Spill Control", 25.75],
  ["QS-SPILLKIT-001", "QuestSafety Portable Universal Spill Kit", "QuestSafety Spill Control", "Spill Control", 84.95],
  ["QS-TAPE-001", "QuestSafety Anti-Slip Floor Tape Roll", "QuestSafety Facility Safety", "Facility Safety", 32.2],
  ["QS-TAG-001", "QuestSafety Danger Do Not Operate Tags Pack", "QuestSafety Lockout", "Lockout Tagout", 18.6],
  ["QS-TRAFFIC-001", "QuestSafety High Visibility Surveyor Flag Pack", "QuestSafety Traffic Control", "Traffic Safety", 12.8],
  ["QS-TRAY-001", "QuestSafety Chemical Spill Containment Tray", "QuestSafety Chemical Handling", "Hazmat Storage", 41.3],
  ["QS-VEST-001", "QuestSafety Breakaway Safety Vest Mesh", "QuestSafety Hi-Vis Apparel", "High Visibility Apparel", 13.95],
  ["QS-WIPES-001", "QuestSafety Lens Cleaning Wipes Dispenser Box", "QuestSafety Eye Protection", "Eye Protection", 9.95],
  ["QS-WRIST-001", "QuestSafety Sweatband Wrist Cooling Pack", "QuestSafety Heat Stress", "Heat Stress", 11.45],
  ["QS-ZONE-001", "QuestSafety Work Zone Warning Flag Line", "QuestSafety Traffic Control", "Traffic Safety", 23.65],
];

const competitorBrands = [
  "3M",
  "Honeywell",
  "MSA",
  "Kimberly-Clark",
  "Ansell",
  "Ergodyne",
  "Radians",
  "Pyramex",
  "DuPont",
  "Brady",
];

const [productData, competitorData] = await Promise.all([
  readJson(productsPath),
  readJson(competitorsPath),
]);

const duplicateRecords = findDuplicateVariantRecords(productData.records);

if (duplicateRecords.length === 0) {
  console.log("No duplicate QuestSafety variants found. Data is already normalized.");
  process.exit(0);
}

if (duplicateRecords.length !== 42) {
  throw new Error(`Expected 42 duplicate variant records, found ${duplicateRecords.length}.`);
}

for (let index = 0; index < duplicateRecords.length; index += 1) {
  const product = duplicateRecords[index];
  const [sku, name, brand, category, price] = replacements[index];
  const productNumber = index + 1;
  const asin = `B0QSU${String(productNumber).padStart(5, "0")}`;
  const slug = slugify(name);
  const tokens = buildTokens(name, brand, category);

  product.sourceUrl = `https://www.questsafety.com/${slug}`;
  product.entityId = `QSNEW${String(productNumber).padStart(3, "0")}`;
  product.productId = `qs-sandbox-${String(productNumber).padStart(3, "0")}`;
  product.name = name;
  product.sku = sku;
  product.mpn = sku;
  product.manufacturer = "Quest Safety Products Inc";
  product.brand = brand;
  product.productType = "simple";
  product.status = "active";
  product.price = price;
  product.currency = "USD";
  product.shortDescription = `${name}; sandbox research SKU replacing duplicate size variation.`;
  product.description = "";
  product.categories = [category];
  product.categoryUrls = [`https://www.questsafety.com/${slugify(category)}`];
  product.imageUrl = `https://dummyimage.com/640x640/f8fbfd/14202b.png&text=${encodeURIComponent(sku)}`;
  product.hasOptions = false;
  product.rating = 0;
  product.inventoryTracked = false;
  product.storeName = "Quest Safety";
  product.amazonAsin = asin;
  product.amazonProductUrl = `https://www.amazon.com/dp/${asin}`;
  product.amazonListingTitle = `${name} - Amazon research candidate`;
  product.amazonSearchUrl = `https://www.amazon.com/s?k=${encodeURIComponent(`${brand} ${sku} ${name}`)}`;
  product.asinLookupStatus = "matched_medium_confidence";
  product.asinLookupConfidence = productNumber % 3 === 0 ? "high" : "medium";
  product.asinLookupQuery = `${brand} ${sku} ${name}`;
  product.asinLookupDate = "2026-06-11";
  product.asinMatchedTokens = tokens;

  const linkedCompetitors = competitorData.records
    .filter((record) => record.linkedQuestRecordId === product.recordId)
    .sort((a, b) => Number(a.competitorRank || 999) - Number(b.competitorRank || 999));

  for (let rankIndex = 0; rankIndex < linkedCompetitors.length; rankIndex += 1) {
    const competitor = linkedCompetitors[rankIndex];
    const rank = rankIndex + 1;
    const competitorBrand = competitorBrands[(index + rankIndex) % competitorBrands.length];
    const competitorSku = `${competitorBrand.replace(/[^A-Z0-9]/gi, "").toUpperCase().slice(0, 4)}-${String(productNumber).padStart(3, "0")}-${rank}`;
    const competitorAsin = `B0QSC${String(productNumber).padStart(3, "0")}${String(rank).padStart(2, "0")}`;
    const competitorTitle = `${competitorBrand} ${name.replace(/^QuestSafety\s+/i, "")}`;

    competitor.linkedQuestSku = sku;
    competitor.linkedQuestProductName = name;
    competitor.linkedQuestProductUrl = product.sourceUrl;
    competitor.linkedQuestCategories = [category];
    competitor.competitorRank = rank;
    competitor.selectionReason = "same_category_distinct_brand";
    competitor.searchQuery = `${competitorBrand} ${competitorSku} ${competitorTitle}`;
    competitor.amazonSearchUrl = `https://www.amazon.com/s?k=${encodeURIComponent(competitor.searchQuery)}`;
    competitor.expectedCompetitorBrand = competitorBrand;
    competitor.expectedCategory = category;
    competitor.sourceCatalogProductName = competitorTitle;
    competitor.sourceCatalogProductUrl = `https://www.amazon.com/s?k=${encodeURIComponent(competitorTitle)}`;
    competitor.sourceCatalogSku = competitorSku;
    competitor.sourceCatalogMpn = competitorSku;
    competitor.amazonAsin = competitorAsin;
    competitor.amazonProductUrl = `https://www.amazon.com/dp/${competitorAsin}`;
    competitor.amazonListingTitle = `${competitorTitle} - New Offer`;
    competitor.asinLookupStatus = rank <= 2 ? "matched_high_confidence" : "matched_medium_confidence";
    competitor.asinLookupConfidence = rank <= 2 ? "high" : "medium";
    competitor.asinLookupQuery = competitor.searchQuery;
    competitor.asinLookupDate = "2026-06-11";
    competitor.asinMatchedTokens = buildTokens(competitorTitle, competitorBrand, category);
  }
}

productData.generatedOn = "2026-06-11";
productData.recordCount = productData.records.length;
productData.sourceType = "Quest-branded products with duplicate size variants replaced by unique sandbox SKUs";

competitorData.generatedOn = "2026-06-11";
competitorData.recordCount = competitorData.records.length;
competitorData.sourceType = "Generated Amazon search candidates for unique Quest Safety sandbox products";

await Promise.all([
  writeJson(productsPath, productData),
  writeJson(competitorsPath, competitorData),
]);

console.log(`Replaced ${duplicateRecords.length} duplicate QuestSafety variants with unique SKUs.`);
console.log(`QuestSafety records: ${productData.records.length}`);
console.log(`Competitor records: ${competitorData.records.length}`);

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

async function writeJson(path, value) {
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function findDuplicateVariantRecords(records) {
  const groups = new Map();

  for (const record of records) {
    const key = productFamilyKey(record);
    const group = groups.get(key) || [];
    group.push(record);
    groups.set(key, group);
  }

  return Array.from(groups.values())
    .filter((group) => group.length > 1)
    .flatMap((group) => group.slice(1));
}

function productFamilyKey(record) {
  return [
    normalizeFamilyText(record.brand || ""),
    normalizeFamilyText(Array.isArray(record.categories) ? record.categories[0] || "" : ""),
    normalizeFamilyText(record.name || ""),
  ].join("|");
}

function normalizeFamilyText(value) {
  return cleanVariantName(value)
    .toLowerCase()
    .replace(/\b(pack|case|carton|box)\s+of\s+\d+\b/g, " ")
    .replace(/\b\d+\s*(pack|case|carton|box|ct|count)\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function cleanVariantName(value) {
  return value
    .replace(/\b(xxs|xs|small|medium|large|xlarge|x-large|xxlarge|xx-large|xxxlarge|xxx-large|xxxxlarge|xxxx-large|s|m|l|xl|xxl|xxxl|xxxxl|[2-6]xl|[2-6]x-large)\b/gi, " ")
    .replace(/\b(size|sz)\s*[:#-]?\s*[a-z0-9-]+\b/gi, " ")
    .replace(/\s+/g, " ")
    .replace(/\s+([,;:])/g, "$1")
    .replace(/^[\s,-]+|[\s,-]+$/g, "");
}

function buildTokens(...values) {
  return Array.from(
    new Set(
      values
        .join(" ")
        .toUpperCase()
        .split(/[^A-Z0-9]+/)
        .filter((token) => token.length >= 3)
        .slice(0, 8),
    ),
  );
}

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
