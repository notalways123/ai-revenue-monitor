// Data loader — fetches pre-computed dashboard_data.json
let DASH_DATA = null;

async function loadDashboardData() {
  const resp = await fetch('dashboard_data.json');
  DASH_DATA = await resp.json();
  return DASH_DATA;
}
