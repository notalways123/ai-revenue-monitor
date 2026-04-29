// Comparability adjustments — client-side gross/net toggling

function adjustPoint(dp, targetBasis, params) {
  const company = dp.company;
  const basis = dp.reporting_basis;
  const rev = dp.revenue_b;
  const result = { ...dp, original_revenue_b: rev, adjusted: false };

  if (basis === targetBasis) return result;

  if (company === 'anthropic' && targetBasis === 'net') {
    const p = params.anthropic.gross_to_net;
    result.revenue_b = +(rev - rev * p.cloud_channel_pct * p.cloud_partner_take_rate).toFixed(2);
    result.reporting_basis = 'estimated_net';
    result.adjusted = true;
  } else if (company === 'openai' && targetBasis === 'gross') {
    const p = params.openai.net_to_gross;
    result.revenue_b = +(rev + rev * p.azure_channel_pct * p.microsoft_share_rate).toFixed(2);
    result.reporting_basis = 'estimated_gross';
    result.adjusted = true;
  }

  return result;
}

function adjustSeries(points, targetBasis, params) {
  return points.map(p => adjustPoint(p, targetBasis, params));
}
