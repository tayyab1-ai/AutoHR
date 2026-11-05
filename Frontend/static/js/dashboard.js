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

  var draftCfg = document.getElementById("dashboard-draft-config");
  var deleteUrlTemplate = draftCfg ? draftCfg.getAttribute("data-delete-url-template") : "";
  var jobIdPlaceholder = draftCfg ? draftCfg.getAttribute("data-job-id-placeholder") : "";

  function jobApiPath(template, jobId, fallback) {
    if (!template) return fallback.replace("{id}", jobId);
    return template.split(jobIdPlaceholder).join(jobId);
  }

  function getCsrf() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  document.querySelectorAll("[data-draft-continue]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-draft-continue");
      activatePanel("create-job");
      if (typeof window.loadJobDraft === "function") {
        window.loadJobDraft(id);
      }
    });
  });

  document.querySelectorAll("[data-draft-delete]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-draft-delete");
      if (!window.confirm("Delete this draft? This cannot be undone.")) return;
      fetch(jobApiPath(deleteUrlTemplate, id, "/dashboard/jobs/{id}/delete/"), {
        method: "POST",
        headers: { "X-CSRFToken": getCsrf(), Accept: "application/json" },
      })
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (!data.ok) return;
          var row = document.querySelector('[data-draft-row="' + id + '"]');
          if (row) row.remove();
        });
    });
  });

});
