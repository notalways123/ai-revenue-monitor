// Charts — ECharts rendering for all dashboard views

const COLORS = {
  anthro: '#d4a44c',
  anthroLight: 'rgba(212,164,76,0.15)',
  anthroBand: 'rgba(212,164,76,0.08)',
  openai: '#10a37f',
  openaiLight: 'rgba(16,163,127,0.15)',
  openaiBand: 'rgba(16,163,127,0.08)',
  danger: '#ef4444',
  text2: '#8892a4',
  border: '#243049',
};

let currentBasis = 'as-reported';
const charts = {};

function initCharts() {
  // Tab switching
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
      // Resize charts on tab switch
      setTimeout(() => Object.values(charts).forEach(c => c.resize()), 50);
    });
  });

  // Basis toggle
  document.querySelectorAll('.basis-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.basis-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentBasis = btn.dataset.basis;
      renderOverview();
    });
  });

  renderHeader();
  renderOverview();
  renderAnthropicDetail();
  renderOpenAIDetail();
  renderSourceTable();
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

function baseAxis() {
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

function getAdjustedPoints(company) {
  const raw = company === 'anthropic' ? DASH_DATA.anthropic.revenue_points : DASH_DATA.openai.revenue_points;
  if (currentBasis === 'as-reported') return raw;
  return adjustSeries(raw, currentBasis, DASH_DATA.comparability_params);
}

// ---- Header ----
function renderHeader() {
  const a = DASH_DATA.anthropic.latest;
  const o = DASH_DATA.openai.latest;
  document.getElementById('header-metrics').innerHTML = `
    <div><span style="color:${COLORS.anthro}">ANTH</span> $${a.revenue_b}B <span style="color:var(--text2);font-size:11px">${a.reporting_basis}</span></div>
    <div><span style="color:${COLORS.openai}">OAI</span> $${o.revenue_b}B <span style="color:var(--text2);font-size:11px">${o.reporting_basis}</span></div>
  `;
}

// ---- Overview ----
function renderOverview() {
  const aPts = getAdjustedPoints('anthropic');
  const oPts = getAdjustedPoints('openai');
  const basisLabel = currentBasis === 'as-reported' ? '' : ` (${currentBasis})`;

  // Metrics
  const aLatest = aPts[aPts.length - 1];
  const oLatest = oPts[oPts.length - 1];
  const aQoq = DASH_DATA.anthropic.qoq;
  const oQoq = DASH_DATA.openai.qoq;
  const co = DASH_DATA.comparison.crossover_net;

  document.getElementById('overview-metrics').innerHTML = `
    <div class="metric-card anthro"><div class="label">Anthropic ARR${basisLabel}</div><div class="value">$${aLatest.revenue_b}B</div><div class="sub">${aLatest.date}</div></div>
    <div class="metric-card openai"><div class="label">OpenAI ARR${basisLabel}</div><div class="value">$${oLatest.revenue_b}B</div><div class="sub">${oLatest.date}</div></div>
    <div class="metric-card"><div class="label">Revenue Gap</div><div class="value" style="color:${aLatest.revenue_b >= oLatest.revenue_b ? COLORS.anthro : COLORS.openai}">$${Math.abs(aLatest.revenue_b - oLatest.revenue_b).toFixed(1)}B</div><div class="sub">${aLatest.revenue_b >= oLatest.revenue_b ? 'Anthropic leads' : 'OpenAI leads'}</div></div>
    <div class="metric-card"><div class="label">Crossover</div><div class="value" style="color:${co.crossover_found ? '#22c55e' : COLORS.text2}">${co.crossover_found ? co.crossover_date : 'N/A'}</div><div class="sub">on ${currentBasis === 'as-reported' ? 'net' : currentBasis} basis</div></div>
  `;

  // Trajectory chart
  const traj = makeChart('chart-trajectory');
  if (traj) {
    const aForecast = DASH_DATA.anthropic.forecast_ensemble;
    const oForecast = DASH_DATA.openai.forecast_ensemble;
    traj.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { textStyle: { color: COLORS.text2, fontSize: 11 }, top: 0 },
      grid: { left: 60, right: 20, top: 40, bottom: 30 },
      xAxis: baseAxis(),
      yAxis: valueAxis('$B'),
      series: [
        {
          name: 'Anthropic', type: 'line', color: COLORS.anthro, symbolSize: 8,
          data: aPts.map(p => [p.date, p.revenue_b]),
        },
        {
          name: 'OpenAI', type: 'line', color: COLORS.openai, symbolSize: 8,
          data: oPts.map(p => [p.date, p.revenue_b]),
        },
        ...(aForecast && aForecast.forecast ? [{
          name: 'Anthropic (forecast)', type: 'line', color: COLORS.anthro,
          lineStyle: { type: 'dashed' }, symbolSize: 0,
          data: aForecast.forecast.map(f => [f.date, f.predicted_b]),
        }] : []),
        ...(oForecast && oForecast.forecast ? [{
          name: 'OpenAI (forecast)', type: 'line', color: COLORS.openai,
          lineStyle: { type: 'dashed' }, symbolSize: 0,
          data: oForecast.forecast.map(f => [f.date, f.predicted_b]),
        }] : []),
      ],
    });
  }

  // Growth rate chart
  const growth = makeChart('chart-growth');
  if (growth) {
    growth.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { textStyle: { color: COLORS.text2, fontSize: 11 }, top: 0 },
      grid: { left: 60, right: 20, top: 40, bottom: 30 },
      xAxis: baseAxis(),
      yAxis: valueAxis('%'),
      series: [
        {
          name: 'Anthropic QoQ', type: 'bar', color: COLORS.anthro, barWidth: 8,
          data: DASH_DATA.anthropic.qoq.map(q => [q.date, q.annualized_growth_pct]),
        },
        {
          name: 'OpenAI QoQ', type: 'bar', color: COLORS.openai, barWidth: 8,
          data: DASH_DATA.openai.qoq.map(q => [q.date, q.annualized_growth_pct]),
        },
      ],
    });
  }

  // Inflection chart
  const infl = makeChart('chart-inflection');
  if (infl) {
    const aD2 = DASH_DATA.anthropic.inflections.second_derivative;
    const oD2 = DASH_DATA.openai.inflections.second_derivative;
    infl.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { textStyle: { color: COLORS.text2, fontSize: 11 }, top: 0 },
      grid: { left: 60, right: 20, top: 40, bottom: 30 },
      xAxis: baseAxis(),
      yAxis: valueAxis('Δ%/period'),
      series: [
        {
          name: 'Anthropic', type: 'line', color: COLORS.anthro, symbolSize: 6,
          data: aD2.map(d => [d.date, d.second_derivative]),
          markPoint: {
            data: aD2.filter(d => d.is_inflection).map(d => ({
              name: d.inflection_type, coord: [d.date, d.second_derivative],
              symbolSize: 30, itemStyle: { color: COLORS.danger },
            })),
          },
        },
        {
          name: 'OpenAI', type: 'line', color: COLORS.openai, symbolSize: 6,
          data: oD2.map(d => [d.date, d.second_derivative]),
          markPoint: {
            data: oD2.filter(d => d.is_inflection).map(d => ({
              name: d.inflection_type, coord: [d.date, d.second_derivative],
              symbolSize: 30, itemStyle: { color: COLORS.danger },
            })),
          },
        },
      ],
    });
  }

  // Crossover chart
  const cross = makeChart('chart-crossover');
  if (cross) {
    const aForecast = DASH_DATA.anthropic.forecast_ensemble;
    const oForecast = DASH_DATA.openai.forecast_ensemble;
    const histA = aPts.map(p => [p.date, p.revenue_b]);
    const histO = oPts.map(p => [p.date, p.revenue_b]);
    const foreA = aForecast && aForecast.forecast ? aForecast.forecast.map(f => [f.date, f.predicted_b]) : [];
    const foreO = oForecast && oForecast.forecast ? oForecast.forecast.map(f => [f.date, f.predicted_b]) : [];

    cross.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { textStyle: { color: COLORS.text2, fontSize: 11 }, top: 0 },
      grid: { left: 60, right: 20, top: 40, bottom: 30 },
      xAxis: baseAxis(),
      yAxis: valueAxis('$B'),
      series: [
        { name: 'Anthropic', type: 'line', color: COLORS.anthro, symbolSize: 6, data: histA },
        { name: 'OpenAI', type: 'line', color: COLORS.openai, symbolSize: 6, data: histO },
        { name: 'Anthropic (est)', type: 'line', color: COLORS.anthro, lineStyle: { type: 'dashed' }, symbolSize: 0, data: foreA },
        { name: 'OpenAI (est)', type: 'line', color: COLORS.openai, lineStyle: { type: 'dashed' }, symbolSize: 0, data: foreO },
      ],
    });
  }
}

// ---- Company Detail Tabs ----
function renderCompanyDetail(company) {
  const isAnthro = company === 'anthropic';
  const prefix = isAnthro ? 'anthro' : 'openai';
  const color = isAnthro ? COLORS.anthro : COLORS.openai;
  const data = DASH_DATA[company];
  const pts = data.revenue_points;
  const latest = pts[pts.length - 1];

  // Metrics
  const qoq = data.qoq;
  const latestQoq = qoq.length > 0 ? qoq[qoq.length - 1] : null;
  const yoy = data.yoy;
  const latestYoy = yoy.length > 0 ? yoy[yoy.length - 1] : null;
  const infl = data.inflections.inflections;

  document.getElementById(prefix + '-metrics').innerHTML = `
    <div class="metric-card" style="border-left:3px solid ${color}"><div class="label">Latest ARR</div><div class="value" style="color:${color}">$${latest.revenue_b}B</div><div class="sub">${latest.date} · ${latest.reporting_basis}</div></div>
    <div class="metric-card"><div class="label">QoQ Annualized</div><div class="value">${latestQoq ? latestQoq.annualized_growth_pct + '%' : 'N/A'}</div><div class="sub">${latestQoq ? latestQoq.date : ''}</div></div>
    <div class="metric-card"><div class="label">YoY Growth</div><div class="value">${latestYoy ? latestYoy.yoy_growth_pct + '%' : 'N/A'}</div><div class="sub">${latestYoy ? latestYoy.date : ''}</div></div>
    <div class="metric-card"><div class="label">Inflections</div><div class="value" style="color:${infl.length > 0 ? COLORS.danger : COLORS.text2}">${infl.length}</div><div class="sub">${infl.map(i => i.inflection_type).join(', ') || 'none'}</div></div>
  `;

  // Trajectory
  const traj = makeChart(`chart-${prefix}-trajectory`);
  if (traj) {
    const fc = data.forecast_ensemble;
    traj.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      xAxis: baseAxis(),
      yAxis: valueAxis('$B'),
      series: [
        {
          type: 'line', color, symbolSize: 10,
          data: pts.map(p => [p.date, p.revenue_b]),
          label: {
            show: true, position: 'top', fontSize: 9, color: COLORS.text2,
            formatter: p => '$' + p.value[1] + 'B',
          },
        },
        ...(fc && fc.forecast ? [{
          type: 'line', color, lineStyle: { type: 'dashed' }, symbolSize: 0,
          data: fc.forecast.map(f => [f.date, f.predicted_b]),
        }] : []),
        ...(fc && fc.confidence_interval_80 ? [{
          type: 'line', color, areaStyle: { opacity: 0.08 }, symbolSize: 0, lineStyle: { opacity: 0 },
          data: fc.confidence_interval_80.upper.map((u, i) => [fc.forecast[i].date, u]),
        }] : []),
      ],
    });
  }

  // Growth
  const growth = makeChart(`chart-${prefix}-growth`);
  if (growth) {
    growth.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      xAxis: baseAxis(),
      yAxis: valueAxis('%'),
      series: [
        {
          type: 'bar', color, barWidth: 12,
          data: data.qoq.map(q => [q.date, q.annualized_growth_pct]),
        },
        {
          type: 'line', color: COLORS.text2, symbolSize: 4,
          data: data.yoy.map(y => [y.date, y.yoy_growth_pct]),
        },
      ],
    });
  }

  // Inflection
  const inflChart = makeChart(`chart-${prefix}-inflection`);
  if (inflChart) {
    const d2 = data.inflections.second_derivative;
    inflChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      xAxis: baseAxis(),
      yAxis: valueAxis('Δ%'),
      series: [{
        type: 'line', color, symbolSize: 6,
        data: d2.map(d => [d.date, d.second_derivative]),
        markPoint: {
          data: d2.filter(d => d.is_inflection).map(d => ({
            name: d.inflection_type,
            coord: [d.date, d.second_derivative],
            symbolSize: 30,
            itemStyle: { color: COLORS.danger },
            label: { show: true, formatter: d.inflection_type.replace('growth_', ''), fontSize: 8, color: '#fff' },
          })),
        },
        markLine: { data: [{ yAxis: 0, lineStyle: { color: COLORS.border, type: 'dashed' } }] },
      }],
    });
  }
}

function renderAnthropicDetail() { renderCompanyDetail('anthropic'); }
function renderOpenAIDetail() { renderCompanyDetail('openai'); }

// ---- Source Table ----
function renderSourceTable() {
  const all = [
    ...DASH_DATA.anthropic.revenue_points,
    ...DASH_DATA.openai.revenue_points,
  ].sort((a, b) => b.date.localeCompare(a.date));

  const tbody = document.querySelector('#source-table tbody');

  function renderRows(data) {
    tbody.innerHTML = data.map(p => `
      <tr>
        <td>${p.date}</td>
        <td><span class="tag ${p.company === 'anthropic' ? 'tag-anthro' : 'tag-openai'}">${p.company}</span></td>
        <td>$${p.revenue_b}B</td>
        <td>${p.metric_type}</td>
        <td>${p.reporting_basis}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${p.source}</td>
        <td><span class="conf-${p.confidence}">${p.confidence}</span></td>
        <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;font-size:11px;color:var(--text2)">${p.notes || ''}</td>
      </tr>
    `).join('');
  }

  renderRows(all);

  document.getElementById('filter-company').addEventListener('change', e => {
    const conf = document.getElementById('filter-confidence').value;
    let filtered = e.target.value === 'all' ? all : all.filter(p => p.company === e.target.value);
    if (conf !== 'all') filtered = filtered.filter(p => p.confidence === conf);
    renderRows(filtered);
  });

  document.getElementById('filter-confidence').addEventListener('change', e => {
    const comp = document.getElementById('filter-company').value;
    let filtered = comp === 'all' ? all : all.filter(p => p.company === comp);
    if (e.target.value !== 'all') filtered = filtered.filter(p => p.confidence === e.target.value);
    renderRows(filtered);
  });
}

// ---- Boot ----
(async () => {
  await loadDashboardData();
  initCharts();
})();
