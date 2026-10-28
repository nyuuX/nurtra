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

  /* ---- Animation helpers ------------------------------------------- */

  const reduceMotion =
    typeof matchMedia !== "undefined" &&
    matchMedia("(prefers-reduced-motion: reduce)").matches;

  /** Animate an SVG node's opacity + optional transform, then resolve.
   * SVG transform-box: fill-box makes `scale`/`translate` relative to the
   * element's own bounding box, which is what makes bar grows look right
   * regardless of where the rect sits in the viewBox. */
  function tween(node, opts) {
    if (reduceMotion) {
      if (opts.onDone) opts.onDone();
      return;
    }
    const duration = opts.duration || 400;
    const delay = opts.delay || 0;
    const from = opts.from != null ? opts.from : 0;
    const to = opts.to != null ? opts.to : 1;
    const attr = opts.attr || "opacity";

    setTimeout(function () {
      const start = performance.now();
      // ease-out cubic — settles with a small overshoot feel
      const step = function (now) {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        const val = from + (to - from) * eased;
        if (attr === "transform") {
          node.setAttribute(
            "transform",
            opts.transform ? opts.transform(val) : ""
          );
        } else {
          node.setAttribute(attr, val.toFixed(3));
        }
        if (t < 1) requestAnimationFrame(step);
        else if (opts.onDone) opts.onDone();
      };
      requestAnimationFrame(step);
    }, delay);
  }

  /* Draw a path by animating its stroke-dashoffset from full length to 0.
   * This is the classic "chart draws itself" effect. getTotalLength is
   * exact for path geometry, so the dash lines up flush at the end. */
  function drawPath(path, duration, delay) {
    if (reduceMotion) return;
    let length = 0;
    try {
      length = path.getTotalLength();
    } catch (e) {
      return; // display:none or zero-length — nothing to animate
    }
    if (!length) return;
    path.style.strokeDasharray = String(length);
    path.style.strokeDashoffset = String(length);
    const start = performance.now();
    setTimeout(function begin() {
      const step = function (now) {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        path.style.strokeDashoffset = String(length * (1 - eased));
        if (t < 1) requestAnimationFrame(step);
        else path.style.strokeDasharray = "none";
      };
      requestAnimationFrame(step);
    }, delay || 0);
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
        const bar = el("rect", {
          x: cx - barW / 2,
          y: y(b.kcal),
          width: barW,
          height: h,
          rx: rx,
          fill: p.emerald,
          opacity: b.over ? 0.95 : 0.85,
        });
        svg.appendChild(bar);

        // Grow from the baseline. SVG transforms need transform-box so the
        // scale origin is the bar's own bottom edge, not the viewBox origin.
        const baseY = padT + innerH;
        bar.style.transformBox = "fill-box";
        bar.style.transformOrigin = "50% 100%";
        tween(bar, {
          attr: "transform",
          duration: 520,
          delay: 120 + i * 70,
          transform: function (v) {
            // scaleY 0 -> 1 while pinning the bottom: translate compensates
            // the vertical shift the scale would otherwise cause.
            return (
              "translate(0 " + (baseY - y(b.kcal)) * (1 - v) + ") scaleY(" + v + ")"
            );
          },
        });

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
          opacity: 0,
        });
        value.textContent = String(Math.round(b.kcal));
        svg.appendChild(value);
        tween(value, { duration: 300, delay: 300 + i * 70 });
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
        opacity: 0,
      });
      dayLabel.textContent = b.weekday;
      svg.appendChild(dayLabel);
      tween(dayLabel, { duration: 260, delay: 150 + i * 70 });
    });

    // ---- Target line (drawn last so it sits above the bars) -------
    const ty = y(target);
    const tline = el("line", {
      x1: padL,
      y1: ty,
      x2: W - padR,
      y2: ty,
      stroke: p.text,
      "stroke-width": 2,
      "stroke-dasharray": "7 5",
      opacity: 0.85,
    });
    svg.appendChild(tline);
    // Lines don't have getTotalLength geometry quirks like paths, so animate
    // opacity + a horizontal sweep instead of a dash draw.
    tween(tline, { duration: 420, delay: 560 });
    const tag = el("text", {
      x: W - padR - 6,
      y: ty - 7,
      "text-anchor": "end",
      "font-size": 11,
      "font-weight": 800,
      fill: p.text,
      opacity: 0,
    });
    tag.textContent = "Target " + Math.round(target) + " kkal";
    svg.appendChild(tag);
    tween(tag, { duration: 300, delay: 760 });
  }

  /* ============================================================
   * Weight trend: smooth Catmull-Rom spline through the points.
   * Weight fluctuates daily from water/glycogen; the smooth curve is
   * the signal, so we never connect the dots with straight lines.
   * ============================================================ */
  function smoothPath(points) {
    if (points.length === 0) return "";
    if (points.length === 1) {
      return "M" + points[0][0].toFixed(1) + "," + points[0][1].toFixed(1);
    }
    if (points.length === 2) {
      return (
        "M" + points[0][0].toFixed(1) + "," + points[0][1].toFixed(1) +
        " L" + points[1][0].toFixed(1) + "," + points[1][1].toFixed(1)
      );
    }
    let d = "M" + points[0][0].toFixed(1) + "," + points[0][1].toFixed(1);
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
      msg.textContent = "Belum ada data berat badan";
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

    if (!linePath) {
      const single = el("circle", {
        cx: points[0][0],
        cy: points[0][1],
        r: 5,
        fill: p.emerald,
        stroke: cssVar("--surface") || "#fff",
        "stroke-width": 2,
      });
      svg.appendChild(single);
      drawPath(single, 600, 250);
      return;
    }

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

    const line = el("path", {
      d: linePath,
      fill: "none",
      stroke: p.emerald,
      "stroke-width": 3,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
    });
    svg.appendChild(line);

    // The curve draws itself: dashoffset animates full -> 0. The area fill
    // follows the same timeline so it doesn't appear ahead of the stroke.
    drawPath(line, 1400, 250);

    // ---- Dots + labels ---------------------------------------------
    weights.forEach(function (w, i) {
      const dot = el("circle", {
        cx: x(i),
        cy: y(w.weight_kg),
        r: 4,
        fill: p.emerald,
        stroke: cssVar("--surface") || "#fff",
        "stroke-width": 2,
        opacity: 0,
      });
      svg.appendChild(dot);
      // Stagger so each dot pops in right as the curve reaches it.
      tween(dot, { duration: 280, delay: 250 + (i / Math.max(1, weights.length - 1)) * 1400 });

      const label = el("text", {
        x: x(i),
        y: y(w.weight_kg) - 10,
        "text-anchor": "middle",
        "font-size": 10.5,
        "font-weight": 700,
        fill: p.text,
        opacity: 0,
      });
      label.textContent = w.weight_kg.toFixed(1);
      svg.appendChild(label);
      tween(label, { duration: 260, delay: 350 + (i / Math.max(1, weights.length - 1)) * 1400 });

      const day = el("text", {
        x: x(i),
        y: H - 10,
        "text-anchor": "middle",
        "font-size": 11,
        fill: p.muted,
        opacity: 0,
      });
      const parts = (w.date || "").split("-");
      if (weights.length > 10) {
        if (i % 3 === 0 || i === weights.length - 1) {
          day.textContent = parts.length === 3 ? parts[2] + "/" + parts[1] : w.date;
        } else {
          day.textContent = "";
        }
      } else {
        day.textContent = parts.length === 3 ? parts[2] : w.date;
      }
      svg.appendChild(day);
      tween(day, { duration: 250, delay: 200 + i * 110 });
    });
  }

  global.NurtraCharts = {
    renderBars: renderBars,
    renderWeight: renderWeight,
  };
})(window);
