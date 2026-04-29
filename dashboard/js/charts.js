// Charts — 3-chart layout: Actual, Anthropic detail, OpenAI detail

const COLORS = {
  anthro: '#d4a44c',
  anthroLight: 'rgba(212,164,76,0.15)',
  anthroBand: 'rgba(212,164,76,0.08)',
  openai: '#10a37f',
  openaiLight: 'rgba(16,163,127,0.15)',
  openaiBand: 'rgba(16,163,127,0.08)',
  anthroTarget: '#f59e0b',
  openaiTarget: '#06b6d4',
  text2: '#8892a4',
  border: '#243049',
};

const charts = {};

function initCharts() {
  renderHeader();
  renderMetrics();
  renderActualChart();
  renderAnthropicDetail();
  renderOpenAIDetail();
  document.getElementById('generated-at').textContent = 'Generated: ' + DASH_DATA.generated_at;
}

function makeChart(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  if (charts[id]) charts[id].dispose();
  charts[id] = echarts.init(el, null, { renderer: 'canvas' });
  window.addEventListener('resize', () => charts[id] && charts[id].resize());
  return charts[id];
}

function timeAxis() {
  return {
    type: 'time',
    axisLine: { lineStyle: { color: COLORS.border } },
    axisLabel: { color: COLORS.text2, fontSize: 10 },
    splitLine: { lineStyle: { color: COLORS.border, opacity: 0.3 } },
  };
}

function valueAxis(name) {
  return {
    type: 'value',
    name: name || '',
    nameTextStyle: { color: COLORS.text2, fontSize: 10 },
    axisLine: { lineStyle: { color: COLORS.border } },
    axisLabel: { color: COLORS.text2, fontSize: 10 },
    splitLine: { lineStyle: { color: COLORS.border, opacity: 0.3 } },
  };
}

// ---- Header & Metrics ----
function renderHeader() {
  const a = DASH_DATA.anthropic.latest;
  const o = DASH_DATA.openai.latest;
  document.getElementById('header-metrics').innerHTML = `
    <div><span style="color:${COLORS.anthro}">ANTH</span> $${a.revenue_b}B <span style="color:var(--text2);font-size:11px">${a.reporting_basis}</span></div>
    <div><span style="color:${COLORS.openai}">OAI</span> $${o.revenue_b}B <span style="color:var(--text2);font-size:11px">${o.reporting_basis}</span></div>
  `;
}

function renderMetrics() {
  const a = DASH_DATA.anthropic;
  const o = DASH_DATA.openai;
  const aQoq = a.qoq.length > 0 ? a.qoq[a.qoq.length - 1] : null;
  const oQoq = o.qoq.length > 0 ? o.qoq[o.qoq.length - 1] : null;

  // Anthropic EOY forecast values (find closest to Dec)
  const aFc = a.forecast_ensemble;
  const aFc2027 = findYearEndForecast(aFc, 2027);
  const aFc2028 = findYearEndForecast(aFc, 2028);
  const aFc2029 = findYearEndForecast(aFc, 2029);
  const aFc2030 = findYearEndForecast(aFc, 2030);

  // OpenAI EOY forecast values
  const oFc = o.forecast_ensemble;
  const oFc2027 = findYearEndForecast(oFc, 2027);
  const oFc2028 = findYearEndForecast(oFc, 2028);
  const oFc2029 = findYearEndForecast(oFc, 2029);
  const oFc2030 = findYearEndForecast(oFc, 2030);

  document.getElementById('key-metrics').innerHTML = `
    <div class="metric-card anthro"><div class="label">Anthropic ARR</div><div class="value">$${a.latest.revenue_b}B</div><div class="sub">${a.latest.date} · QoQ ${aQoq ? aQoq.annualized_growth_pct + '%' : 'N/A'}</div></div>
    <div class="metric-card openai"><div class="label">OpenAI ARR</div><div class="value">$${o.latest.revenue_b}B</div><div class="sub">${o.latest.date} · QoQ ${oQoq ? oQoq.annualized_growth_pct + '%' : 'N/A'}</div></div>
    <div class="metric-card"><div class="label">Anthropic 2027E</div><div class="value" style="color:${COLORS.anthro}">$${aFc2027}B</div><div class="sub">EOY forecast</div></div>
    <div class="metric-card"><div class="label">Anthropic 2030E</div><div class="value" style="color:${COLORS.anthroTarget}">$${aFc2030}B</div><div class="sub">forecast / target $180B</div></div>
    <div class="metric-card"><div class="label">OpenAI 2027E</div><div class="value" style="color:${COLORS.openai}">$${oFc2027}B</div><div class="sub">EOY forecast</div></div>
    <div class="metric-card"><div class="label">OpenAI 2030E</div><div class="value" style="color:${COLORS.openaiTarget}">$${oFc2030}B</div><div class="sub">forecast / target $213B</div></div>
  `;
}

function findYearEndForecast(fc, year) {
  if (!fc || !fc.forecast) return '—';
  // Find the forecast point closest to December of the given year
  for (const f of fc.forecast) {
    if (f.date.startsWith(year + '-12')) return f.predicted_b;
  }
  // Fallback: find the last point in that year
  for (const f of fc.forecast) {
    if (f.date.startsWith(year + '-')) return f.predicted_b;
  }
  return '—';
}

// ---- Chart 1: Actual ARR (both companies, historical only) ----
function renderActualChart() {
  const chart = makeChart('chart-actual');
  if (!chart) return;

  const aPts = DASH_DATA.anthropic.revenue_points;
  const oPts = DASH_DATA.openai.revenue_points;

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: params => {
        let s = params[0].axisValueLabel + '<br/>';
        params.forEach(p => {
          s += `${p.marker} ${p.seriesName}: $${p.value[1]}B<br/>`;
        });
        return s;
      },
    },
    legend: { textStyle: { color: COLORS.text2, fontSize: 11 }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 30 },
    xAxis: timeAxis(),
    yAxis: valueAxis('$B'),
    series: [
      {
        name: 'Anthropic', type: 'line', color: COLORS.anthro, symbolSize: 10,
        lineStyle: { width: 2 },
        data: aPts.map(p => [p.date, p.revenue_b]),
        label: {
          show: true, position: 'top', fontSize: 10, color: COLORS.anthro,
          formatter: p => '$' + p.value[1] + 'B',
        },
      },
      {
        name: 'OpenAI', type: 'line', color: COLORS.openai, symbolSize: 10,
        lineStyle: { width: 2 },
        data: oPts.map(p => [p.date, p.revenue_b]),
        label: {
          show: true, position: 'bottom', fontSize: 10, color: COLORS.openai,
          formatter: p => '$' + p.value[1] + 'B',
        },
      },
    ],
  });
}

// ---- Chart 2: Anthropic detail (historical + forecast + target) ----
function renderAnthropicDetail() {
  renderCompanyDetail('anthropic');
}

// ---- Chart 3: OpenAI detail (historical + forecast + target) ----
function renderOpenAIDetail() {
  renderCompanyDetail('openai');
}

function renderCompanyDetail(company) {
  const isAnthro = company === 'anthropic';
  const chartId = isAnthro ? 'chart-anthro-detail' : 'chart-openai-detail';
  const chart = makeChart(chartId);
  if (!chart) return;

  const color = isAnthro ? COLORS.anthro : COLORS.openai;
  const targetColor = isAnthro ? COLORS.anthroTarget : COLORS.openaiTarget;
  const data = DASH_DATA[company];
  const pts = data.revenue_points;
  const fc = data.forecast_ensemble;

  const histData = pts.map(p => [p.date, p.revenue_b]);
  const forecastData = fc && fc.forecast ? fc.forecast.map(f => [f.date, f.predicted_b]) : [];
  const ciUpper = fc && fc.confidence_interval_80 && fc.forecast
    ? fc.confidence_interval_80.upper.map((u, i) => [fc.forecast[i].date, u]) : [];
  const ciLower = fc && fc.confidence_interval_80 && fc.forecast
    ? fc.confidence_interval_80.lower.map((l, i) => [fc.forecast[i].date, l]) : [];
  const targetData = fc && fc.arr_targets ? fc.arr_targets.map(t => [t.date, t.revenue_b]) : [];
  const targetLabels = fc && fc.arr_targets ? fc.arr_targets.map(t => t.label) : [];

  // Connect historical to forecast: add the last actual point as first forecast point for continuity
  const bridgePoint = [pts[pts.length - 1].date, pts[pts.length - 1].revenue_b];
  const connectedForecast = [bridgePoint, ...forecastData];
  const connectedUpper = [bridgePoint, ...ciUpper];
  const connectedLower = [bridgePoint, ...ciLower];

  // Mark line for year-end 2027, 2028, 2029, 2030
  const yearLines = [2027, 2028, 2029, 2030].map(y => ({
    xAxis: y + '-12-31',
    label: { show: true, formatter: y + ' EOY', color: COLORS.text2, fontSize: 9 },
    lineStyle: { color: COLORS.border, type: 'dashed', width: 1 },
  }));

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: params => {
        const date = params[0].axisValueLabel;
        let s = date + '<br/>';
        params.forEach(p => {
          if (p.value && p.value[1] != null) {
            s += `${p.marker} ${p.seriesName}: $${p.value[1]}B<br/>`;
          }
        });
        return s;
      },
    },
    legend: { textStyle: { color: COLORS.text2, fontSize: 11 }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 30 },
    xAxis: { ...timeAxis(), ...{ markLine: { data: yearLines, symbol: 'none' } } },
    yAxis: valueAxis('$B'),
    series: [
      {
        name: 'Historical ARR', type: 'line', color, symbolSize: 10, lineStyle: { width: 2.5 },
        data: histData,
        label: {
          show: true, position: 'top', fontSize: 10, color,
          formatter: p => '$' + p.value[1] + 'B',
        },
      },
      {
        name: 'Forecast', type: 'line', color,
        lineStyle: { type: 'dashed', width: 1.5 }, symbolSize: 0,
        data: connectedForecast,
      },
      {
        name: '80% CI (upper)', type: 'line', color, symbolSize: 0,
        lineStyle: { type: 'dashed', opacity: 0.25, width: 1 },
        data: connectedUpper,
      },
      {
        name: '80% CI (lower)', type: 'line', color, symbolSize: 0,
        lineStyle: { type: 'dashed', opacity: 0.25, width: 1 },
        data: connectedLower,
      },
      ...(targetData.length > 0 ? [{
        name: 'Company Target', type: 'line', color: targetColor,
        lineStyle: { type: 'dotted', width: 2 }, symbolSize: 10, symbol: 'diamond',
        data: targetData.map((t, i) => ({
          value: t,
          label: targetLabels[i] || '',
        })),
        label: {
          show: true, position: 'top', fontSize: 10, color: targetColor,
          formatter: p => p.data.label,
        },
      }] : []),
    ],
  });
}

// ---- Boot ----
(async () => {
  await loadDashboardData();
  initCharts();
})();