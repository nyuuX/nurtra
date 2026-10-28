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
    const historyBars = res.history && res.history.bars ? res.history.bars : [];
    renderHistory30DayChart($("historyChart"), historyBars, res.target_kcal);

    const historyWeights = res.history && res.history.weights ? res.history.weights : [];
    charts.renderWeight($("weightChart"), historyWeights);

    const stats = res.stats || {};
    const range = res.range || {};
    const adherence = stats.adherence || {};
    const hStats = res.history.stats || {};

    $("statAdherence").textContent = (adherence.rate || 0).toFixed(0) + "%";
    $("statAvgKcal").textContent = shared.fmt(hStats.avg_kcal || 0);
    $("statLoggedDays").textContent = (hStats.logged_days || 0) + " hari";
    $("statAvgProtein").textContent = (stats.avg_protein_g || 0).toFixed(0) + "g";
    $("statAvgWater").textContent =
      shared.fmt(stats.avg_water_ml || 0) + " ml" +
      (stats.water_target_ml ? " / " + shared.fmt(stats.water_target_ml) : "");
    $("reportRange").textContent =
      shared.fmtDate(range.start) + " — " + shared.fmtDate(range.end);

    const hTrend = res.history && res.history.weight_trend ? res.history.weight_trend : {};
    $("trendSub").textContent = historyWeights.length
      ? "Δ " + (hTrend.change_kg || 0).toFixed(1) + " kg · rata-rata " + (hTrend.avg || "-") + " kg (30 hari)"
      : "Belum ada data berat badan";
  }

  // ---- 30-day bar chart -----------------------------------------------------

  function renderHistory30DayChart(svg, bars, target) {
    if (!bars || !bars.length) return;
    if (!svg) return;
    const W = 1400;
    const H = 420;
    const padL = 50;
    const padR = 20;
    const padT = 20;
    const padB = 80;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;

    while (svg.firstChild) svg.removeChild(svg.firstChild);

    function el(name, attrs) {
      const node = document.createElementNS("http://www.w3.org/2000/svg", name);
      Object.keys(attrs || {}).forEach(function (key) {
        node.setAttribute(key, attrs[key]);
      });
      return node;
    }

    function cssVar(name) {
      return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    const p = {
      emerald: cssVar("--emerald") || "#10b981",
      warm: cssVar("--warm") || "#f59e0b",
      text: cssVar("--text") || "#0f172a",
      muted: cssVar("--text-muted") || "#6b7280",
      grid: cssVar("--border") || "#e5e7eb",
    };

    const maxVal = Math.max(target * 1.25, 500);
    const y = function (v) {
      return padT + innerH - (Math.min(v, maxVal) / maxVal) * innerH;
    };

    [0, 0.5, 1].forEach(function (frac) {
      const gy = padT + innerH - frac * innerH;
      svg.appendChild(el("line", {
        x1: padL, y1: gy, x2: W - padR, y2: gy,
        stroke: p.grid, "stroke-width": 1,
        "stroke-dasharray": frac === 1 ? "" : "3 5",
      }));
      const label = el("text", {
        x: padL - 8, y: gy + 4, "text-anchor": "end",
        "font-size": 12, fill: p.muted,
      });
      label.textContent = Math.round(frac * maxVal);
      svg.appendChild(label);
    });

    const slot = innerW / bars.length;
    const barW = Math.min(26, slot * 0.65);

    bars.forEach(function (b, i) {
      const cx = padL + slot * i + slot / 2;
      const logged = b.logged && b.kcal > 0;
      const h = logged ? Math.max(2, padT + innerH - y(b.kcal)) : 0;
      const rx = 4;

      if (logged) {
        svg.appendChild(el("rect", {
          x: cx - barW / 2, y: y(b.kcal), width: barW, height: h,
          rx: rx, fill: p.emerald, opacity: b.over ? 0.95 : 0.85,
        }));
        if (b.exercise_kcal > 0) {
          const exH = Math.max(2, (b.exercise_kcal / maxVal) * innerH);
          svg.appendChild(el("rect", {
            x: cx - barW / 2, y: y(b.kcal) - exH, width: barW, height: exH,
            rx: rx, fill: p.warm, opacity: 0.9,
          }));
        }
      } else {
        svg.appendChild(el("rect", {
          x: cx - barW / 2, y: padT + innerH - 4, width: barW, height: 4,
          rx: 2, fill: p.grid,
        }));
      }

      const dayLabel = el("text", {
        x: cx, y: H - 48, "text-anchor": "middle",
        "font-size": 11, "font-weight": 600,
        fill: logged ? p.text : p.muted,
      });
      dayLabel.textContent = b.weekday;
      svg.appendChild(dayLabel);

      if (i % 2 === 0 || i === bars.length - 1) {
        const dateLabel = el("text", {
          x: cx, y: H - 30, "text-anchor": "middle",
          "font-size": 10, fill: p.muted,
        });
        const parts = (b.date_label || "").split(", ");
        dateLabel.textContent = parts.length > 1 ? parts[1] : b.date_label;
        svg.appendChild(dateLabel);
      }

      if (logged) {
        const value = el("text", {
          x: cx, y: y(b.kcal) - (b.exercise_kcal > 0 ? 6 : 0) - 5,
          "text-anchor": "middle", "font-size": 10, "font-weight": 700,
          fill: p.text,
        });
        value.textContent = String(Math.round(b.kcal));
        svg.appendChild(value);
      }
    });

    const ty = y(target);
    svg.appendChild(el("line", {
      x1: padL, y1: ty, x2: W - padR, y2: ty,
      stroke: p.text, "stroke-width": 2, "stroke-dasharray": "7 5", opacity: 0.85,
    }));
    const t = el("text", {
      x: W - padR - 6, y: ty - 8, "text-anchor": "end",
      "font-size": 12, "font-weight": 800, fill: p.text,
    });
    t.textContent = "Target " + Math.round(target) + " kkal";
    svg.appendChild(t);
  }

  // ---- AI insights ---------------------------------------------------------

  async function requestInsights() {
    if (!(await shared.requireAuth())) return;
    if (!state.report) return;
    const btn = $("btnInsights");
    btn.disabled = true;
    btn.textContent = "NumNum lagi mikirin… (±1 menit)";

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

    shared.refreshAuthUI();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
