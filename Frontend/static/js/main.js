// Shared behaviour for the landing page and the auth page:
// scroll-reveal animation init, Bootstrap tooltips, animated stat counters,
// and the sign-in/create-account toggle.

document.addEventListener("DOMContentLoaded", function () {
  if (window.AOS) {
    AOS.init({ duration: 650, once: true, offset: 60, easing: "ease-out-cubic" });
  }

  // Bootstrap tooltips for every "i" info icon.
  var tooltipTriggers = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipTriggers.forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  // Animated count-up for hero / stat numbers that carry data-count-to.
  var counters = document.querySelectorAll("[data-count-to]");
  var hasRun = new WeakMap();

  function animateCounter(el) {
    if (hasRun.get(el)) return;
    hasRun.set(el, true);
    var target = parseFloat(el.getAttribute("data-count-to"));
    var suffix = el.getAttribute("data-count-suffix") || "";
    var prefix = el.getAttribute("data-count-prefix") || "";
    var decimals = el.getAttribute("data-count-decimals") ? parseInt(el.getAttribute("data-count-decimals"), 10) : 0;
    var duration = 1100;
    var start = null;

    function step(timestamp) {
      if (!start) start = timestamp;
      var progress = Math.min((timestamp - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var value = target * eased;
      el.textContent = prefix + value.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + suffix;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  if (counters.length) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) animateCounter(entry.target);
        });
      },
      { threshold: 0.4 }
    );
    counters.forEach(function (el) {
      observer.observe(el);
    });
  }

  // Password show/hide toggle (used on auth page).
  document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetId = btn.getAttribute("data-toggle-password");
      var input = document.getElementById(targetId);
      if (!input) return;
      var icon = btn.querySelector("i");
      if (input.type === "password") {
        input.type = "text";
        if (icon) { icon.classList.remove("bi-eye"); icon.classList.add("bi-eye-slash"); }
      } else {
        input.type = "password";
        if (icon) { icon.classList.remove("bi-eye-slash"); icon.classList.add("bi-eye"); }
      }
    });
  });

  // Sign-in / create-account toggle on the auth page (no page reload).
  var authCard = document.querySelector("[data-auth-card]");
  if (authCard) {
    var signupPanel = authCard.querySelector('[data-auth-panel="signup"]');
    var signinPanel = authCard.querySelector('[data-auth-panel="signin"]');
    var switches = authCard.querySelectorAll("[data-auth-switch]");
    switches.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mode = btn.getAttribute("data-auth-switch");
        if (mode === "signup") {
          signupPanel.classList.remove("d-none");
          signinPanel.classList.add("d-none");
        } else {
          signinPanel.classList.remove("d-none");
          signupPanel.classList.add("d-none");
        }
      });
    });
  }

  // Demo-only submit handler: validates with Bootstrap styles, then
  // shows a success banner and redirects to the dashboard preview.
  document.querySelectorAll("[data-demo-auth-form]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      event.stopPropagation();
      if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
      }
      var banner = form.querySelector("[data-form-banner]");
      var submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Please wait...';
      }
      if (banner) {
        banner.classList.remove("d-none");
        banner.textContent = form.getAttribute("data-success-message") || "Success. Redirecting...";
      }
      window.setTimeout(function () {
        window.location.href = "/dashboard/";
      }, 650);
    });
  });
});
