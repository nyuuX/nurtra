/* Nurtra — Interactive User Onboarding Walkthrough
   
   First-time auto-trigger on login/signup. Manual replay via menu.
   Steps: Welcome (input name+target) → Highlight meal add → Highlight calorie ring → Done
*/
(function (global) {
  "use strict";

  const COMPLETED_KEY = "nurtra_onboard_completed";
  const PENDING_KEY = "nurtra_onboard_pending";

  const steps = [
    {
      id: "welcome",
      title: "Sambutan dari NumNum!",
      body: "",
      image: "/img/numnum-menyapa.png",
      type: "welcome",
    },
    {
      id: "add-meal",
      title: "Catat Makananmu <svg width=\"20\" height=\"20\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2\"/><path d=\"M7 2v20\"/><path d=\"M21 15V2a5 5 0 0 0-5 5v6\"/></svg>",
      body: "Gunakan tombol '+' di setiap kategori makanan atau 'Add Custom Meal' untuk mencatat apa yang kamu makan. Bisa cari, foto, atau AI parse!",
      targetSelector: ".add-btn",
      type: "highlight",
    },
    {
      id: "calorie-ring",
      title: "Monitor Sisa Kalorimu <svg width=\"20\" height=\"20\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><line x1=\"18\" y1=\"20\" x2=\"18\" y2=\"10\"/><line x1=\"12\" y1=\"20\" x2=\"12\" y2=\"4\"/><line x1=\"6\" y1=\"20\" x2=\"6\" y2=\"14\"/></svg>",
      body: "Lingkaran di atas menunjukkan berapa kalori yang tersisa hari ini. Tetap dalam target untuk hasil optimal!",
      targetSelector: "#heroCard",
      type: "highlight",
    },
    {
      id: "done",
      title: "Siap Dimulai! <svg width=\"20\" height=\"20\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 2l3 7h7l-6 4 2 7-6-4-6 4 2-7-6-4h7z\"/></svg>",
      body: "Kamu sekarang siap melacak defisit kalorimu dengan Nurtra. Atur profil kamu di menu Target, dan cek laporan mingguan di Laporan. Selamat menggunakan!",
      image: "/img/numnum-girang.png",
      type: "done",
      buttonLabel: "Mulai Gunakan Aplikasi",
    },
  ];

  let currentStep = 0;
  let overlay = null;
  let card = null;
  let spotlight = null;
  let stepData = {};

  function $(id) {
    return document.getElementById(id);
  }

  function startOnboarding() {
    // Only works on dashboard
    if (!$("viewDashboard")) {
      return;
    }
    // Reset to step 0
    currentStep = 0;
    stepData = {};
    createOverlay();
    showStep();
    document.body.style.overflow = "hidden";
  }

  function createOverlay() {
    if (overlay) return;

    overlay = document.createElement("div");
    overlay.id = "obOverlay";
    overlay.className = "ob-overlay";

    spotlight = document.createElement("div");
    spotlight.id = "obSpotlight";
    spotlight.className = "ob-spotlight";
    spotlight.style.display = "none";
    overlay.appendChild(spotlight);

    card = document.createElement("div");
    card.id = "obCard";
    card.className = "ob-card";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");
    overlay.appendChild(card);

    document.body.appendChild(overlay);
  }

  function showStep() {
    const step = steps[currentStep];
    if (!step) return;

    // Save input values if transitioning away from welcome step
    if (currentStep > 0 && steps[currentStep - 1].type === "welcome") {
      captureFormData();
    }

    card.innerHTML = "";

    // Media (image)
    if (step.image) {
      const media = document.createElement("div");
      media.className = "ob-media";
      const img = document.createElement("img");
      img.src = step.image;
      img.alt = "NumNum";
      media.appendChild(img);
      card.appendChild(media);
    }

    // Title
    const title = document.createElement("h2");
    title.id = "obTitle";
    title.className = "ob-title";
    title.innerHTML = step.title;
    card.appendChild(title);

    // Body text
    const body = document.createElement("p");
    body.className = "ob-body";
    body.textContent = step.body;
    card.appendChild(body);

    // Welcome step: read user name from localStorage
    if (step.type === "welcome") {
      const userName = (() => {
        try {
          const dkUser = localStorage.getItem("dk_user");
          if (dkUser) {
            const parsed = JSON.parse(dkUser);
            return parsed.name || parsed.email.split("@")[0];
          }
        } catch (e) {}
        return "Teman";
      })();
      const greeting = document.createElement("p");
      greeting.className = "ob-greeting";
      greeting.style.cssText =
        "font-weight:600;font-size:1.05rem;color:var(--text);margin-top:0.5rem;";
      greeting.innerHTML = `Halo <strong>${userName}</strong>! Kenalin aku NumNum asisten pribadi kamu untuk bantuin kamu lacak defisit kalori kamu. Ayo kenalan sama fitur-fitur utama Nurtra.`;
      card.appendChild(greeting);
    }

    // Navigation + dots
    const nav = document.createElement("div");
    nav.className = "ob-nav";

    const skipBtn = document.createElement("button");
    skipBtn.className = "ob-btn ob-btn-skip";
    skipBtn.textContent = "Lewati";
    skipBtn.addEventListener("click", skipOnboarding);
    nav.appendChild(skipBtn);

    const backBtn = document.createElement("button");
    backBtn.className = "ob-btn ob-btn-back";
    backBtn.textContent = "Kembali";
    backBtn.disabled = currentStep === 0;
    backBtn.addEventListener("click", prevStep);
    nav.appendChild(backBtn);

    const nextBtn = document.createElement("button");
    nextBtn.className = "ob-btn ob-btn-next btn-primary";
    nextBtn.textContent = step.type === "done" ? step.buttonLabel : "Lanjut";
    nextBtn.addEventListener("click", nextStep);
    nav.appendChild(nextBtn);

    card.appendChild(nav);

    // Dots
    const dots = document.createElement("div");
    dots.className = "ob-dots";
    for (let i = 0; i < steps.length; i++) {
      const dot = document.createElement("span");
      dot.className = "ob-dot" + (i === currentStep ? " active" : "");
      dots.appendChild(dot);
    }
    card.appendChild(dots);

    // Highlight step: show spotlight & position card
    if (step.type === "highlight") {
      showSpotlight(step.targetSelector);
    } else {
      spotlight.style.display = "none";
    }

    // Position card
    positionCard();

    // Handle window resize
    window.addEventListener("resize", () => {
      if (spotlight.style.display !== "none") {
        showSpotlight(step.targetSelector);
      }
      positionCard();
    });
  }

  function showSpotlight(selector) {
    const target = document.querySelector(selector);
    if (!target) {
      spotlight.style.display = "none";
      if (overlay) overlay.style.background = "rgba(10,10,10,0.65)";
      return;
    }

    if (overlay) overlay.style.background = "transparent";

    // Scroll target into view
    target.scrollIntoView({ behavior: "auto", block: "center" });

    // Get rect after scroll
    const rect = target.getBoundingClientRect();
    const pad = 8; // padding around spotlight

    spotlight.style.display = "block";
    spotlight.style.top = Math.max(0, rect.top - pad) + "px";
    spotlight.style.left = Math.max(0, rect.left - pad) + "px";
    spotlight.style.width =
      Math.min(window.innerWidth, rect.width + pad * 2) + "px";
    spotlight.style.height =
      Math.min(window.innerHeight, rect.height + pad * 2) + "px";
  }

  function positionCard() {
    if (!card) return;

    // On mobile, card is full-width near bottom or centered
    // On desktop, centered
    const isMobile = window.innerWidth < 600;

    if (isMobile) {
      card.style.position = "fixed";
      card.style.bottom = "60px";
      card.style.left = "16px";
      card.style.right = "16px";
      card.style.top = "auto";
    } else {
      card.style.position = "fixed";
      card.style.left = "50%";
      card.style.top = "50%";
      card.style.transform = "translate(-50%, -50%)";
      card.style.bottom = "auto";
      card.style.right = "auto";
    }
  }

  function captureFormData() {
    // No inputs on welcome step anymore
  }

  async function saveToProfile() {
    try {
      // Don't fail the onboarding if profile save fails (anonymous user)
      await fetch("/api/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_kcal: stepData.target_kcal }),
        credentials: "include",
      });
    } catch (err) {
      // Silent fail — user might not be authenticated yet
      console.debug("onboarding: profile save skipped (anon user ok)");
    }
  }

  function nextStep() {
    if (currentStep < steps.length - 1) {
      currentStep++;
      showStep();
    } else {
      completeOnboarding();
    }
  }

  function prevStep() {
    if (currentStep > 0) {
      currentStep--;
      showStep();
    }
  }

  function skipOnboarding() {
    completeOnboarding();
  }

  function completeOnboarding() {
    localStorage.setItem(COMPLETED_KEY, "1");
    sessionStorage.removeItem(PENDING_KEY);
    hideOverlay();
    document.body.style.overflow = "";
  }

  function hideOverlay() {
    if (overlay) {
      overlay.remove();
      overlay = null;
      card = null;
      spotlight = null;
    }
  }

  function injectMenuButton() {
    // Only show onboarding menu item if user is logged in
    const isLogged = localStorage.getItem("dk_user");
    if (!isLogged) return;

    const menu = $("acctMenu");
    if (!menu) return;

    // Check if button already exists
    if (menu.querySelector("[data-ob-menu]")) return;

    const item = document.createElement("button");
    item.className = "acct-item";
    item.type = "button";
    item.setAttribute("data-ob-menu", "1");
    item.innerHTML =
      '<span class="acct-ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span><span>Panduan Aplikasi</span>';
    item.addEventListener("click", startOnboarding);
    menu.appendChild(item);
  }

  function init() {
    // Auto-trigger if pending + not completed (only on dashboard)
    if (
      $("viewDashboard") &&
      sessionStorage.getItem(PENDING_KEY) &&
      !localStorage.getItem(COMPLETED_KEY)
    ) {
      startOnboarding();
      sessionStorage.removeItem(PENDING_KEY);
    }

    // Inject menu button (works on all pages if acctMenu exists)
    injectMenuButton();
  }

  global.NurtraOnboarding = {
    start: startOnboarding,
    reset: () => localStorage.removeItem(COMPLETED_KEY),
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
