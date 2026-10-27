/* Nurtra — weekly report page logic (report.html). */
(function () {
  "use strict";

  const api = window.NurtraAPI;
  const charts = window.NurtraCharts;
  const $ = function (id) { return document.getElementById(id); };
  const shared = window.NurtraShared;

  const state = {
    weekOffset: 0,
    report: null,
  };

  // ---- Loading & rendering ------------------------------------------------

  async function loadReport(weeksBack) {
    // The report endpoint requires a session; an anonymous user is bounced
    // to login by the API client's 401 handler. Don't paint stale charts.
    if (!(await shared.requireAuth())) return;
    try {
      const res = await api.getReport(weeksBack);
      state.report = res;
      state.weekOffset = weeksBack || 0;
      renderReport(res);
      renderWeekSelect();
    } catch (err) {
      shared.toast(err.message);
    }
  }

  function renderWeekSelect() {
    const sel = $("weekSelect");
    const opts = [];
    for (let i = 0; i < 4; i++) {
      const label = i === 0 ? "Minggu ini" : i + " minggu lalu";
      opts.push('<option value="' + i + '"' + (i === state.weekOffset ? " selected" : "") + ">" + label + "</option>");
    }
    sel.innerHTML = opts.join("");
  }

  function renderReport(res) {
    charts.renderBars($("barChart"), res.bars, res.target_kcal);
    charts.renderWeight($("weightChart"), res.weights);

    // The payload nests these under stats/range; read defensively so a
    // shape change degrades to a placeholder instead of "undefined".
    const stats = res.stats || {};
    const range = res.range || {};
    const adherence = stats.adherence || {};

    $("statAdherence").textContent = (adherence.rate || 0).toFixed(0) + "%";
    $("statAvgKcal").textContent = shared.fmt(stats.avg_kcal || 0);
    $("statAvgProtein").textContent = (stats.avg_protein_g || 0).toFixed(0) + "g";
    // Hydration shows the daily average plus the goal so the reader can see
    // whether they were short, not just the raw number.
    $("statAvgWater").textContent =
      shared.fmt(stats.avg_water_ml || 0) + " ml" +
      (stats.water_target_ml ? " / " + shared.fmt(stats.water_target_ml) : "");
    $("reportRange").textContent =
      shared.fmtDate(range.start) + " — " + shared.fmtDate(range.end);

    const trend = res.weight_trend || {};
    $("trendSub").textContent = res.weights.length
      ? "Δ " + (trend.change_kg || 0).toFixed(1) + " kg · rata-rata " + (trend.avg || "-") + " kg"
      : "Belum ada data berat badan minggu ini";
  }

  // ---- AI insights ---------------------------------------------------------

  async function requestInsights() {
    if (!(await shared.requireAuth())) return;
    if (!state.report) return;
    const btn = $("btnInsights");
    btn.disabled = true;
    btn.textContent = "NumNum lagi mikirin… (±1 menit)";

    // The reasoning model can take 60-150s, so show the user it is still
    // alive instead of a frozen spinner.
    let dots = 0;
    const tick = setInterval(function () {
      dots = (dots + 1) % 4;
      btn.textContent = "NumNum berpikir" + ".".repeat(dots);
    }, 2000);

    try {
      const insights = await api.weeklyInsights(state.report);
      renderInsights(insights, state.report);
    } catch (err) {
      shared.toast(err.message);
    } finally {
      clearInterval(tick);
      btn.disabled = false;
      btn.textContent = "Minta Insight AI";
    }
  }

  function renderInsights(insights, payload) {
    $("insightsCard").hidden = false;
    $("insightSource").textContent = insights.source === "atria" ? "NumNum" : "Lokal";
    $("insightSummary").textContent = insights.summary || "";
    const sevClass = { info: "", warning: "warning", alert: "alert" };

    $("insightList").innerHTML = (insights.insights || [])
      .map(function (i) {
        return (
          '<div class="insight-item ' + (sevClass[i.severity] || "") + '">' +
          "<strong>" + shared.escapeHtml(i.title || i.type) + "</strong>" +
          shared.escapeHtml(i.detail || "") +
          "</div>"
        );
      })
      .join("");

    $("recList").innerHTML = (insights.recommendations || [])
      .map(function (r) {
        return (
          '<div class="rec-item">' +
          '<div class="rec-cat">' + shared.escapeHtml(r.category || "") + "</div>" +
          "<p>" + shared.escapeHtml(r.action || "") + "</p>" +
          '<p class="rec-why">' + shared.escapeHtml(r.rationale || "") + "</p>" +
          "</div>"
        );
      })
      .join("");

    $("insightsCard").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---- Init -----------------------------------------------------------------

  // Let the shared theme toggle re-render these SVGs with new palette tokens
  window.NurtraReport = {
    onThemeChange: function () {
      if (state.report) renderReport(state.report);
    },
  };

  function init() {
    $("btnInsights").addEventListener("click", requestInsights);
    $("weekSelect").addEventListener("change", function (e) {
      loadReport(parseInt(e.target.value, 10));
    });
    loadReport(0);

    const shared = window.NurtraShared;
    if (shared) shared.refreshAuthUI();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
