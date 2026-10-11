/* Nurtra — profile/settings page logic (profile.html). */
(function () {
  "use strict";

  const api = window.NurtraAPI;
  const $ = function (id) { return document.getElementById(id); };
  const shared = window.NurtraShared;

  async function loadProfile() {
    if (!(await shared.requireAuth())) return;
    try {
      const res = await api.getProfile();
      const p = res.profile;
      const f = $("profileForm");
      f.name.value = p.name || "";
      f.gender.value = p.gender || "male";
      f.age.value = p.age || 25;
      f.weight_kg.value = p.weight_kg || 70;
      f.height_cm.value = p.height_cm || 170;
      f.activity.value = p.activity || "moderate";
      f.weekly_loss_kg.value = p.weekly_loss_kg || 0.5;
      f.fasting_protocol.value = p.fasting_protocol || "";
      renderProfileResult(res);
    } catch (err) {
      shared.toast(err.message);
    }
  }

  function renderProfileResult(res) {
    const limits = res.limits_applied || {};
    const lines = [
      "BMR: " + shared.fmt(res.bmr) + " kkal",
      "TDEE: " + shared.fmt(res.tdee) + " kkal",
      "Target harian: " + shared.fmt(res.target_kcal) + " kkal (defisit " + shared.fmt(res.deficit_kcal) + " kkal/hari)",
      "Protein: " + Math.round(res.macros.protein.target_g) + " g · Karbo: " +
        Math.round(res.macros.carb.target_g) + " g · Lemak: " + Math.round(res.macros.fat.target_g) + " g",
    ];
    if (limits.floored_at_kcal) {
      lines.push("⚠ Target tidak boleh di bawah " + shared.fmt(limits.floored_at_kcal) + " kkal (batas aman).");
    }
    if (limits.capped_deficit_kcal) {
      lines.push("⚠ Defisit dibatasi maksimal 25% dari TDEE.");
    }
    $("profileResult").textContent = lines.join("\n");
  }

  async function submitProfile(form) {
    if (!(await shared.requireAuth())) return;
    const fd = new FormData(form);
    const body = {
      name: fd.get("name").toString(),
      gender: fd.get("gender").toString(),
      age: parseInt(fd.get("age"), 10),
      weight_kg: parseFloat(fd.get("weight_kg")),
      height_cm: parseFloat(fd.get("height_cm")),
      activity: fd.get("activity").toString(),
      weekly_loss_kg: parseFloat(fd.get("weekly_loss_kg")),
      fasting_protocol: fd.get("fasting_protocol").toString() || null,
    };
    try {
      const res = await api.saveProfile(body);
      renderProfileResult(res);
      shared.toast("Profil disimpan · target " + shared.fmt(res.target_kcal) + " kkal");
    } catch (err) {
      shared.toast(err.message);
    }
  }

  function init() {
    $("profileForm").addEventListener("submit", function (e) {
      e.preventDefault();
      submitProfile(e.target);
    });
    loadProfile();

    const shared = window.NurtraShared;
    if (shared) shared.refreshAuthUI();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
