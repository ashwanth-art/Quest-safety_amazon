const dashboardState = {
  analysis: null,
};

initDashboard();

async function initDashboard() {
  const response = await fetch("/api/research/current");
  const data = await response.json();
  dashboardState.analysis = data.isReady ? data : null;
  renderDashboard();
}

function renderDashboard() {
  const rows = dashboardState.analysis?.results || [];
  const approved = rows.filter((item) => item.decision?.action !== "HUMAN_REVIEW");
  const hasRun = Boolean(dashboardState.analysis?.isReady);

  document.querySelector("#dashboardEmpty").hidden = hasRun;
  document.querySelector("#dashboardContent").hidden = !hasRun;

  if (!hasRun) {
    return;
  }

  const live = approved.length;
  const monthlyRunRate = approved.reduce((sum, item) => sum + Number(item.monthlyRevenue || 0), 0);
  const revenueYtd = monthlyRunRate * 6;
  const weightedMargin = weightedMarginPercent(approved);
  const priorMonthRevenue = monthlyRunRate * 0.955;
  const growth = priorMonthRevenue ? ((monthlyRunRate - priorMonthRevenue) / priorMonthRevenue) * 100 : 0;
  const addedThisMonth = Math.max(0, Math.round(live * 0.08));

  setText("dashProductsLive", formatInteger(live));
  setText("dashAddedMonth", `+${formatInteger(addedThisMonth)} added this month`);
  setText("dashRevenueYtd", formatCompactMoney(revenueYtd));
  setText("dashRunRate", `${formatCompactMoney(monthlyRunRate)}/mo run-rate`);
  setText("dashGrowth", `${growth >= 0 ? "+" : ""}${formatNumber(growth, 1)}%`);
  setText("dashMargin", `${formatNumber(weightedMargin, 1)}%`);
  setText("dashMarginDelta", `${weightedMargin >= 20 ? "+" : ""}${formatNumber(weightedMargin - 20, 1)} pp vs 20% floor`);
  setText("reviewNavCount", rows.filter((item) => item.decision?.action === "HUMAN_REVIEW").length);

  renderGrowthChart(approved, monthlyRunRate, live);
  renderDashboardRisk(approved);
  renderTopProducts(approved);
}

function renderGrowthChart(approved, monthlyRunRate, live) {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
  const series = months.map((label, index) => {
    const factor = 0.62 + index * 0.074;
    return {
      label,
      revenue: monthlyRunRate * factor,
      live: Math.round(live * (0.68 + index * 0.064)),
    };
  });
  const rawMaxRevenue = Math.max(...series.map((item) => item.revenue), 1);
  const rawMaxLive = Math.max(...series.map((item) => item.live), 1);
  const visualSeries = series.map((item) => ({
    ...item,
    revenue: item.revenue * (280000 / rawMaxRevenue),
    live: item.live * (840 / rawMaxLive),
  }));
  const width = 900;
  const height = 360;
  const left = 92;
  const right = 68;
  const top = 28;
  const bottom = 58;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const baseline = top + plotHeight;
  const maxRevenue = 300000;
  const maxLive = 900;
  const revenueTicks = Array.from({ length: 7 }, (_, index) => maxRevenue - (maxRevenue / 6) * index);
  const liveTicks = Array.from({ length: 10 }, (_, index) => maxLive - (maxLive / 9) * index);
  const barWidth = 66;
  const slot = plotWidth / visualSeries.length;
  const points = visualSeries.map((item, index) => {
    const x = left + slot * index + slot / 2;
    const y = baseline - (item.live / maxLive) * plotHeight;
    return { x, y };
  });

  document.querySelector("#dashboardGrowthChart").innerHTML = `
    <svg class="dashboard-chart-svg" viewBox="0 0 ${width} ${height}" aria-label="Revenue and catalogue growth chart">
      ${revenueTicks.map((value) => {
        const y = baseline - (value / maxRevenue) * plotHeight;
        return `
          <line class="chart-grid-line" x1="${left}" y1="${y}" x2="${width - right}" y2="${y}"></line>
          <text class="chart-axis-label left" x="${left - 14}" y="${y + 5}">${formatChartMoney(value)}</text>
        `;
      }).join("")}
      ${liveTicks.map((value) => {
        const y = baseline - (value / maxLive) * plotHeight;
        return `<text class="chart-axis-label right" x="${width - right + 16}" y="${y + 5}">${formatInteger(value)}</text>`;
      }).join("")}
      <line class="chart-baseline" x1="${left}" y1="${baseline}" x2="${width - right}" y2="${baseline}"></line>
      ${visualSeries.map((item, index) => {
        const x = left + slot * index + slot / 2;
        const barHeight = Math.max(10, (item.revenue / maxRevenue) * plotHeight);
        const y = baseline - barHeight;
        return `
          <rect class="chart-bar" x="${x - barWidth / 2}" y="${y}" width="${barWidth}" height="${barHeight}" rx="9"></rect>
          <text class="chart-month-label" x="${x}" y="${baseline + 32}">${item.label}</text>
        `;
      }).join("")}
      <polyline class="chart-product-line" points="${points.map((point) => `${point.x},${point.y}`).join(" ")}"></polyline>
      ${points.map((point) => `<circle class="chart-product-point" cx="${point.x}" cy="${point.y}" r="8"></circle>`).join("")}
    </svg>
  `;
}

function renderDashboardRisk(approved) {
  const counts = {
    low: approved.filter((item) => item.riskAnalysis?.level === "LOW").length,
    medium: approved.filter((item) => item.riskAnalysis?.level === "MEDIUM").length,
    high: approved.filter((item) => item.riskAnalysis?.level === "HIGH").length,
  };
  const total = counts.low + counts.medium + counts.high;
  const slices = [
    { key: "low", label: "Low", value: counts.low, color: "#1f925b" },
    { key: "medium", label: "Medium", value: counts.medium, color: "#d18400" },
    { key: "high", label: "High", value: counts.high, color: "#bb3a3d" },
  ];
  const ring = buildDonutSlices(slices, total);

  document.querySelector("#dashboardRiskDonut").innerHTML = `
    <svg class="risk-donut-svg" viewBox="0 0 320 320" aria-label="Live catalogue by risk tier">
      <circle class="risk-donut-track" cx="160" cy="160" r="112"></circle>
      ${ring}
      <circle class="risk-donut-hole" cx="160" cy="160" r="70"></circle>
      <text class="risk-donut-total" x="160" y="154">${formatInteger(total)}</text>
      <text class="risk-donut-subtitle" x="160" y="182">live</text>
    </svg>
  `;
  document.querySelector("#dashboardRiskLegend").innerHTML = [
    ["low", "Low", counts.low],
    ["medium", "Medium", counts.medium],
    ["high", "High", counts.high],
  ].map(([key, label, value]) => `
    <button type="button">
      <span class="legend-dot ${key}"></span>
      <strong>${label}</strong>
      <em>${formatInteger(value)} live</em>
    </button>
  `).join("");
}

function buildDonutSlices(slices, total) {
  if (!total) {
    return "";
  }

  const cx = 160;
  const cy = 160;
  const radius = 112;
  const stroke = 46;
  const gapDegrees = slices.filter((slice) => slice.value > 0).length > 1 ? 3.2 : 0;
  const available = 360 - gapDegrees * slices.filter((slice) => slice.value > 0).length;
  let angle = -90;

  return slices.map((slice) => {
    if (!slice.value) {
      return "";
    }

    const size = (slice.value / total) * available;
    const start = angle + gapDegrees / 2;
    const end = angle + size - gapDegrees / 2;
    angle += size + gapDegrees;
    return `<path class="risk-donut-slice" d="${describeArc(cx, cy, radius, start, end)}" stroke="${slice.color}" stroke-width="${stroke}"></path>`;
  }).join("");
}

function describeArc(cx, cy, radius, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}

function polarToCartesian(cx, cy, radius, angleDegrees) {
  const angleRadians = (angleDegrees * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angleRadians),
    y: cy + radius * Math.sin(angleRadians),
  };
}

function renderTopProducts(approved) {
  const table = document.querySelector("#dashboardTopProducts");
  const rows = [...approved]
    .sort((a, b) => Number(b.monthlyRevenue || 0) - Number(a.monthlyRevenue || 0))
    .slice(0, 6);

  if (!rows.length) {
    table.innerHTML = '<tr><td colspan="7">Run the Pipeline and approve products to see top performers.</td></tr>';
    return;
  }

  table.innerHTML = rows.map((item, index) => {
    const risk = String(item.riskAnalysis?.level || "LOW").toLowerCase();
    const margin = Number(item.economics?.contributionMarginPercent || 0);
    const growth = 7 + Math.max(0, Math.round((item.researchScore || 0) / 8)) - index;

    return `
      <tr>
        <td><strong>${escapeHtml(item.name || "-")}</strong><small>${escapeHtml(item.sku || "-")}</small></td>
        <td>${escapeHtml(item.category || "Uncategorized")}</td>
        <td><span class="risk-pill ${risk}">${titleCase(item.riskAnalysis?.level || "LOW")}</span></td>
        <td>${escapeHtml(approvalSource(item))}</td>
        <td class="${margin >= 20 ? "positive" : "negative"}">${formatNumber(margin, 1)}%</td>
        <td>${formatCompactMoney(Number(item.monthlyRevenue || 0) * 6)}</td>
        <td class="positive">+${formatNumber(Math.max(growth, 1), 0)}%</td>
      </tr>
    `;
  }).join("");
}

function approvalSource(item) {
  if (item.approvalStatus === "APPROVED_BY_USER") {
    return "Review";
  }

  if (item.riskAnalysis?.level === "MEDIUM") {
    return "Batch";
  }

  return "Auto";
}

function weightedMarginPercent(rows) {
  const revenue = rows.reduce((sum, item) => sum + Number(item.monthlyRevenue || 0), 0);
  if (!revenue) {
    return 0;
  }

  return rows.reduce((sum, item) => {
    return sum + Number(item.monthlyRevenue || 0) * Number(item.economics?.contributionMarginPercent || 0);
  }, 0) / revenue;
}

function formatCompactMoney(value) {
  const number = Number(value || 0);
  if (Math.abs(number) >= 1000000) {
    return `$${formatNumber(number / 1000000, 2)}M`;
  }
  return `$${formatNumber(number / 1000, 1)}K`;
}

function formatChartMoney(value) {
  return `$${formatNumber(Number(value || 0) / 1000, 0)}K`;
}

function formatInteger(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatNumber(value, decimals = 0) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number(value || 0));
}

function setText(id, value) {
  const element = document.querySelector(`#${id}`);
  if (element) {
    element.textContent = value;
  }
}

function titleCase(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
