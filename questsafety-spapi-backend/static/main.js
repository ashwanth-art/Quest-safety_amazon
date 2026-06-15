const mainState = {
  analysis: null,
  selectedRecordId: null,
  query: "",
};

const analysisResults = document.querySelector("#analysisResults");
const pipelineFlow = document.querySelector("#pipelineFlow");
const runButton = document.querySelector("#runResearchButton");
const runStatus = document.querySelector("#runStatus");
const headerStatus = document.querySelector("#headerStatus");
const productQueue = document.querySelector("#productQueue");
const studioSku = document.querySelector("#studioSku");
const studioScore = document.querySelector("#studioScore");
const studioBody = document.querySelector("#studioBody");
const mainSearch = document.querySelector("#mainSearch");
const resetMain = document.querySelector("#resetMain");

initMainPage();

async function initMainPage() {
  bindMainEvents();
  await loadCurrentAnalysis();
}

function bindMainEvents() {
  runButton.addEventListener("click", runAllSkus);

  mainSearch.addEventListener("input", debounce(() => {
    mainState.query = mainSearch.value.trim().toLowerCase();
    renderAnalysis();
  }, 180));

  resetMain.addEventListener("click", async () => {
    await fetch("/api/research/clear", { method: "POST" });
    mainState.analysis = null;
    mainState.selectedRecordId = null;
    mainState.query = "";
    mainSearch.value = "";
    analysisResults.hidden = true;
    pipelineFlow.hidden = true;
    headerStatus.textContent = "Not run";
    runStatus.textContent = "Waiting";
    resetPipelineStats();
    document.dispatchEvent(new CustomEvent("analysis:updated"));
    studioSku.textContent = "Run analysis";
    studioScore.textContent = "0/100";
    studioBody.innerHTML = '<div class="empty-state">Run the pipeline to see recommendation, competitors, decision gates, and risk analysis.</div>';
  });

  productQueue.addEventListener("click", (event) => {
    const card = event.target.closest("[data-record-id]");
    if (!card) {
      return;
    }

    mainState.selectedRecordId = card.dataset.recordId;
    renderAnalysis();
  });
}

async function loadCurrentAnalysis() {
  try {
    const response = await fetch("/api/research/current");
    if (!response.ok) {
      return;
    }

    const data = await response.json();
    if (data.isReady) {
      mainState.analysis = data;
      mainState.selectedRecordId = data.results?.[0]?.recordId || null;
      renderAnalysis();
    } else {
      pipelineFlow.hidden = true;
      resetPipelineStats();
    }
  } catch {
    // Fresh local runs start empty by design.
    resetPipelineStats();
  }
}

async function runAllSkus() {
  setRunning(true);

  try {
    const response = await fetch("/api/research/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: null,
        monthlyRevenueThreshold: Number(document.querySelector("#revenueThreshold").value || 2000),
        minMarginPercent: Number(document.querySelector("#minMargin").value || 20),
        priority: "researchScore",
      }),
    });

    if (!response.ok) {
      throw new Error("Research API failed");
    }

    const data = await response.json();
    mainState.analysis = data;
    mainState.selectedRecordId = data.results?.[0]?.recordId || null;
    renderAnalysis();
    runStatus.textContent = "Complete";
    document.dispatchEvent(new CustomEvent("analysis:updated"));
  } catch (error) {
    runStatus.textContent = "Failed";
    studioBody.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Research failed.")}</div>`;
  } finally {
    setRunning(false);
  }
}

function setRunning(isRunning) {
  runButton.disabled = isRunning;
  runButton.textContent = isRunning ? "Analyzing..." : "Run pipeline";
  runStatus.textContent = isRunning ? "Running margin, competitor, and risk checks" : runStatus.textContent;
  headerStatus.textContent = isRunning ? "Running" : headerStatus.textContent;
}

function renderAnalysis() {
  const analysis = mainState.analysis;
  if (!analysis?.results?.length) {
    analysisResults.hidden = true;
    pipelineFlow.hidden = true;
    return;
  }

  pipelineFlow.hidden = false;
  analysisResults.hidden = false;
  renderSummary(analysis);
  renderPipelineStats(analysis);

  const rows = visibleRows(analysis.results);
  if (!rows.find((item) => item.recordId === mainState.selectedRecordId)) {
    mainState.selectedRecordId = rows[0]?.recordId || analysis.results[0].recordId;
  }

  renderQueue(rows);
  renderStudio(selectedItem(analysis.results, rows));
}

function renderSummary(analysis) {
  const summary = analysis.summary || {};
  const metadata = analysis.metadata || {};
  document.querySelector("#summarySkuCount").textContent = formatInteger(metadata.productCount || analysis.results.length);
  document.querySelector("#summaryPushCount").textContent = formatInteger(summary.pushCount || 0);
  document.querySelector("#summaryRevenue").textContent = formatMoney(summary.totalEstimatedMonthlyRevenue || 0);
  document.querySelector("#summaryMargin").textContent = `${formatNumber(summary.averageMarginPercent || 0, 1)}%`;
  headerStatus.textContent = `${formatInteger(metadata.productCount || analysis.results.length)} SKUs analyzed`;
}

function visibleRows(rows) {
  const query = mainState.query;

  return sortRows(rows.filter((item) => {
    if (!query) {
      return true;
    }

    return [
      item.sku,
      item.asin,
      item.name,
      item.brand,
      item.category,
    ].join(" ").toLowerCase().includes(query);
  }));
}

function sortRows(rows) {
  return [...rows].sort((a, b) => (b.researchScore || 0) - (a.researchScore || 0));
}

function renderPipelineStats(analysis) {
  const rows = analysis.results || [];
  const metadata = analysis.metadata || {};
  const discovered = metadata.productCount || rows.length;
  const marginQualified = rows.filter((item) => item.criteria?.margin?.passed).length;
  const approved = rows.filter((item) => isLiveListing(item)).length;
  const high = rows.filter((item) => item.riskAnalysis?.level === "HIGH").length;
  const medium = rows.filter((item) => item.riskAnalysis?.level === "MEDIUM").length;
  const low = rows.filter((item) => item.riskAnalysis?.level === "LOW").length;
  const competitorCount = metadata.competitorCount || rows.reduce((sum, item) => sum + (item.competitors?.length || 0), 0);
  const withCost = rows.filter((item) => Number(item.Cost || item.economics?.Cost || 0) > 0).length;
  const withAsin = rows.filter((item) => item.asin).length;
  const reviewCount = rows.filter((item) => item.decision?.action === "HUMAN_REVIEW").length;

  setText("flowDiscovered", formatInteger(discovered));
  setText("flowMarginQualified", formatInteger(marginQualified));
  setText("flowRiskCategorized", formatInteger(rows.length));
  setText("flowApproved", formatInteger(approved));
  setText("flowMarginRate", `${percent(marginQualified, discovered)}%`);
  setText("flowApproveRate", `${percent(approved, rows.length)}%`);
  setText("flowRiskBreakdown", `${formatInteger(low)} Low - ${formatInteger(medium)} Med - ${formatInteger(high)} High`);
  setText("flowReviewNote", `${formatInteger(reviewCount)} routed to Review`);
  setText("p21SkuCount", `${formatInteger(metadata.sourceProductCount || discovered)} SKUs`);
  setText("p21CostCoverage", `${percent(withCost, rows.length)}%`);
  setText("amazonCandidateCount", `${formatInteger(competitorCount)} candidates`);
  setText("amazonMatchRate", `${percent(withAsin, rows.length)}%`);
  setText("amazonExceptionCount", formatInteger(Math.max(0, rows.length - withAsin)));
  setText("reviewNavCount", formatInteger(reviewCount));
}

function resetPipelineStats() {
  [
    "flowDiscovered",
    "flowMarginQualified",
    "flowRiskCategorized",
    "flowApproved",
    "p21CostCoverage",
    "amazonMatchRate",
    "amazonExceptionCount",
    "reviewNavCount",
  ].forEach((id) => setText(id, "0"));
  setText("flowMarginRate", "0%");
  setText("flowApproveRate", "0%");
  setText("flowRiskBreakdown", "0 Low - 0 Med - 0 High");
  setText("flowReviewNote", "0 routed to Review");
  setText("p21SkuCount", "0 SKUs");
  setText("amazonCandidateCount", "0 candidates");
}

function renderQueue(rows) {
  document.querySelector("#queueCount").textContent = `${formatInteger(rows.length)} products`;

  if (!rows.length) {
    productQueue.innerHTML = '<div class="empty-state">No products match the current filters.</div>';
    return;
  }

  productQueue.innerHTML = rows.map((item) => {
    const decision = item.decision || {};
    const isPush = isLiveListing(item);
    const isSelected = item.recordId === mainState.selectedRecordId;

    return `
      <article class="product-card${isSelected ? " is-selected" : ""}" data-record-id="${escapeAttr(item.recordId)}">
        <div class="card-topline">
          <strong>${escapeHtml(item.sku || "-")}</strong>
          <span class="decision-pill ${isPush ? "push" : "review"}">${escapeHtml(decision.label || "-")}</span>
        </div>
        <div class="product-main">
          <img class="product-image" src="${escapeAttr(item.imageUrl || "")}" alt="">
          <div>
            <h3>${escapeHtml(item.name || "-")}</h3>
            <p class="product-meta">${escapeHtml(item.brand || "-")} / ${escapeHtml(item.category || "Uncategorized")}</p>
          </div>
        </div>
        <div class="score-bar"><span style="width:${Math.min(Math.max(item.researchScore || 0, 0), 100)}%"></span></div>
        <div class="card-metrics">
          <div><span class="metric-label">Score</span><strong>${formatInteger(item.researchScore || 0)}/100</strong></div>
          <div><span class="metric-label">Cost</span><strong>${formatMoney(item.Cost || economicsCost(item) || 0)}</strong></div>
          <div><span class="metric-label">Revenue</span><strong>${formatMoney(item.monthlyRevenue || 0)}</strong></div>
          <div><span class="metric-label">Margin</span><strong>${formatNumber(item.economics?.contributionMarginPercent || 0, 1)}%</strong></div>
          <div><span class="metric-label">Risk</span><strong>${escapeHtml(item.riskAnalysis?.level || "-")}</strong></div>
        </div>
      </article>
    `;
  }).join("");
}

function selectedItem(allRows, visible) {
  return (
    allRows.find((item) => item.recordId === mainState.selectedRecordId) ||
    visible[0] ||
    allRows[0]
  );
}

function renderStudio(item) {
  if (!item) {
    studioSku.textContent = "No SKU";
    studioScore.textContent = "0/100";
    studioBody.innerHTML = '<div class="empty-state">No product is selected.</div>';
    return;
  }

  const decision = item.decision || {};
  const isPush = isLiveListing(item);
  const economics = item.economics || {};
  const pricing = item.pricingBasis || {};
  const push = item.pushRecommendation || {};

  studioSku.textContent = item.sku || "-";
  studioScore.textContent = `${formatInteger(item.researchScore || 0)}/100`;
  studioBody.innerHTML = `
    <section class="studio-product">
      <img class="studio-image" src="${escapeAttr(item.imageUrl || "")}" alt="">
      <div>
        <span class="decision-pill ${isPush ? "push" : "review"}">${escapeHtml(decision.label || "-")}</span>
        <h3>${escapeHtml(item.name || "-")}</h3>
        <div class="tag-row">
          <span class="tag">${escapeHtml(item.brand || "-")}</span>
          <span class="tag">${escapeHtml(item.category || "Uncategorized")}</span>
          <span class="tag">SKU ${escapeHtml(item.sku || "-")}</span>
          <span class="tag">ASIN ${escapeHtml(item.asin || "-")}</span>
        </div>
      </div>
    </section>

    <section class="studio-metrics">
      <div><span class="metric-label">Monthly revenue</span><strong>${formatMoney(item.monthlyRevenue || 0)}</strong></div>
      <div><span class="metric-label">Cost</span><strong>${formatMoney(item.Cost || economics.Cost || 0)}</strong></div>
      <div><span class="metric-label">Recommended price</span><strong>${formatMoney(item.recommendedAmazonPrice || 0)}</strong></div>
      <div><span class="metric-label">Margin</span><strong>${formatNumber(economics.contributionMarginPercent || 0, 1)}%</strong></div>
      <div><span class="metric-label">Risk</span><strong><span class="risk-pill ${String(item.riskAnalysis?.level || "").toLowerCase()}">${escapeHtml(item.riskAnalysis?.level || "-")}</span></strong></div>
    </section>

    <section class="panel-block">
      <h3>Decision gates</h3>
      <div class="criteria-grid">${renderCriteria(item.criteria || {})}</div>
    </section>

    <section class="panel-block">
      <h3>Pricing basis</h3>
      <div class="pricing-basis">
        <div><span class="metric-label">Required margin</span><strong>${formatNumber(pricing.requiredMarginPercent || economics.requiredMarginPercent || 0, 1)}%</strong></div>
        <div><span class="metric-label">Target margin</span><strong>${formatNumber(pricing.targetMarginPercent || economics.targetMarginPercent || 0, 1)}%</strong></div>
        <div><span class="metric-label">Lowest FBA</span><strong>${formatMoney(pricing.lowestFbaCompetitorPrice || 0)}</strong></div>
      </div>
    </section>

    <section class="panel-block">
      <h3>Competitors</h3>
      <ul class="competitor-list">${renderCompetitors(item.competitors || [])}</ul>
    </section>

    <section class="panel-block">
      <h3>Risk analysis</h3>
      <ul class="risk-list">${renderRiskFactors(item.riskAnalysis?.factors || [])}</ul>
    </section>

    <section class="panel-block">
      <h3>Why this decision</h3>
      <ul class="why-list">${(item.explanation || []).map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>
    </section>

    <section class="push-suggestion ${isPush ? "push" : "review"}">
      <div>
        <span class="criteria-pill ${isPush ? "pass" : "fail"}">${isPush ? "Ready to push" : "Review first"}</span>
        <h3>${escapeHtml(push.priceAction || decision.label || "-")}</h3>
        <p>${escapeHtml(push.message || decision.reason || "")}</p>
        <dl class="suggestion-list">
          <div><dt>SKU</dt><dd>${escapeHtml(push.sku || item.sku || "-")}</dd></div>
          <div><dt>ASIN</dt><dd>${escapeHtml(push.asin || item.asin || "-")}</dd></div>
          <div><dt>Risk</dt><dd>${escapeHtml(push.riskLevel || item.riskAnalysis?.level || "-")}</dd></div>
        </dl>
        <ul class="why-list">${(push.nextSteps || []).map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>
      </div>
      <div class="push-price">
        <span>Recommended price</span>
        <strong>${formatMoney(push.recommendedPrice || item.recommendedAmazonPrice || 0)}</strong>
      </div>
    </section>
  `;
}

function renderCriteria(criteria) {
  const labels = {
    revenue: "Revenue",
    fbaCompetitive: "FBA fit",
    margin: "Margin",
  };

  return Object.entries(criteria).map(([key, value]) => `
    <article class="criteria-card">
      <span class="criteria-pill ${value.passed ? "pass" : "fail"}">${value.passed ? "Clear" : "Review"}</span>
      <h3>${labels[key] || titleCase(key)}</h3>
      <p>${escapeHtml(value.explanation || "")}</p>
    </article>
  `).join("");
}

function renderCompetitors(competitors) {
  if (!competitors.length) {
    return '<li class="empty-state">No competitor records are linked to this SKU.</li>';
  }

  return competitors.slice(0, 5).map((competitor) => `
    <li class="competitor-row">
      <span class="rank-badge">${formatInteger(competitor.rank || 0)}</span>
      <div>
        <strong>${escapeHtml(competitor.sellerName || competitor.brand || "-")}</strong>
        <span>${escapeHtml(competitor.title || "-")}</span>
        <span>${escapeHtml(competitor.fulfillmentType || "-")} / ${escapeHtml(competitor.matchConfidence || "unknown")} match</span>
      </div>
      <div class="price-stack">
        <strong>${formatMoney(competitor.estimatedPrice || 0)}</strong>
      </div>
    </li>
  `).join("");
}

function economicsCost(item) {
  return Number(item?.economics?.Cost || 0);
}

function isLiveListing(item) {
  return (
    item?.approvalStatus === "APPROVED_BY_USER" ||
    ["PUSH_TO_AMAZON", "REPRICE_AND_PUSH"].includes(item?.decision?.action)
  );
}

function renderRiskFactors(factors) {
  if (!factors.length) {
    return '<li>No risk factors returned.</li>';
  }

  return factors.map((factor) => `
    <li class="${String(factor.level || "").toLowerCase()}">
      <strong>${escapeHtml(factor.name || "-")} / ${escapeHtml(factor.level || "-")}</strong>
      <span>${escapeHtml(factor.message || "")}</span>
    </li>
  `).join("");
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: Number(value || 0) >= 1000 ? 0 : 2,
  }).format(Number(value || 0));
}

function percent(value, total) {
  return total ? Math.round((Number(value || 0) / Number(total || 1)) * 100) : 0;
}

function setText(id, value) {
  const element = document.querySelector(`#${id}`);
  if (element) {
    element.textContent = value;
  }
}

function formatInteger(value) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function formatNumber(value, decimals = 0) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number(value || 0));
}

function titleCase(value) {
  return String(value || "")
    .replace(/([A-Z])/g, " $1")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .trim();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function debounce(callback, delay) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(...args), delay);
  };
}
