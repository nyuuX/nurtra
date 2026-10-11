/* Nurtra — login / signup page.
 *
 * Email+password only for now. The Google button is wired but shows a notice
 * until OAuth credentials are configured on the backend.
 *
 * Auth state lives in localStorage so every page can check it on load;
 * the API call is also made with credentials:"include" so the httpOnly
 * cookie is set for same-origin requests.
 */

(function () {
  "use strict";

  const API = "/api/auth";
  let mode = "login";

  const el = (id) => document.getElementById(id);
  const tabs = { login: el("tabLogin"), signup: el("tabSignup") };
  const form = el("authForm");
  const nameWrap = el("nameWrap");
  const title = el("authTitle");
  const sub = el("authSub");
  const btn = el("btnAuth");
  const errorBox = el("authError");
  const switchLink = el("switchLink");
  const googleBtn = el("btnGoogle");

  // Where to land after a successful auth. `?redirect=` lets gated pages
  // (report/profile, or a 401 from a write) send the user back where they
  // came from instead of dumping them on the dashboard.
  function redirectTarget() {
    const back = new URLSearchParams(window.location.search).get("redirect");
    if (back && back.startsWith("/")) return back;
    return "/";
  }

  // Already logged in? Skip the form entirely.
  fetch(`${API}/me`, { credentials: "include" })
    .then((r) => r.json())
    .then((d) => {
      if (d && d.user) window.location.href = redirectTarget();
    })
    .catch(() => {});

  function setMode(next) {
    mode = next;
    tabs.login.classList.toggle("active", next === "login");
    tabs.signup.classList.toggle("active", next === "signup");
    nameWrap.hidden = next !== "signup";
    title.textContent = next === "login" ? "Masuk" : "Daftar";
    sub.textContent =
      next === "login"
        ? "Lanjutkan pelacakan defisit kalorimu"
        : "Buat akun untuk menyimpan progressmu";
    btn.textContent = next === "login" ? "Masuk" : "Daftar Sekarang";
    switchLink.textContent = next === "login" ? "Daftar gratis" : "Sudah punya akun?";
    hideError();
  }

  // The account dropdown can link here with ?mode=signup to land on the
  // registration form directly. Must run after setMode is defined but the
  // final setMode("login") call below honours it instead of resetting.
  const params = new URLSearchParams(window.location.search);
  const initialMode = params.get("mode") === "signup" ? "signup" : "login";

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.add("show");
  }

  function hideError() {
    errorBox.classList.remove("show");
  }

  tabs.login.addEventListener("click", () => setMode("login"));
  tabs.signup.addEventListener("click", () => setMode("signup"));
  switchLink.addEventListener("click", (e) => {
    e.preventDefault();
    setMode(mode === "login" ? "signup" : "login");
  });
  form.addEventListener("input", hideError);

  async function persistLocal(user, token) {
    localStorage.setItem(
      "dk_user",
      JSON.stringify({ email: user.email, name: user.name, token })
    );
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();
    btn.disabled = true;
    const prev = btn.textContent;
    btn.textContent = mode === "login" ? "Memproses…" : "Mendaftarkan…";

    const email = el("authEmail").value.trim();
    const password = el("authPassword").value;
    const name = el("authName").value.trim();

    if (!email || !password) {
      showError("Email dan password wajib diisi");
      btn.disabled = false;
      btn.textContent = prev;
      return;
    }

    const body = mode === "signup" ? { email, password, name } : { email, password };

    try {
      const res = await fetch(`${API}/${mode === "signup" ? "signup" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        credentials: "include",
      });

      const data = await res.json();
      if (!res.ok) {
        showError((data && data.detail) || "Terjadi kesalahan");
        btn.disabled = false;
        btn.textContent = prev;
        return;
      }

      await persistLocal(data.user, data.token);

      // First signup: adopt the anonymous demo data so nothing is lost.
      if (mode === "signup") {
        try {
          await fetch(`${API}/migrate-anonymous`, {
            method: "POST",
            credentials: "include",
          });
        } catch (err) {
          // Non-fatal — the account works either way.
          console.warn("migrate-anonymous failed:", err);
        }
      }

      window.location.href = redirectTarget();
    } catch (err) {
      showError("Gagal terhubung ke server. Coba lagi.");
      btn.disabled = false;
      btn.textContent = prev;
    }
  });

  googleBtn.addEventListener("click", () => {
    showError("Login Google belum dikonfigurasi. Gunakan email + password untuk sekarang.");
  });

  setMode(initialMode);
})();
