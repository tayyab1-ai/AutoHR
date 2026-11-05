document.addEventListener("DOMContentLoaded", function () {
  var backdrop = document.querySelector("[data-profile-wizard-backdrop]");
  if (!backdrop) return;

  var stepLabel = backdrop.querySelector("[data-profile-step-label]");
  var errBox = backdrop.querySelector("[data-profile-wizard-error]");
  var okBox = backdrop.querySelector("[data-profile-wizard-success]");
  var nextBtn = backdrop.querySelector("[data-profile-next]");
  var prevBtn = backdrop.querySelector("[data-profile-prev]");
  var saveExitBtn = backdrop.querySelector("[data-profile-save-exit]");
  var closeBtn = backdrop.querySelector("[data-profile-close]");
  var summaryEl = backdrop.querySelector("[data-profile-summary]");

  var currentStep = 1;
  var lastIntegrations = null;

  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function showError(msg) {
    if (okBox) okBox.classList.add("d-none");
    if (!errBox) return;
    errBox.textContent = msg;
    errBox.classList.remove("d-none");
  }

  function showSuccess(msg) {
    if (errBox) errBox.classList.add("d-none");
    if (!okBox) return;
    okBox.textContent = msg;
    okBox.classList.remove("d-none");
    window.setTimeout(function () {
      okBox.classList.add("d-none");
    }, 2800);
  }

  function clearError() {
    if (errBox) errBox.classList.add("d-none");
  }

  function setIntegrationBadges(integrations) {
    if (!integrations) return;
    Object.keys(integrations).forEach(function (key) {
      var badge = backdrop.querySelector('[data-int-badge="' + key + '"]');
      if (!badge) return;
      var st = integrations[key].status || "not_connected";
      badge.textContent = st === "connected" ? "Connected" : "Not connected";
      badge.classList.toggle("connected", st === "connected");
      badge.classList.toggle("not-connected", st !== "connected");
    });
  }

  function showStep(step) {
    currentStep = step;
    backdrop.querySelectorAll("[data-profile-step-panel]").forEach(function (panel) {
      var n = Number(panel.getAttribute("data-profile-step-panel"));
      panel.classList.toggle("d-none", n !== step);
    });
    backdrop.querySelectorAll("[data-step-seg]").forEach(function (seg) {
      var n = Number(seg.getAttribute("data-step-seg"));
      seg.classList.toggle("is-done", n < step);
      seg.classList.toggle("is-active", n === step);
    });
    if (stepLabel) stepLabel.textContent = "Step " + step + " of 7";
    if (prevBtn) prevBtn.classList.toggle("invisible", step <= 1);
    if (nextBtn) {
      nextBtn.innerHTML =
        step >= 7
          ? 'Complete setup <i class="bi bi-check-lg"></i>'
          : 'Next step <i class="bi bi-arrow-right"></i>';
    }
    if (step === 7) buildSummary();
    clearError();
  }

  function collectStepData(step) {
    var data = {};
    var panel = backdrop.querySelector('[data-profile-step-panel="' + step + '"]');
    if (!panel) return data;
    panel.querySelectorAll("[data-pf]").forEach(function (el) {
      var key = el.getAttribute("data-pf");
      if (el.disabled) return;
      if (el.type === "checkbox") {
        data[key] = el.checked;
      } else {
        data[key] = el.value;
      }
    });
    return data;
  }

  function fillFromState(state) {
    if (!state) return;
    if (state.step_data) {
      Object.keys(state.step_data).forEach(function (stepKey) {
        var block = state.step_data[stepKey];
        if (!block || typeof block !== "object") return;
        Object.keys(block).forEach(function (field) {
          var el = backdrop.querySelector('[data-pf="' + field + '"]');
          if (!el) return;
          if (el.type === "checkbox") {
            el.checked = !!block[field];
          } else if (block[field] != null) {
            el.value = block[field];
          }
        });
      });
    }
    lastIntegrations = state.integrations || null;
    setIntegrationBadges(state.integrations);
    if (state.current_step) {
      showStep(Math.min(Math.max(state.current_step, 1), 7));
    }
  }

  function buildSummary() {
    if (!summaryEl) return;
    var lines = [];
    var s1 = collectStepData(1);
    if (s1.first_name) lines.push("HR: " + s1.first_name + " " + (s1.last_name || ""));
    var s2 = collectStepData(2);
    if (s2.company_name) lines.push("Company: " + s2.company_name);
    if (lastIntegrations) {
      ["gmail", "google_workspace", "google_calendar"].forEach(function (key) {
        var row = lastIntegrations[key];
        if (!row) return;
        var label =
          key === "gmail" ? "Gmail" : key === "google_workspace" ? "Google Workspace" : "Google Calendar";
        var status = row.status === "connected" ? "Connected" : "Not connected";
        if (row.email && row.status === "connected") status += " (" + row.email + ")";
        lines.push(label + ": " + status);
      });
    }
    summaryEl.innerHTML = lines.map(function (t) { return "<li>" + t + "</li>"; }).join("");
  }

  function saveStep(step) {
    return fetch("/profile/api/step/" + step + "/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
        Accept: "application/json",
      },
      body: JSON.stringify(collectStepData(step)),
    }).then(function (res) {
      return res
        .json()
        .then(function (data) {
          return { ok: res.ok, status: res.status, data: data };
        })
        .catch(function () {
          return { ok: false, status: res.status, data: { errors: { _: ["Unexpected server response."] } } };
        });
    });
  }

  function loadState() {
    return fetch("/profile/api/state/", { headers: { Accept: "application/json" } })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.ok) fillFromState(data);
        return data;
      })
      .catch(function () { return null; });
  }

  function openWizard(step) {
    backdrop.classList.remove("d-none");
    backdrop.setAttribute("aria-hidden", "false");
    requestAnimationFrame(function () {
      backdrop.classList.add("is-open");
    });
    document.body.style.overflow = "hidden";
    loadState().then(function () {
      if (step) showStep(step);
    });
  }

  function closeWizard() {
    backdrop.classList.remove("is-open");
    backdrop.setAttribute("aria-hidden", "true");
    window.setTimeout(function () {
      backdrop.classList.add("d-none");
      document.body.style.overflow = "";
    }, 260);
  }

  window.openProfileWizard = openWizard;

  function handleSaveResult(result, exitAfter) {
    if (!result.ok) {
      var errs = (result.data.errors && result.data.errors.__all__) || [];
      if (!errs.length && result.data.errors) {
        Object.keys(result.data.errors).forEach(function (k) {
          var v = result.data.errors[k];
          if (Array.isArray(v)) errs = errs.concat(v);
        });
      }
      showError(errs.join(" ") || "Could not save this step.");
      return;
    }
    fillFromState(result.data);
    if (result.data.profile_complete) {
      closeWizard();
      window.location.reload();
      return;
    }
    if (exitAfter) {
      showSuccess("Progress saved. You can resume setup anytime from the dashboard.");
      window.setTimeout(closeWizard, 900);
      return;
    }
    showSuccess("Step saved.");
  }

  function runSave(exitAfter) {
    clearError();
    if (nextBtn) nextBtn.disabled = true;
    if (saveExitBtn) saveExitBtn.disabled = true;
    saveStep(currentStep)
      .then(function (result) {
        handleSaveResult(result, exitAfter);
      })
      .catch(function () {
        showError("Network error while saving.");
      })
      .finally(function () {
        if (nextBtn) nextBtn.disabled = false;
        if (saveExitBtn) saveExitBtn.disabled = false;
      });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", function () {
      runSave(false);
    });
  }

  if (saveExitBtn) {
    saveExitBtn.addEventListener("click", function () {
      runSave(true);
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", function () {
      closeWizard();
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener("click", function () {
      if (currentStep > 1) showStep(currentStep - 1);
    });
  }

  backdrop.addEventListener("click", function (e) {
    if (e.target === backdrop) closeWizard();
  });

  function clearIntegrationQuery() {
    if (!window.history.replaceState) return;
    var url = new URL(window.location.href);
    url.searchParams.delete("integration");
    url.searchParams.delete("flow");
    window.history.replaceState({}, "", url.pathname + url.search);
  }

  var params = new URLSearchParams(window.location.search);
  var integrationParam = params.get("integration");
  if (integrationParam === "connected") {
    var flowStep =
      params.get("flow") === "google_workspace" ? 4 : params.get("flow") === "google_calendar" ? 5 : 3;
    openWizard(flowStep);
    clearIntegrationQuery();
  } else if (
    integrationParam === "failed" ||
    integrationParam === "denied" ||
    integrationParam === "oauth_not_configured"
  ) {
    openWizard(3);
    window.setTimeout(function () {
      showError(
        integrationParam === "denied"
          ? "Google authorization was cancelled. You can try Connect again when ready."
          : integrationParam === "oauth_not_configured"
            ? "Google OAuth is not configured. Add GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET to .env."
            : "Google connection failed. Check OAuth settings in .env and try again."
      );
    }, 400);
    clearIntegrationQuery();
  }
});
