/* Nurtra — shared helpers + dashboard logic (index.html).

Exposes window.NurtraShared (fmt, fmtDate, escapeHtml, toast, applyTheme)
so the profile and report pages reuse them without duplicating code.
*/
(function (global) {
  "use strict";

  const api = window.NurtraAPI;
  const $ = function (id) {
    return document.getElementById(id);
  };

  const MEALS = [
    { key: "breakfast", label: "Sarapan", emoji: "" },
    { key: "lunch", label: "Makan Siang", emoji: "" },
    { key: "dinner", label: "Makan Malam", emoji: "" },
    { key: "snack", label: "Ngemil", emoji: "" },
  ];

  const state = {
    today: null,
    profile: null,
    recent: [],
    favorites: [],
    exercises: [],
    lastSearch: [],
    pendingFood: null,
    pendingMeal: "lunch",
    pendingExercise: null,
  };

  // ---- Shared helpers (used by profile.js / report.js too) ----------------

  function fmt(n) {
    return Math.round(n || 0).toLocaleString("id-ID");
  }

  function fmtDate(iso) {
    if (!iso) return "";
    const months = [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "Mei",
      "Jun",
      "Jul",
      "Agu",
      "Sep",
      "Okt",
      "Nov",
      "Des",
    ];
    const d = new Date(iso + "T12:00:00");
    if (isNaN(d.getTime())) return iso;
    return d.getDate() + " " + months[d.getMonth()] + " " + d.getFullYear();
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function toast(msg) {
    const t = $("toast");
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(function () {
      t.hidden = true;
    }, 2600);
  }

  // ---- Theme ---------------------------------------------------------------

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    // The account menu reflects the current mode; the toggle flips between
    // Mode Gelap / Mode Terang.
    const label = $("miThemeLabel");
    const icon = $("miThemeIcon");
    if (label)
      label.textContent = theme === "dark" ? "Mode Terang" : "Mode Gelap";
    if (icon) icon.textContent = theme === "dark" ? "☀️" : "🌙";
    // The report page registers here so its SVG charts re-render on theme switch
    if (global.NurtraReport && global.NurtraReport.onThemeChange) {
      global.NurtraReport.onThemeChange();
    }
  }

  function initTheme() {
    let theme = "light";
    try {
      theme = localStorage.getItem("dk-theme") || "light";
    } catch (e) {}
    applyTheme(theme);
  }

  function bindThemeButton() {
    const btn = $("miTheme");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const next =
        document.documentElement.getAttribute("data-theme") === "dark"
          ? "light"
          : "dark";
      try {
        localStorage.setItem("dk-theme", next);
      } catch (e) {}
      applyTheme(next);
    });
  }

  // ---- Account dropdown ------------------------------------------------------

  // One button opens a menu with the greeting, theme toggle, login and logout.
  // Closing happens on outside click / Escape / focus loss.
  function bindAccountMenu() {
    const wrap = document.querySelector(".acct-wrap");
    const btn = $("btnAcct");
    const menu = $("acctMenu");
    if (!wrap || !btn || !menu) return;

    function setOpen(open) {
      menu.hidden = !open;
      wrap.classList.toggle("open", open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      setOpen(menu.hidden);
    });

    // Click anywhere else closes it.
    document.addEventListener("click", function (e) {
      if (!menu.hidden && !wrap.contains(e.target)) setOpen(false);
    });

    // Escape closes and returns focus to the trigger.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !menu.hidden) {
        setOpen(false);
        btn.focus();
      }
    });

    const out = $("miLogout");
    if (out) out.addEventListener("click", logout);
  }

  // ---- Dashboard -----------------------------------------------------------

  async function loadToday() {
    // Only the dashboard renders this data; on profile/report pages
    // app.js is loaded just for the shared theme + account menu, so skip
    // the request entirely rather than render into missing elements.
    if (!document.getElementById("ringProgress")) return;

    // Anonymous visitors get the demo numbers but no write access: show the
    // login banner so the limit is visible, not just a toast on first write.
    const banner = document.getElementById("authBanner");
    let isAnon = false;
    try {
      const res = await fetch("/api/auth/me", { credentials: "include" });
      const data = await res.json();
      isAnon = !(data && data.user);
    } catch (err) {
      isAnon = true;
    }
    if (banner) banner.hidden = !isAnon;

    try {
      const data = await api.getToday();
      state.today = data;
      renderDashboard(data);
    } catch (err) {
      toast(err.message);
    }
  }

  function renderDashboard(d) {
    $("dateLabel").textContent = fmtDateLong(d.date);

    // Hero ring: ring arc tracks consumed/target, the number shows remaining
    const remaining = d.remaining_kcal;
    const ring = $("ringProgress");
    const C = 2 * Math.PI * 100;
    const consumed = Math.max(0, d.target_kcal - remaining);
    const pct = Math.min(1, consumed / Math.max(1, d.target_kcal));
    ring.setAttribute("stroke-dasharray", C.toFixed(1));
    ring.setAttribute("stroke-dashoffset", (C * (1 - pct)).toFixed(1));
    ring.classList.toggle("over", d.over);
    $("remainingKcal").textContent = fmt(remaining);
    $("ringCaption").textContent = d.over
      ? "kkal — melebihi target!"
      : "kkal tersisa";
    $("heroCard").classList.toggle("over", d.over);

    // Breakdown: Target - Makanan + Olahraga
    $("bdTarget").textContent = fmt(d.target_kcal);
    $("bdFood").textContent = fmt(d.food_kcal);
    $("bdExercise").textContent = fmt(d.exercise_kcal);

    // Fasting chip
    if (d.fasting && d.fasting.enabled) {
      $("fastingChip").hidden = false;
      $("fastingText").textContent = d.fasting.eating_now
        ? "Jendela makan " +
          d.fasting.protocol +
          " · " +
          d.fasting.window_start +
          "–" +
          d.fasting.window_end +
          " · Makan sekarang"
        : "Puasa " +
          d.fasting.protocol +
          " · makan " +
          d.fasting.window_start +
          "–" +
          d.fasting.window_end;
      $("fastingDot").classList.toggle("fasting", !d.fasting.eating_now);
    } else {
      $("fastingChip").hidden = true;
    }

    // Macros (protein emphasized)
    const order = ["protein", "carb", "fat"];
    const names = { protein: "Protein", carb: "Karbohidrat", fat: "Lemak" };
    $("macroList").innerHTML = order
      .map(function (k) {
        const m = d.macros[k];
        const fill = Math.min(100, m.pct);
        return (
          '<div class="macro-row">' +
          '<div class="macro-name">' +
          names[k] +
          (k === "protein" ? "<small>prioritas utama</small>" : "") +
          "</div>" +
          '<div class="macro-bar"><div class="macro-fill ' +
          k +
          '" style="width:' +
          fill +
          '%"></div></div>' +
          '<div class="macro-val">' +
          m.eaten_g +
          "g <small>/ " +
          Math.round(m.target_g) +
          "g</small></div>" +
          "</div>"
        );
      })
      .join("");
    const prot = d.macros.protein;
    $("macroSub").textContent =
      "Protein " + prot.eaten_g + "g dari " + Math.round(prot.target_g) + "g";

    // Meal sections
    $("mealSections").innerHTML = MEALS.map(function (meal) {
      const found = (d.meals || []).find(function (m) {
        return m.key === meal.key;
      });
      const items = found ? found.items : [];
      const itemsHtml = items.length
        ? items.map(renderMealItem).join("")
        : '<div class="empty-meal">Belum ada log</div>';

      return (
        '<div class="meal-section">' +
        '<div class="meal-head">' +
        "<h3>" +
        meal.emoji +
        " " +
        meal.label +
        "</h3>" +
        '<div class="meal-kcal">' +
        fmt(found ? found.kcal : 0) +
        " kkal</div>" +
        "</div>" +
        '<div class="meal-items">' +
        itemsHtml +
        "</div>" +
        '<button class="add-btn" data-add-meal="' +
        meal.key +
        '" title="Tambah ' +
        meal.label +
        '">+</button>' +
        "</div>"
      );
    }).join("");

    // Exercises
    const exs = d.exercises || [];
    $("exerciseList").innerHTML = exs.length
      ? exs.map(renderExerciseItem).join("")
      : '<div class="empty-meal">Belum ada olahraga hari ini</div>';
  }

  function renderMealItem(it) {
    return (
      '<div class="meal-item">' +
      '<div class="mi-name">' +
      escapeHtml(it.name) +
      (it.volume_eating ? ' <span class="tag-vol">VOLUME</span>' : "") +
      "</div>" +
      '<div class="mi-meta">' +
      "<span>" +
      Math.round(it.kcal) +
      " kkal</span>" +
      "<span>" +
      (it.protein_g || 0) +
      "p</span>" +
      '<button class="icon-btn" data-del-meal="' +
      it.meal +
      '" data-del-id="' +
      it.id +
      '" title="Hapus">✕</button>' +
      "</div>" +
      "</div>"
    );
  }

  function renderExerciseItem(e) {
    // Older seeded rows may lack an id; fall back to a name-based key so the
    // delete button still resolves (the backend matches id OR name).
    const delKey = e.id || e.name;
    return (
      '<div class="exercise-item">' +
      "<div>" +
      escapeHtml(e.name) +
      ' <span style="color:var(--text-muted);font-size:0.75rem">' +
      (e.duration_min || 30) +
      " menit</span>" +
      "</div>" +
      '<div class="ex-kcal">−' +
      Math.round(e.kcal) +
      ' kkal <button class="icon-btn" data-del-ex="' +
      escapeHtml(delKey) +
      '">✕</button></div>' +
      "</div>"
    );
  }

  function fmtDateLong(iso) {
    if (!iso) return "";
    const days = [
      "Minggu",
      "Senin",
      "Selasa",
      "Rabu",
      "Kamis",
      "Jumat",
      "Sabtu",
    ];
    const d = new Date(iso + "T12:00:00");
    if (isNaN(d.getTime())) return fmtDate(iso);
    return days[d.getDay()] + ", " + fmtDate(iso);
  }

  // ---- Sheets ---------------------------------------------------------------

  function openSheet(id) {
    $(id).hidden = false;
    $("sheetBackdrop").hidden = false;
  }

  function closeSheets() {
    ["foodSheet", "exerciseSheet", "quickSheet", "weightSheet"].forEach(
      function (id) {
        const el = $(id);
        if (el) el.hidden = true;
      },
    );
    $("sheetBackdrop").hidden = true;
  }

  // ---- Food sheet -----------------------------------------------------------

  async function openFoodSheet(mealKey) {
    state.pendingMeal = mealKey;
    state.pendingFood = null;
    $("sheetTitle").textContent = "Tambah " + mealLabel(mealKey);
    $("foodSearch").value = "";
    $("searchResults").innerHTML = "";
    $("portionBox").hidden = true;
    $("aiParseBox").hidden = true;
    $("aiParseResult").innerHTML = "";
    $("aiParseText").value = "";
    await loadChips();
    openSheet("foodSheet");
    setTimeout(function () {
      $("foodSearch").focus();
    }, 200);
  }

  function mealLabel(key) {
    const m = MEALS.find(function (x) {
      return x.key === key;
    });
    return m ? m.label : key;
  }

  async function loadChips() {
    let favorites = [];
    try {
      const favs = await api.getFavorites();
      favorites = favs.favorites || [];
      state.favorites = favorites;
    } catch (e) {}
    const recents = state.recent || [];

    const parts = [];
    favorites.slice(0, 4).forEach(function (f) {
      parts.push(
        '<button class="chip" data-fav="' +
          f.id +
          '"><span class="chip-star">★</span>' +
          escapeHtml(f.name) +
          "</button>",
      );
    });
    recents.slice(0, 5).forEach(function (r) {
      parts.push(
        '<button class="chip" data-recent="' +
          escapeHtml(r) +
          '">' +
          escapeHtml(r) +
          "</button>",
      );
    });
    parts.push(
      '<button class="chip" data-volume="1">🥬 Volume eating</button>',
    );
    $("recentChips").innerHTML = parts.join("");
  }

  let searchTimer = null;
  function scheduleSearch(q) {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () {
      runSearch(q);
    }, 220);
  }

  async function runSearch(q) {
    if (!q.trim()) {
      $("searchResults").innerHTML = "";
      state.lastSearch = [];
      return;
    }
    try {
      const res = await api.searchFoods(q);
      state.lastSearch = res.foods || [];
      state.recent = [q.trim()]
        .concat(
          (state.recent || []).filter(function (r) {
            return r !== q.trim();
          }),
        )
        .slice(0, 6);
      renderFoodResults(state.lastSearch);
    } catch (err) {
      $("searchResults").innerHTML =
        '<div class="empty-meal">Pencarian gagal: ' +
        escapeHtml(err.message) +
        "</div>";
    }
  }

  function renderFoodResults(foods) {
    if (!foods.length) {
      $("searchResults").innerHTML =
        '<div class="empty-meal">Tidak ditemukan. Coba teks bebas dengan AI ✨ atau Quick Add manual.</div>';
      return;
    }
    $("searchResults").innerHTML = foods
      .map(function (f) {
        return (
          '<button class="food-row" data-food-id="' +
          escapeHtml(f.id) +
          '">' +
          "<div>" +
          '<div class="fr-name">' +
          escapeHtml(f.name) +
          (f.volume_eating ? ' <span class="tag-vol">VOLUME</span>' : "") +
          "</div>" +
          '<div class="fr-sub">' +
          f.protein_g +
          "g protein · " +
          f.portion_g +
          " g porsi</div>" +
          "</div>" +
          '<div class="fr-kcal">' +
          Math.round(f.kcal) +
          " kkal</div>" +
          "</button>"
        );
      })
      .join("");
  }

  function pickFood(food) {
    state.pendingFood = food;
    $("portionName").textContent = food.name;
    $("portionPer").textContent =
      food.portion_g + " g per porsi · " + food.protein_g + " g protein";
    $("portionPresets").innerHTML = [0.5, 1, 1.5, 2]
      .map(function (v) {
        return (
          '<button class="preset" data-preset="' + v + '">' + v + "x</button>"
        );
      })
      .join("");
    $("portionBox").hidden = false;
    $("portionRange").value = 1;
    setPortion();
  }

  function setPortion() {
    const v = parseFloat($("portionRange").value) || 1;
    const f = state.pendingFood;
    $("rangeVal").textContent = v + "x";
    $("portionKcal").textContent = Math.round(f.kcal * v) + " kkal";
    document.querySelectorAll(".preset").forEach(function (b) {
      b.classList.toggle("active", parseFloat(b.dataset.preset) === v);
    });
  }

  async function confirmAddFood() {
    const v = parseFloat($("portionRange").value) || 1;
    const f = state.pendingFood;
    if (!f) return;
    try {
      const updated = await api.addMeal(state.pendingMeal, {
        name: f.name,
        kcal: f.kcal * v,
        protein_g: (f.protein_g || 0) * v,
        carb_g: (f.carb_g || 0) * v,
        fat_g: (f.fat_g || 0) * v,
        portion_g: Math.round((f.portion_g || 100) * v),
        servings: v,
        volume_eating: !!f.volume_eating,
      });
      closeSheets();
      renderDashboard(updated);
      toast(f.name + " ditambahkan (" + v + "x)");
    } catch (err) {
      toast(err.message);
    }
  }

  // ---- AI parse --------------------------------------------------------------

  async function runAIParse() {
    const text = $("aiParseText").value.trim();
    if (!text) {
      toast("Tulis dulu makanannya");
      return;
    }
    $("aiParseResult").innerHTML =
      '<span style="opacity:.7">Memproses dengan Atria Dawn…</span>';
    try {
      const res = await api.parseFoods(text);
      const foods = res.foods || [];
      if (!foods.length) {
        $("aiParseResult").innerHTML =
          "Tidak dikenali. Coba: <em>'nasi putih, dada ayam 150 gram'</em>";
        return;
      }
      $("aiParseResult").innerHTML =
        '<div style="margin-bottom:6px"><strong>' +
        foods.length +
        " makanan dikenali</strong> · " +
        (res.source === "atria" ? "Atria Dawn" : "database lokal") +
        " · confidence " +
        Math.round((res.confidence || 0) * 100) +
        "%</div>" +
        foods
          .map(function (f, i) {
            return (
              '<button class="food-row" data-ai-food="' +
              i +
              '">' +
              '<div><div class="fr-name">' +
              escapeHtml(f.name) +
              "</div>" +
              '<div class="fr-sub">' +
              Math.round(f.kcal) +
              " kkal · " +
              (f.protein_g || 0) +
              " g protein</div></div>" +
              '<div class="fr-kcal">+</div></button>'
            );
          })
          .join("");
      $("aiParseResult").dataset.foods = JSON.stringify(foods);
    } catch (err) {
      $("aiParseResult").innerHTML = "Gagal: " + escapeHtml(err.message);
    }
  }

  // ---- Exercise sheet --------------------------------------------------------

  async function openExerciseSheet() {
    $("exerciseForm").hidden = true;
    $("exercisePicker").innerHTML = '<div class="empty-meal">Memuat…</div>';
    openSheet("exerciseSheet");
    try {
      const res = await api.listExercises();
      state.exercises = res.exercises || [];
      $("exercisePicker").innerHTML = state.exercises
        .map(function (e) {
          return (
            '<button class="food-row" data-ex-id="' +
            escapeHtml(e.id) +
            '">' +
            '<div><div class="fr-name">' +
            escapeHtml(e.name) +
            "</div>" +
            '<div class="fr-sub">' +
            e.kcal_per_30min +
            " kkal / 30 menit</div></div>" +
            '<div class="fr-kcal">~' +
            e.kcal_per_30min +
            "</div></button>"
          );
        })
        .join("");
    } catch (err) {
      $("exercisePicker").innerHTML =
        '<div class="empty-meal">Gagal: ' + escapeHtml(err.message) + "</div>";
    }
  }

  function pickExercise(id) {
    const ex = state.exercises.find(function (e) {
      return e.id === id;
    });
    if (!ex) return;
    state.pendingExercise = ex;
    $("exName").textContent = ex.name;
    $("exMeta").textContent = "MET " + ex.met + " · estimasi untuk 70 kg";
    $("exDuration").value = 30;
    updateExKcal();
    $("exerciseForm").hidden = false;
  }

  function updateExKcal() {
    const ex = state.pendingExercise;
    if (!ex) return;
    const mins = parseFloat($("exDuration").value) || 30;
    $("exKcalPreview").textContent =
      "≈ " + Math.round((ex.kcal_per_30min / 30) * mins) + " kkal terbakar";
  }

  async function confirmAddExercise() {
    const ex = state.pendingExercise;
    const mins = parseFloat($("exDuration").value) || 30;
    const kcal = (ex.kcal_per_30min / 30) * mins;
    try {
      const updated = await api.addExercise({
        name: ex.name,
        kcal: kcal,
        duration_min: mins,
      });
      closeSheets();
      renderDashboard(updated);
      toast(ex.name + " · " + Math.round(kcal) + " kkal terbakar");
    } catch (err) {
      toast(err.message);
    }
  }

  // ---- Quick add / weight -----------------------------------------------------

  async function submitQuick(form) {
    const fd = new FormData(form);
    const entry = {
      name: (fd.get("name") || "").toString(),
      kcal: parseFloat(fd.get("kcal")),
      protein_g: parseFloat(fd.get("protein_g") || 0),
      carb_g: parseFloat(fd.get("carb_g") || 0),
      fat_g: parseFloat(fd.get("fat_g") || 0),
    };
    try {
      const updated = await api.addMeal(fd.get("meal").toString(), entry);
      closeSheets();
      renderDashboard(updated);
      toast(entry.name + " ditambahkan");
      form.reset();
    } catch (err) {
      toast(err.message);
    }
  }

  async function submitWeight(form) {
    const fd = new FormData(form);
    const w = parseFloat(fd.get("weight_kg"));
    try {
      await api.logWeight(w);
      closeSheets();
      await loadToday();
      toast("Berat " + w + " kg dicatat");
      form.reset();
    } catch (err) {
      toast(err.message);
    }
  }

  // ---- Deletes ----------------------------------------------------------------

  async function deleteMealEntry(meal, entryId) {
    try {
      const updated = await api.deleteMeal(meal, entryId);
      renderDashboard(updated);
      toast("Dihapus");
    } catch (err) {
      toast(err.message);
    }
  }

  async function deleteExerciseEntry(entryId) {
    try {
      const updated = await api.deleteExercise(entryId);
      renderDashboard(updated);
      toast("Dihapus");
    } catch (err) {
      toast(err.message);
    }
  }

  async function addFavoriteDirect(favId) {
    const fav = state.favorites.find(function (f) {
      return f.id === favId;
    });
    if (!fav) return;
    try {
      const updated = await api.addMeal(state.pendingMeal, {
        name: fav.name,
        kcal: fav.kcal,
        protein_g: fav.protein_g || 0,
        carb_g: fav.carb_g || 0,
        fat_g: fav.fat_g || 0,
        portion_g: 100,
        servings: 1,
      });
      closeSheets();
      renderDashboard(updated);
      toast(fav.name + " ditambahkan");
    } catch (err) {
      toast(err.message);
    }
  }

  async function showVolumeFoods() {
    try {
      const res = await api.volumeFoods();
      renderFoodResults(res.foods || []);
    } catch (err) {
      toast(err.message);
    }
  }

  function findFoodById(id) {
    return state.lastSearch
      ? state.lastSearch.find(function (f) {
          return f.id === id;
        }) || null
      : null;
  }

  // ---- Events -----------------------------------------------------------------

  function bindEvents() {
    bindThemeButton();

    // app.js is shared by index, profile and report pages, but these elements
    // only exist on the dashboard. Guard the whole block so a missing element
    // doesn't throw and skip the account menu binding.
    if (!document.getElementById("btnQuickAdd")) return;

    $("btnLogWeight").addEventListener("click", function () {
      openSheet("weightSheet");
    });
    $("btnQuickAdd").addEventListener("click", function () {
      openSheet("quickSheet");
    });
    $("btnAddExercise").addEventListener("click", openExerciseSheet);
    $("btnCloseSheet").addEventListener("click", closeSheets);
    $("btnCloseExSheet").addEventListener("click", closeSheets);
    $("btnCloseQuickSheet").addEventListener("click", closeSheets);
    $("btnCloseWeightSheet").addEventListener("click", closeSheets);
    $("sheetBackdrop").addEventListener("click", closeSheets);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeSheets();
    });

    // Meal + exercise rows (event delegation)
    $("mealSections").addEventListener("click", function (e) {
      const addBtn = e.target.closest("[data-add-meal]");
      if (addBtn) {
        openFoodSheet(addBtn.dataset.addMeal);
        return;
      }
      const del = e.target.closest("[data-del-meal]");
      if (del) {
        deleteMealEntry(del.dataset.delMeal, del.dataset.delId);
      }
    });
    $("exerciseList").addEventListener("click", function (e) {
      const del = e.target.closest("[data-del-ex]");
      if (del) deleteExerciseEntry(del.dataset.delEx);
    });

    // Food sheet
    $("foodSearch").addEventListener("input", function (e) {
      scheduleSearch(e.target.value);
    });
    $("searchResults").addEventListener("click", function (e) {
      const row = e.target.closest("[data-food-id]");
      if (!row) return;
      const food = findFoodById(row.dataset.foodId);
      if (food) pickFood(food);
    });
    $("recentChips").addEventListener("click", function (e) {
      const chip = e.target.closest("button");
      if (!chip) return;
      if (chip.dataset.volume) {
        showVolumeFoods();
        return;
      }
      if (chip.dataset.recent) {
        $("foodSearch").value = chip.dataset.recent;
        runSearch(chip.dataset.recent);
        return;
      }
      if (chip.dataset.fav) addFavoriteDirect(chip.dataset.fav);
    });
    $("portionRange").addEventListener("input", setPortion);
    $("portionPresets").addEventListener("click", function (e) {
      const b = e.target.closest(".preset");
      if (!b) return;
      $("portionRange").value = b.dataset.preset;
      setPortion();
    });
    $("btnConfirmAdd").addEventListener("click", confirmAddFood);

    $("btnAIParse").addEventListener("click", function () {
      const box = $("aiParseBox");
      box.hidden = !box.hidden;
      if (!box.hidden) $("aiParseText").focus();
    });
    $("btnAIParseGo").addEventListener("click", runAIParse);
    $("aiParseResult").addEventListener("click", function (e) {
      const row = e.target.closest("[data-ai-food]");
      if (!row) return;
      const foods = JSON.parse($("aiParseResult").dataset.foods || "[]");
      const f = foods[parseInt(row.dataset.aiFood, 10)];
      if (f) {
        pickFood({
          id: "ai-" + Date.now(),
          name: f.name,
          kcal: f.kcal,
          protein_g: f.protein_g || 0,
          carb_g: f.carb_g || 0,
          fat_g: f.fat_g || 0,
          portion_g: f.portion_g || 100,
          volume_eating: !!f.volume_eating,
        });
      }
    });

    // Exercise sheet
    $("exercisePicker").addEventListener("click", function (e) {
      const row = e.target.closest("[data-ex-id]");
      if (row) pickExercise(row.dataset.exId);
    });
    $("exDuration").addEventListener("input", updateExKcal);
    $("btnConfirmExercise").addEventListener("click", confirmAddExercise);

    // Forms
    $("quickForm").addEventListener("submit", function (e) {
      e.preventDefault();
      submitQuick(e.target);
    });
    $("weightForm").addEventListener("submit", function (e) {
      e.preventDefault();
      submitWeight(e.target);
    });
  }

  // ---- Init ---------------------------------------------------------------------

  async function init() {
    initTheme();
    bindEvents();
    bindAccountMenu();
    await loadToday();
    refreshAuthUI();
  }

  // ---- Auth UI ------------------------------------------------------------------

  // Keeps the account dropdown in sync across every page.
  // Anonymous users keep full access to the demo data, so a missing session
  // is never an error — the menu just shows the login entry instead of logout.
  async function refreshAuthUI() {
    const btn = document.getElementById("btnAcct");
    const greeting = document.getElementById("acctGreeting");
    const miLogin = document.getElementById("miLogin");
    const miSignup = document.getElementById("miSignup");
    const miLogout = document.getElementById("miLogout");
    if (!btn) return;

    try {
      const res = await fetch("/api/auth/me", { credentials: "include" });
      const data = await res.json();
      if (data && data.user) {
        btn.classList.add("signed-in");
        if (greeting) {
          const name = data.user.name || data.user.email.split("@")[0];
          greeting.innerHTML = "Hello! <b>" + escapeHtml(name) + "</b>";
        }
        // initials for the avatar
        const initials = (data.user.name || data.user.email)
          .trim()
          .split(/\s+/)
          .slice(0, 2)
          .map(function (w) {
            return w.charAt(0).toUpperCase();
          })
          .join("");
        const avatar = document.getElementById("acctIcon");
        if (avatar) avatar.textContent = initials || "?";
        if (miLogin) miLogin.hidden = true;
        if (miSignup) miSignup.hidden = true;
        if (miLogout) miLogout.hidden = false;
      } else {
        btn.classList.remove("signed-in");
        if (greeting) greeting.textContent = "Belum masuk";
        const avatar = document.getElementById("acctIcon");
        if (avatar) avatar.textContent = "?";
        if (miLogin) miLogin.hidden = false;
        if (miSignup) miSignup.hidden = false;
        if (miLogout) miLogout.hidden = true;
      }
    } catch (err) {
      // Server unreachable: leave the anonymous state.
      console.warn("auth check failed:", err);
    }
  }

  async function logout() {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    } catch (err) {
      console.warn("logout failed:", err);
    }
    localStorage.removeItem("dk_user");
    window.location.reload();
  }

  // Session gate. The API client already redirects on a 401, but pages
  // with privileged data should check up-front so an anonymous visitor
  // never sees a flash of someone else's numbers before the redirect.
  // Returns true when a session exists.
  async function requireAuth() {
    try {
      const res = await fetch("/api/auth/me", { credentials: "include" });
      const data = await res.json();
      if (data && data.user) return true;
    } catch (err) {
      // Server unreachable: treat as anonymous rather than dead-ending.
      return false;
    }
    const back = encodeURIComponent(
      window.location.pathname + window.location.search,
    );
    window.location.href = "/login.html?redirect=" + back;
    return false;
  }

  // Shared helpers for the other pages
  global.NurtraShared = {
    fmt: fmt,
    fmtDate: fmtDate,
    escapeHtml: escapeHtml,
    toast: toast,
    applyTheme: applyTheme,
    refreshAuthUI: refreshAuthUI,
    requireAuth: requireAuth,
    logout: logout,
  };

  document.addEventListener("DOMContentLoaded", init);
})(window);
