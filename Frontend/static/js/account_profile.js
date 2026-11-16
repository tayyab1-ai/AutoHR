document.addEventListener("DOMContentLoaded", function () {
  var panel = document.querySelector('[data-panel="account"]');
  if (!panel) return;

  function getCsrf() {
    var match = document.cookie.match(/(^| )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[2]) : "";
  }

  function showToast(message, isError) {
    window.dispatchEvent(
      new CustomEvent("autohr-toast", { detail: { message: message, error: !!isError } })
    );
  }

  /* Render "autohr-toast" events into the account panel's toast element (auto-hides). */
  var toastEl = panel.querySelector("[data-account-toast]");
  var toastTimer = null;
  window.addEventListener("autohr-toast", function (event) {
    if (!toastEl) return;
    var detail = (event && event.detail) || {};
    if (!detail.message) return;
    var isError = !!detail.error;
    toastEl.textContent = String(detail.message);
    toastEl.setAttribute("role", isError ? "alert" : "status");
    toastEl.classList.remove("d-none", "is-success", "is-error");
    toastEl.classList.add(isError ? "is-error" : "is-success");
    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toastEl.classList.add("d-none");
      toastTimer = null;
    }, isError ? 8000 : 4000);
  });

  function applyProfile(profile) {
    if (!profile) return;
    Object.keys(profile).forEach(function (key) {
      panel.querySelectorAll('[data-display="' + key + '"]').forEach(function (el) {
        el.textContent = profile[key] != null ? profile[key] : "—";
      });
    });
  }

  panel.querySelectorAll("[data-edit-trigger]").forEach(function (btn) {
    var field = btn.getAttribute("data-edit-trigger");
    var row = btn.closest("[data-account-row]");
    if (!row) return;
    var displayWrap = row.querySelector("[data-display-wrap]");
    var editWrap = row.querySelector("[data-edit-wrap]");
    function openEdit() {
      displayWrap.classList.add("d-none");
      editWrap.classList.remove("d-none");
    }
    function closeEdit() {
      editWrap.classList.add("d-none");
      displayWrap.classList.remove("d-none");
    }
    btn.addEventListener("click", openEdit);
    var cancel = row.querySelector('[data-edit-cancel="' + field + '"]');
    if (cancel) cancel.addEventListener("click", closeEdit);
    var save = row.querySelector('[data-edit-save="' + field + '"]');
    if (save) {
      save.addEventListener("click", function () {
        var input = row.querySelector('[data-edit-input="' + field + '"]');
        var value = input ? input.value : "";
        save.disabled = true;
        fetch("/account/api/update/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
            Accept: "application/json",
          },
          body: JSON.stringify({ field: field, value: value }),
        })
          .then(function (res) {
            return res.json().then(function (data) {
              return { ok: res.ok, data: data };
            });
          })
          .then(function (result) {
            if (!result.ok) {
              var errs = (result.data.errors && result.data.errors.__all__) || ["Could not save."];
              showToast(Array.isArray(errs) ? errs.join(" ") : errs, true);
              return;
            }
            applyProfile(result.data.profile);
            closeEdit();
            showToast(result.data.message || "Saved successfully.", false);
          })
          .catch(function () {
            showToast("Network error while saving.", true);
          })
          .finally(function () {
            save.disabled = false;
          });
      });
    }
  });

  fetch("/account/api/profile/", { headers: { Accept: "application/json" } })
    .then(function (res) {
      return res.json();
    })
    .then(function (data) {
      if (data.ok) applyProfile(data.profile);
    })
    .catch(function () {});

  var accountCfg = window.AUTOHR_ACCOUNT || {};
  var sessionsList = panel.querySelector("[data-sessions-list]");
  var revokeOthersBtn = panel.querySelector("[data-revoke-other-sessions]");

  function renderSessions(sessions) {
    if (!sessionsList) return;
    sessionsList.innerHTML = "";
    if (!sessions || !sessions.length) {
      sessionsList.innerHTML = "<li class=\"text-muted\">No active sessions.</li>";
      return;
    }
    sessions.forEach(function (s) {
      var li = document.createElement("li");
      li.className = "mb-2 pb-2 border-bottom border-light";
      var label = (s.current ? "This device · " : "") + (s.device_label || "Device");
      var seen = s.last_seen_at ? new Date(s.last_seen_at).toLocaleString() : "";
      li.innerHTML =
        '<div class="d-flex justify-content-between align-items-start gap-2">' +
        "<span><strong>" +
        label +
        "</strong><br><span class=\"text-muted\">Last active " +
        seen +
        (s.ip_address && s.ip_address !== "—" ? " · " + s.ip_address : "") +
        "</span></span>" +
        (s.current
          ? ""
          : '<button type="button" class="btn btn-link btn-sm p-0" data-revoke-session="' +
            s.id +
            '">Sign out</button>') +
        "</div>";
      sessionsList.appendChild(li);
    });
    sessionsList.querySelectorAll("[data-revoke-session]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var sid = btn.getAttribute("data-revoke-session");
        fetch(accountCfg.revokeSessionUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
            Accept: "application/json",
          },
          body: JSON.stringify({ session_id: sid }),
        })
          .then(function (res) {
            return res.json();
          })
          .then(function (data) {
            if (data.ok) renderSessions(data.sessions);
            else showToast("Could not revoke session.", true);
          });
      });
    });
  }

  function loadSessions() {
    if (!accountCfg.sessionsUrl) return;
    fetch(accountCfg.sessionsUrl, { headers: { Accept: "application/json" } })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (data.ok) renderSessions(data.sessions);
      })
      .catch(function () {});
  }

  loadSessions();

  var intCard = panel.querySelector("[data-integrations-card]");
  var intStatus = panel.querySelector("[data-int-status-label]");
  var intCalStatus = panel.querySelector("[data-int-cal-status-label]");
  var intDisconnect = panel.querySelector("[data-int-disconnect]");
  var intGmailStatus = panel.querySelector("[data-int-gmail-status-label]");
  var intGmailConnect = panel.querySelector("[data-int-gmail-connect]");
  var intGmailDisconnect = panel.querySelector("[data-int-gmail-disconnect]");

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function renderIntegrations(integrations) {
    if (!integrations) return;
    var ws = integrations.google_workspace || {};
    if (intStatus) {
      if (ws.status === "connected") {
        intStatus.innerHTML =
          "Connected" +
          (ws.email ? " as <strong>" + ws.email + "</strong>" : "") +
          (ws.token_usable ? " · token active" : " · <span class=\"text-danger\">token needs reconnect</span>");
      } else {
        intStatus.textContent = "Not connected — required for Google application forms.";
      }
    }
    if (intDisconnect) {
      intDisconnect.classList.toggle("d-none", ws.status !== "connected");
    }
    var gm = integrations.gmail || {};
    if (intGmailStatus) {
      if (gm.status === "connected") {
        intGmailStatus.innerHTML =
          "Connected" +
          (gm.email ? " as <strong>" + escapeHtml(gm.email) + "</strong>" : "") +
          (gm.token_usable
            ? " · invitations are emailed from this address"
            : " · <span class=\"text-danger\">token needs reconnect</span>");
      } else {
        intGmailStatus.textContent = "Not connected — required to email interview invitations to candidates.";
      }
    }
    if (intGmailConnect) {
      intGmailConnect.textContent = gm.status === "connected" ? "Reconnect" : "Connect Gmail";
    }
    if (intGmailDisconnect) {
      intGmailDisconnect.classList.toggle("d-none", gm.status !== "connected");
    }
    var cal = integrations.google_calendar || {};
    if (intCalStatus) {
      intCalStatus.textContent =
        cal.status === "connected"
          ? "Connected" + (cal.email ? " (" + cal.email + ")" : "")
          : "Optional — connect for interview scheduling.";
    }
  }

  function loadIntegrations() {
    if (!accountCfg.integrationsUrl) return;
    fetch(accountCfg.integrationsUrl, { headers: { Accept: "application/json" } })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (data.ok) renderIntegrations(data.integrations);
      })
      .catch(function () {
        if (intStatus) intStatus.textContent = "Could not load integration status.";
      });
  }

  loadIntegrations();

  if (intDisconnect) {
    intDisconnect.addEventListener("click", function () {
      if (!window.confirm("Disconnect Google Workspace? Form creation will stop until you reconnect.")) return;
      fetch(accountCfg.disconnectIntegrationUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrf(),
          Accept: "application/json",
        },
        body: JSON.stringify({ provider: "google_workspace" }),
      })
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (data.ok) {
            renderIntegrations(data.integrations);
            showToast(data.message || "Disconnected.", false);
          } else showToast("Could not disconnect.", true);
        });
    });
  }

  if (intGmailDisconnect) {
    intGmailDisconnect.addEventListener("click", function () {
      if (!window.confirm("Disconnect Gmail? Interview invitations will no longer be emailed automatically.")) return;
      fetch(accountCfg.disconnectIntegrationUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrf(),
          Accept: "application/json",
        },
        body: JSON.stringify({ provider: "gmail" }),
      })
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (data.ok) {
            renderIntegrations(data.integrations);
            showToast("Gmail disconnected.", false);
          } else showToast("Could not disconnect Gmail.", true);
        })
        .catch(function () {
          showToast("Network error while disconnecting Gmail.", true);
        });
    });
  }

  window.refreshAccountIntegrations = loadIntegrations;

  if (revokeOthersBtn) {
    revokeOthersBtn.addEventListener("click", function () {
      revokeOthersBtn.disabled = true;
      fetch(accountCfg.revokeOthersUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrf(),
          Accept: "application/json",
        },
        body: "{}",
      })
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (data.ok) {
            renderSessions(data.sessions);
            showToast(data.message || "Other devices signed out.", false);
          }
        })
        .finally(function () {
          revokeOthersBtn.disabled = false;
        });
    });
  }

  var deleteBackdrop = document.querySelector("[data-delete-account-backdrop]");
  if (!deleteBackdrop) return;

  var deleteStart = panel.querySelector("[data-delete-account-start]");
  var deleteClose = deleteBackdrop.querySelector("[data-delete-account-close]");
  var deleteCancel = deleteBackdrop.querySelector("[data-delete-account-cancel]");
  var deleteConfirm = deleteBackdrop.querySelector("[data-delete-confirm]");
  var deletePhrase = deleteBackdrop.querySelector("[data-delete-confirmation]");
  var deleteEmail = deleteBackdrop.querySelector("[data-delete-email-input]");
  var deleteStatus = deleteBackdrop.querySelector("[data-delete-status]");

  function deleteShowStatus(text, kind) {
    if (!deleteStatus) return;
    deleteStatus.textContent = text || "";
    deleteStatus.classList.remove("d-none", "alert-danger", "alert-success", "alert-warning");
    deleteStatus.classList.add(kind === "success" ? "alert-success" : "alert-danger");
    if (!text) deleteStatus.classList.add("d-none");
  }

  function openDeleteModal() {
    deleteBackdrop.classList.remove("d-none");
    deleteBackdrop.setAttribute("aria-hidden", "false");
    deleteShowStatus("", "");
    if (deletePhrase) deletePhrase.value = "";
  }

  function closeDeleteModal() {
    deleteBackdrop.classList.add("d-none");
    deleteBackdrop.setAttribute("aria-hidden", "true");
  }

  if (deleteStart) {
    deleteStart.addEventListener("click", function () {
      if (!window.confirm("Delete your account permanently? This cannot be undone.")) return;
      openDeleteModal();
    });
  }

  if (deleteClose) deleteClose.addEventListener("click", closeDeleteModal);
  if (deleteCancel) deleteCancel.addEventListener("click", closeDeleteModal);

  if (deleteConfirm) {
    deleteConfirm.addEventListener("click", function () {
      var confirmation = deletePhrase ? deletePhrase.value.trim() : "";
      var email = deleteEmail ? deleteEmail.value.trim() : "";
      deleteConfirm.disabled = true;
      fetch(accountCfg.deleteConfirmUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrf(),
          Accept: "application/json",
        },
        body: JSON.stringify({ confirmation: confirmation, email: email }),
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            var msg =
              (result.data.errors &&
                ((result.data.errors.confirmation && result.data.errors.confirmation[0]) ||
                  (result.data.errors.email && result.data.errors.email[0]))) ||
              "Could not delete account.";
            deleteShowStatus(msg, "error");
            return;
          }
          deleteShowStatus(result.data.message || "Account deleted.", "success");
          window.setTimeout(function () {
            window.location.href = result.data.redirect || "/";
          }, 800);
        })
        .catch(function () {
          deleteShowStatus("Network error. Try again.", "error");
        })
        .finally(function () {
          deleteConfirm.disabled = false;
        });
    });
  }
});
