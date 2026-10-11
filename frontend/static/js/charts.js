/* Nurtra — SVG charts: 7-day intake vs target, and a smooth weight
 * spline (Catmull-Rom -> cubic beziers so the curve is C1 smooth).
 * Hand-rolled SVG, no chart library, so the app stays dependency-free.
 */
(function (global) {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";

  function el(name, attrs) {
    const node = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    return node;
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
  }

  /** Read the theme-aware palette, with a fallback if CSS vars are empty. */
  function palette() {
    const text = cssVar("--text") || "#0f172a";
    const muted = cssVar("--text-muted") || "#6b7280";
    const grid = cssVar("--border") || "#e5e7eb";
    return {
      emerald: cssVar("--emerald") || "#10b981",
      warm: cssVar("--warm") || "#f59e0b",
      text: text,
      muted: muted,
      grid: grid,
      surface: cssVar("--surface-2") || "#f3f4f6",
    };
  }

  /* ============================================================
   * 7-day bar chart: intake bars + exercise overlay + target line
   * ============================================================ */
  function renderBars(svg, bars, target) {
    const W = 640;
    const H = 260;
    const padL = 44;
    const padR = 12;
    const padT = 16;
    const padB = 34;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const p = palette();
    const maxVal = Math.max(target * 1.25, 500);
    const y = function (v) {
      return padT + innerH - (Math.min(v, maxVal) / maxVal) * innerH;
    };

    // ---- Gridlines + y labels (0, target, max) --------------------
    [0, 0.5, 1].forEach(function (frac) {
      const gy = padT + innerH - frac * innerH;
      svg.appendChild(
        el("line", {
          x1: padL,
          y1: gy,
          x2: W - padR,
          y2: gy,
          stroke: p.grid,
          "stroke-width": 1,
          "stroke-dasharray": frac === 1 ? "" : "3 5",
        })
      );
      const label = el("text", {
        x: padL - 8,
        y: gy + 4,
        "text-anchor": "end",
        "font-size": 11,
        fill: p.muted,
      });
      label.textContent = Math.round(frac * maxVal);
      svg.appendChild(label);
    });

    // ---- Bars ------------------------------------------------------
    const slot = innerW / bars.length;
    const barW = Math.min(38, slot * 0.44);

    bars.forEach(function (b, i) {
      const cx = padL + slot * i + slot / 2;
      const logged = b.logged && b.kcal > 0;
      const h = logged ? Math.max(2, padT + innerH - y(b.kcal)) : 0;
      const rx = 5;

      if (logged) {
        svg.appendChild(
          el("rect", {
            x: cx - barW / 2,
            y: y(b.kcal),
            width: barW,
            height: h,
            rx: rx,
            fill: p.emerald,
            opacity: b.over ? 0.95 : 0.85,
          })
        );
        // exercise overlay stripe (warm) on top of the intake bar
        if (b.exercise_kcal > 0) {
          const exH = Math.max(
            2,
            (b.exercise_kcal / maxVal) * innerH
          );
          svg.appendChild(
            el("rect", {
              x: cx - barW / 2,
              y: y(b.kcal) - exH,
              width: barW,
              height: exH,
              rx: rx,
              fill: p.warm,
              opacity: 0.9,
            })
          );
        }
        const value = el("text", {
          x: cx,
          y: y(b.kcal) - (b.exercise_kcal > 0 ? 8 : 0) - 6,
          "text-anchor": "middle",
          "font-size": 11,
          "font-weight": 700,
          fill: p.text,
        });
        value.textContent = String(Math.round(b.kcal));
        svg.appendChild(value);
      } else {
        // unlogged day: faint placeholder so the week reads complete
        svg.appendChild(
          el("rect", {
            x: cx - barW / 2,
            y: padT + innerH - 6,
            width: barW,
            height: 6,
            rx: 3,
            fill: p.grid,
          })
        );
      }

      const dayLabel = el("text", {
        x: cx,
        y: H - 12,
        "text-anchor": "middle",
        "font-size": 12,
        "font-weight": 600,
        fill: logged ? p.text : p.muted,
      });
      dayLabel.textContent = b.weekday;
      svg.appendChild(dayLabel);
    });

    // ---- Target line (drawn last so it sits above the bars) -------
    const ty = y(target);
    svg.appendChild(
      el("line", {
        x1: padL,
        y1: ty,
        x2: W - padR,
        y2: ty,
        stroke: p.text,
        "stroke-width": 2,
        "stroke-dasharray": "7 5",
        opacity: 0.85,
      })
    );
    const tag = el("text", {
      x: W - padR - 6,
      y: ty - 7,
      "text-anchor": "end",
      "font-size": 11,
      "font-weight": 800,
      fill: p.text,
    });
    tag.textContent = "Target " + Math.round(target) + " kkal";
    svg.appendChild(tag);
  }

  /* ============================================================
   * Weight trend: smooth Catmull-Rom spline through the points.
   * Weight fluctuates daily from water/glycogen; the smooth curve is
   * the signal, so we never connect the dots with straight lines.
   * ============================================================ */
  function smoothPath(points) {
    if (points.length < 2) return "";
    if (points.length === 2) {
      return "M" + points[0][0] + "," + points[0][1] + " L" + points[1][0] + "," + points[1][1];
    }
    let d = "M" + points[0][0] + "," + points[0][1];
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[Math.max(0, i - 1)];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[Math.min(points.length - 1, i + 2)];
      const c1x = p1[0] + (p2[0] - p0[0]) / 6;
      const c1y = p1[1] + (p2[1] - p0[1]) / 6;
      const c2x = p2[0] - (p3[0] - p1[0]) / 6;
      const c2y = p2[1] - (p3[1] - p1[1]) / 6;
      d +=
        " C" +
        c1x.toFixed(1) + "," + c1y.toFixed(1) +
        " " + c2x.toFixed(1) + "," + c2y.toFixed(1) +
        " " + p2[0].toFixed(1) + "," + p2[1].toFixed(1);
    }
    return d;
  }

  function renderWeight(svg, weights) {
    const W = 640;
    const H = 240;
    const padL = 44;
    const padR = 14;
    const padT = 18;
    const padB = 30;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const p = palette();

    if (!weights.length) {
      const msg = el("text", {
        x: W / 2,
        y: H / 2,
        "text-anchor": "middle",
        "font-size": 13,
        fill: p.muted,
      });
      msg.textContent = "Belum ada data berat badan minggu ini";
      svg.appendChild(msg);
      return;
    }

    const values = weights.map(function (w) { return w.weight_kg; });
    const lo = Math.min.apply(null, values);
    const hi = Math.max.apply(null, values);
    const span = Math.max(0.5, hi - lo);
    const pad = span * 0.25;
    const yMin = lo - pad;
    const yMax = hi + pad;

    const x = function (i) {
      return padL + (weights.length === 1 ? innerW / 2 : (i / (weights.length - 1)) * innerW);
    };
    const y = function (v) {
      return padT + innerH - ((v - yMin) / (yMax - yMin)) * innerH;
    };

    // ---- Gridlines --------------------------------------------------
    [0, 0.5, 1].forEach(function (frac) {
      const gy = padT + innerH - frac * innerH;
      svg.appendChild(
        el("line", {
          x1: padL,
          y1: gy,
          x2: W - padR,
          y2: gy,
          stroke: p.grid,
          "stroke-width": 1,
          "stroke-dasharray": "3 5",
        })
      );
      const label = el("text", {
        x: padL - 8,
        y: gy + 4,
        "text-anchor": "end",
        "font-size": 11,
        fill: p.muted,
      });
      label.textContent = (yMin + frac * (yMax - yMin)).toFixed(1);
      svg.appendChild(label);
    });

    // ---- Smooth spline + area fill ---------------------------------
    const points = weights.map(function (w, i) { return [x(i), y(w.weight_kg)]; });
    const linePath = smoothPath(points);

    // Area under the curve, filled with a soft emerald tint
    const areaPath =
      linePath +
      " L" + points[points.length - 1][0] + "," + (padT + innerH) +
      " L" + points[0][0] + "," + (padT + innerH) +
      " Z";
    const defs = el("defs", {});
    const grad = el("linearGradient", {
      id: "weightFill",
      x1: "0",
      y1: "0",
      x2: "0",
      y2: "1",
    });
    grad.appendChild(
      el("stop", { offset: "0%", "stop-color": p.emerald, "stop-opacity": "0.28" })
    );
    grad.appendChild(
      el("stop", { offset: "100%", "stop-color": p.emerald, "stop-opacity": "0.02" })
    );
    defs.appendChild(grad);
    svg.appendChild(defs);

    svg.appendChild(
      el("path", { d: areaPath, fill: "url(#weightFill)", stroke: "none" })
    );
    svg.appendChild(
      el("path", {
        d: linePath,
        fill: "none",
        stroke: p.emerald,
        "stroke-width": 3,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
      })
    );

    // ---- Dots + labels ---------------------------------------------
    weights.forEach(function (w, i) {
      svg.appendChild(
        el("circle", {
          cx: x(i),
          cy: y(w.weight_kg),
          r: 4,
          fill: p.emerald,
          stroke: cssVar("--surface") || "#fff",
          "stroke-width": 2,
        })
      );
      const label = el("text", {
        x: x(i),
        y: y(w.weight_kg) - 10,
        "text-anchor": "middle",
        "font-size": 10.5,
        "font-weight": 700,
        fill: p.text,
      });
      label.textContent = w.weight_kg.toFixed(1);
      svg.appendChild(label);

      const day = el("text", {
        x: x(i),
        y: H - 10,
        "text-anchor": "middle",
        "font-size": "11",
        fill: p.muted,
      });
      const parts = (w.date || "").split("-");
      day.textContent = parts.length === 3 ? parts[2] : w.date;
      svg.appendChild(day);
    });
  }

  global.NurtraCharts = {
    renderBars: renderBars,
    renderWeight: renderWeight,
  };
})(window);
