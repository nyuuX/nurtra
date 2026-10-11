/* Nurtra — thin API client. All backend calls go through here. */
(function (global) {
  "use strict";

  const BASE = "/api";

  async function request(path, options) {
    const opts = options || {};

    // Atria Dawn is a reasoning model: insight calls legitimately take
    // 60-150s. Give slow AI endpoints a long leash, everything else a
    // short one, so a hung server surfaces instead of spinning forever.
    const isAI = path.indexOf("/ai/") === 0;
    const timeoutMs = isAI ? 240000 : 15000;
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, timeoutMs);

    let response;
    try {
      response = await fetch(BASE + path, {
        method: opts.method || "GET",
        headers: Object.assign(
          { "Content-Type": "application/json" },
          opts.headers || {}
        ),
        body: opts.body ? JSON.stringify(opts.body) : undefined,
        signal: controller.signal,
      });
    } catch (err) {
      clearTimeout(timer);
      if (err.name === "AbortError") {
        throw new Error(
          isAI
            ? "Atria Dawn terlalu lama merespons. Coba lagi."
            : "Request timeout. Periksa koneksi server."
        );
      }
      throw new Error("Tidak bisa terhubung ke server. Pastikan uvicorn berjalan.");
    }
    clearTimeout(timer);

    if (response.status === 204) {
      return null;
    }
    const text = await response.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (e) {
        data = { raw: text };
      }
    }
    if (!response.ok) {
      const msg =
        (data && (data.detail || (data.error && data.error.message))) ||
        "Request gagal (" + response.status + ")";
      // A 401 means the write endpoint refused an anonymous session.
      // Send the user to login rather than showing a bare error toast.
      if (response.status === 401) {
        const back = encodeURIComponent(
          window.location.pathname + window.location.search
        );
        window.location.href = "/login.html?redirect=" + back;
        throw new Error("Login diperlukan");
      }
      throw new Error(msg);
    }
    return data;
  }

  const api = {
    // ---- Core -------------------------------------------------------
    health: () => request("/health"),
    getToday: () => request("/today"),
    getDay: (date) => request("/days/" + date),
    getProfile: () => request("/profile"),
    saveProfile: (profile) =>
      request("/profile", { method: "POST", body: profile }),

    searchFoods: (q, limit) =>
      request("/foods/search?q=" + encodeURIComponent(q) + "&limit=" + (limit || 12)),
    volumeFoods: () => request("/foods/volume"),
    listExercises: () => request("/exercises"),

    addMeal: (meal, entry) =>
      request("/meals/" + meal, { method: "POST", body: entry }),
    deleteMeal: (meal, entryId) =>
      request("/meals/" + meal + "/" + entryId, { method: "DELETE" }),

    addExercise: (entry) =>
      request("/exercises", { method: "POST", body: entry }),
    deleteExercise: (entryId) =>
      request("/exercises/" + entryId, { method: "DELETE" }),

    logWeight: (weightKg) =>
      request("/weight", { method: "POST", body: { weight_kg: weightKg } }),

    getFavorites: () => request("/favorites"),
    addFavorite: (fav) => request("/favorites", { method: "POST", body: fav }),
    deleteFavorite: (favId) =>
      request("/favorites/" + favId, { method: "DELETE" }),

    // ---- Report -----------------------------------------------------
    getReport: (weeksBack) =>
      request("/report" + (weeksBack ? "?weeks_back=" + weeksBack : "")),

    // ---- AI (Atria Dawn) --------------------------------------------
    aiStatus: () => request("/ai/status"),
    parseFoods: (text) =>
      request("/ai/parse-foods", { method: "POST", body: { text: text } }),
    suggestRecipes: (pantry, targetKcal) =>
      request("/ai/recipes", {
        method: "POST",
        body: { pantry: pantry, target_kcal: targetKcal || 500 },
      }),
    weeklyInsights: (week) =>
      request("/ai/weekly-insights", { method: "POST", body: { week: week } }),
  };

  global.NurtraAPI = api;
})(window);
