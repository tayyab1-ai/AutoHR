// Dashboard behaviour: same-screen navigation between panels, sidebar
// collapse/mobile toggle, animated bars, candidate split view, tabs,
// and the Create Job skill-chip input. Everything here is client-side
// only -- no network calls, since this is a frontend-only preview.

document.addEventListener("DOMContentLoaded", function () {
  if (window.AOS) {
    AOS.init({ duration: 500, once: true, offset: 40 });
  }

  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  /* ---------------- Same-screen panel navigation ---------------- */
  var navItems = document.querySelectorAll("[data-panel-target]");
  var panels = document.querySelectorAll("[data-panel]");
  var pageTitle = document.querySelector("[data-page-title]");
  var pageSubtitle = document.querySelector("[data-page-subtitle]");

  function activatePanel(name) {
    panels.forEach(function (panel) {
      panel.classList.toggle("is-active", panel.getAttribute("data-panel") === name);
    });
    navItems.forEach(function (item) {
      item.classList.toggle("is-active", item.getAttribute("data-panel-target") === name);
    });
    var meta = navItems[0] ? null : null;
    var activeNav = document.querySelector('[data-panel-target="' + name + '"]');
    if (activeNav && pageTitle) {
      pageTitle.textContent = activeNav.getAttribute("data-panel-title") || pageTitle.textContent;
    }
    if (activeNav && pageSubtitle) {
      pageSubtitle.textContent = activeNav.getAttribute("data-panel-subtitle") || "";
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
    animateVisiblePanel(name);
    // Close the mobile sidebar after choosing a section.
    document.querySelector(".db-sidebar")?.classList.remove("is-mobile-open");
  }

  navItems.forEach(function (item) {
    item.addEventListener("click", function () {
      activatePanel(item.getAttribute("data-panel-target"));
    });
  });

  document.querySelectorAll("[data-go-panel]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      activatePanel(btn.getAttribute("data-go-panel"));
    });
  });

  /* ---------------- Sidebar collapse (desktop) / mobile toggle ---------------- */
  var sidebar = document.querySelector(".db-sidebar");
  var collapseBtn = document.querySelector("[data-sidebar-collapse]");
  if (collapseBtn && sidebar) {
    collapseBtn.addEventListener("click", function () {
      sidebar.classList.toggle("is-collapsed");
    });
  }
  var mobileToggle = document.querySelector("[data-sidebar-mobile-toggle]");
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener("click", function () {
      sidebar.classList.toggle("is-mobile-open");
    });
  }

  /* ---------------- Animate funnel bars + chart bars on first view ---------------- */
  function animateVisiblePanel(name) {
    var panel = document.querySelector('[data-panel="' + name + '"]');
    if (!panel) return;
    panel.querySelectorAll(".db-funnel-fill[data-pct]").forEach(function (bar) {
      var pct = bar.getAttribute("data-pct");
      requestAnimationFrame(function () {
        bar.style.width = pct + "%";
      });
    });
    panel.querySelectorAll(".db-chart-bar[data-height]").forEach(function (bar) {
      var height = bar.getAttribute("data-height");
      requestAnimationFrame(function () {
        bar.style.height = height + "%";
      });
    });
    panel.querySelectorAll(".db-score-bar-fill[data-score]").forEach(function (bar) {
      var score = bar.getAttribute("data-score");
      requestAnimationFrame(function () {
        bar.style.width = score + "%";
      });
    });
  }
  animateVisiblePanel("overview");

  /* ---------------- Candidate split view (Applications panel) ---------------- */
  document.querySelectorAll("[data-candidate-card]").forEach(function (card) {
    card.addEventListener("click", function () {
      var id = card.getAttribute("data-candidate-card");
      document.querySelectorAll("[data-candidate-card]").forEach(function (c) {
        c.classList.toggle("is-selected", c === card);
      });
      document.querySelectorAll("[data-candidate-detail]").forEach(function (detail) {
        var match = detail.getAttribute("data-candidate-detail") === id;
        detail.classList.toggle("d-none", !match);
        if (match) {
          detail.querySelectorAll(".db-score-bar-fill[data-score]").forEach(function (bar) {
            var score = bar.getAttribute("data-score");
            bar.style.width = "0%";
            requestAnimationFrame(function () {
              bar.style.width = score + "%";
            });
          });
        }
      });
    });
  });

  /* ---------------- Generic tab bars (candidate detail: overview/breakdown) ---------------- */
  document.querySelectorAll("[data-tab-group]").forEach(function (group) {
    var groupName = group.getAttribute("data-tab-group");
    group.querySelectorAll("[data-tab-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tabName = btn.getAttribute("data-tab-btn");
        group.querySelectorAll("[data-tab-btn]").forEach(function (b) {
          b.classList.toggle("is-active", b === btn);
        });
        document.querySelectorAll('[data-tab-panel-group="' + groupName + '"]').forEach(function (panel) {
          panel.classList.toggle("is-active", panel.getAttribute("data-tab-panel") === tabName);
        });
      });
    });
  });

  /* ---------------- Create Job: skill chip input ---------------- */
  function wireChipInput(inputSelector, listSelector, hiddenSelector) {
    var input = document.querySelector(inputSelector);
    var list = document.querySelector(listSelector);
    var hidden = document.querySelector(hiddenSelector);
    if (!input || !list || !hidden) return;
    var items = [];

    function render() {
      list.innerHTML = "";
      items.forEach(function (value, index) {
        var chip = document.createElement("span");
        chip.className = "db-skill-chip";
        chip.innerHTML = '<span></span><button type="button" aria-label="Remove">&times;</button>';
        chip.querySelector("span").textContent = value;
        chip.querySelector("button").addEventListener("click", function () {
          items.splice(index, 1);
          render();
        });
        list.appendChild(chip);
      });
      hidden.value = items.join(", ");
    }

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === ",") {
        event.preventDefault();
        var value = input.value.trim().replace(/,$/, "");
        if (value && !items.includes(value)) {
          items.push(value);
          render();
        }
        input.value = "";
      }
    });
  }
  wireChipInput("#required-skill-input", "#required-skill-list", "#required_skills_hidden");
  wireChipInput("#bonus-skill-input", "#bonus-skill-list", "#bonus_skills_hidden");

  /* ---------------- Create Job: live preview + demo "save" ---------------- */
  var createJobForm = document.querySelector("[data-create-job-form]");
  if (createJobForm) {
    var previewFields = {
      title: document.querySelector("[data-preview-title]"),
      exp: document.querySelector("[data-preview-exp]"),
      salary: document.querySelector("[data-preview-salary]"),
      city: document.querySelector("[data-preview-city]"),
      hires: document.querySelector("[data-preview-hires]"),
    };
    function syncPreview() {
      var title = createJobForm.querySelector("#job_title")?.value || "Untitled role";
      var minExp = createJobForm.querySelector("#min_experience")?.value;
      var maxExp = createJobForm.querySelector("#max_experience")?.value;
      var minSalary = createJobForm.querySelector("#min_salary")?.value;
      var maxSalary = createJobForm.querySelector("#max_salary")?.value;
      var city = createJobForm.querySelector("#job_city")?.value || "Not set";
      var hires = createJobForm.querySelector("#target_hires")?.value || "1";

      if (previewFields.title) previewFields.title.textContent = title || "Untitled role";
      if (previewFields.exp) {
        previewFields.exp.textContent = minExp ? minExp + (maxExp ? " – " + maxExp : "+") + " years" : "Not set";
      }
      if (previewFields.salary) {
        previewFields.salary.textContent = minSalary
          ? "PKR " + Number(minSalary).toLocaleString("en-PK") + (maxSalary ? " – " + Number(maxSalary).toLocaleString("en-PK") : "+") + " / month"
          : "Not set";
      }
      if (previewFields.city) previewFields.city.textContent = city;
      if (previewFields.hires) previewFields.hires.textContent = hires;
    }
    createJobForm.addEventListener("input", syncPreview);
    syncPreview();

    createJobForm.addEventListener("submit", function (event) {
      event.preventDefault();
      event.stopPropagation();
      if (!createJobForm.checkValidity()) {
        createJobForm.classList.add("was-validated");
        return;
      }
      var resultBox = document.querySelector("[data-create-job-result]");
      var formBox = document.querySelector("[data-create-job-fields]");
      if (formBox) formBox.classList.add("d-none");
      if (resultBox) resultBox.classList.remove("d-none");
    });
  }
});
