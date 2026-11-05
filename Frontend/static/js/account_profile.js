document.addEventListener("DOMContentLoaded", function () {
  var panel = document.querySelector('[data-panel="account"]');
  if (!panel) return;

  var toast = panel.querySelector("[data-account-toast]");
  var EDITABLE = ["first_name", "last_name", "phone", "job_title", "work_email", "hr_department"];

  function getCsrf() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function showToast(msg, isError) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.remove("d-none", "is-error", "is-success");
    toast.classList.add(isError ? "is-error" : "is-success");
    window.setTimeout(function () {
      toast.classList.add("d-none");
    }, 3200);
  }

  function displayValue(field, profile) {
    var v = profile[field];
    if (v === undefined || v === null || v === "") return "—";
    return v;
  }

  function applyProfile(profile) {
    if (!profile) return;
    panel.querySelectorAll("[data-display]").forEach(function (el) {
      var key = el.getAttribute("data-display");
      el.textContent = displayValue(key, profile);
    });
    panel.querySelectorAll("[data-edit-input]").forEach(function (input) {
      var key = input.getAttribute("data-edit-input");
      var raw = profile[key];
      if (raw === "—" || raw === undefined || raw === null) raw = "";
      input.value = raw;
    });
    var chipName = document.querySelector(".db-user-name");
    if (chipName && profile.full_name) chipName.textContent = profile.full_name;
    var chipRole = document.querySelector(".db-user-role");
    if (chipRole && profile.job_title) chipRole.textContent = profile.job_title;
    var headerName = panel.querySelector("[data-account-header-name]");
    if (headerName) headerName.textContent = profile.full_name;
    var headerSub = panel.querySelector("[data-account-header-sub]");
    if (headerSub) {
      headerSub.textContent =
        (profile.job_title || "HR") +
        " at " +
        (profile.company_name || "—") +
        " · " +
        (profile.city || "—") +
        ", " +
        (profile.country || "Pakistan");
    }
    var avatar = panel.querySelector("[data-account-avatar]");
    if (avatar && profile.initials) avatar.textContent = profile.initials;
    var chipAvatar = document.querySelector(".db-avatar");
    if (chipAvatar && profile.initials) chipAvatar.textContent = profile.initials;
  }

  function closeEdit(field) {
    var row = panel.querySelector('[data-account-row="' + field + '"]');
    if (!row) return;
    row.querySelector("[data-display-wrap]").classList.remove("d-none");
    row.querySelector("[data-edit-wrap]").classList.add("d-none");
  }

  function openEdit(field) {
    var row = panel.querySelector('[data-account-row="' + field + '"]');
    if (!row) return;
    row.querySelector("[data-display-wrap]").classList.add("d-none");
    row.querySelector("[data-edit-wrap]").classList.remove("d-none");
    var input = row.querySelector("[data-edit-input]");
    if (input) input.focus();
  }

  panel.querySelectorAll("[data-edit-trigger]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      openEdit(btn.getAttribute("data-edit-trigger"));
    });
  });

  panel.querySelectorAll("[data-edit-cancel]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      closeEdit(btn.getAttribute("data-edit-cancel"));
    });
  });

  panel.querySelectorAll("[data-edit-save]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var field = btn.getAttribute("data-edit-save");
      if (EDITABLE.indexOf(field) === -1) return;
      var row = panel.querySelector('[data-account-row="' + field + '"]');
      var input = row ? row.querySelector("[data-edit-input]") : null;
      if (!input) return;
      btn.disabled = true;
      fetch("/account/api/update/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrf(),
          Accept: "application/json",
        },
        body: JSON.stringify({ field: field, value: input.value }),
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            var errs = (result.data.errors && result.data.errors.__all__) || ["Could not save."];
            showToast(errs.join(" "), true);
            return;
          }
          applyProfile(result.data.profile);
          closeEdit(field);
          showToast(result.data.message || "Saved successfully.", false);
        })
        .catch(function () {
          showToast("Network error while saving.", true);
        })
        .finally(function () {
          btn.disabled = false;
        });
    });
  });

  fetch("/account/api/profile/", { headers: { Accept: "application/json" } })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      if (data.ok) applyProfile(data.profile);
    })
    .catch(function () {});

  /* ----- Delete account (OTP) ----- */
  var deleteCfg = window.AUTOHR_ACCOUNT || {};
  var deleteBackdrop = document.querySelector("[data-delete-account-backdrop]");
  if (!deleteBackdrop) return;

  var deleteStart = panel.querySelector("[data-delete-account-start]");
  var deleteClose = deleteBackdrop.querySelector("[data-delete-account-close]");
  var deleteCancel = deleteBackdrop.querySelector("[data-delete-account-cancel]");
  var deleteVerify = deleteBackdrop.querySelector("[data-delete-otp-verify]");
  var deleteResend = deleteBackdrop.querySelector("[data-delete-otp-resend]");
  var deleteInput = deleteBackdrop.querySelector("[data-delete-otp-input]");
  var deleteStatus = deleteBackdrop.querySelector("[data-delete-otp-status]");
  var deleteTimerEl = deleteBackdrop.querySelector("[data-delete-otp-timer]");
  var deleteEmailEl = deleteBackdrop.querySelector("[data-delete-email-display]");
  var deleteTimerId = null;
  var deleteSeconds = 0;

  function deleteShowStatus(text, kind) {
    if (!deleteStatus) return;
    deleteStatus.textContent = text || "";
    deleteStatus.classList.remove("d-none", "alert-danger", "alert-success", "alert-warning");
    deleteStatus.classList.add(kind === "success" ? "alert-success" : kind === "warn" ? "alert-warning" : "alert-danger");
    if (!text) deleteStatus.classList.add("d-none");
  }

  function stopDeleteTimer() {
    if (deleteTimerId) clearInterval(deleteTimerId);
    deleteTimerId = null;
  }

  function formatDeleteTimer(secs) {
    var m = Math.floor(secs / 60);
    var s = secs % 60;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function startDeleteTimer(duration) {
    stopDeleteTimer();
    deleteSeconds = duration;
    if (deleteTimerEl) deleteTimerEl.textContent = formatDeleteTimer(deleteSeconds);
    if (deleteResend) deleteResend.disabled = true;
    deleteTimerId = setInterval(function () {
      deleteSeconds -= 1;
      if (deleteTimerEl) deleteTimerEl.textContent = formatDeleteTimer(Math.max(0, deleteSeconds));
      if (deleteSeconds <= 0) {
        stopDeleteTimer();
        if (deleteResend) deleteResend.disabled = false;
      }
    }, 1000);
  }

  function openDeleteModal() {
    deleteBackdrop.classList.remove("d-none");
    deleteBackdrop.setAttribute("aria-hidden", "false");
    deleteShowStatus("", "");
    if (deleteInput) deleteInput.value = "";
  }

  function closeDeleteModal() {
    deleteBackdrop.classList.add("d-none");
    deleteBackdrop.setAttribute("aria-hidden", "true");
    stopDeleteTimer();
  }

  function postDelete(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrf(),
        Accept: "application/json",
      },
      body: body ? JSON.stringify(body) : "{}",
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, data: data };
      });
    });
  }

  if (deleteStart) {
    deleteStart.addEventListener("click", function () {
      if (!window.confirm("Delete your account permanently? This cannot be undone.")) return;
      deleteStart.disabled = true;
      postDelete(deleteCfg.deleteSendOtpUrl)
        .then(function (result) {
          if (!result.ok) {
            var errs = (result.data.errors && (result.data.errors.email || result.data.errors.__all__)) || ["Could not send code."];
            showToast(Array.isArray(errs) ? errs.join(" ") : errs, true);
            return;
          }
          if (deleteEmailEl && result.data.email_masked) {
            deleteEmailEl.textContent = result.data.email_masked;
          }
          openDeleteModal();
          startDeleteTimer(result.data.expires_in || 120);
        })
        .catch(function () {
          showToast("Network error while sending verification code.", true);
        })
        .finally(function () {
          deleteStart.disabled = false;
        });
    });
  }

  if (deleteVerify && deleteInput) {
    deleteVerify.addEventListener("click", function () {
      var otp = deleteInput.value.trim();
      if (otp.length !== 6) {
        deleteShowStatus("Enter the 6-digit code from your email.", "error");
        return;
      }
      deleteVerify.disabled = true;
      postDelete(deleteCfg.deleteVerifyUrl, { otp: otp })
        .then(function (result) {
          if (!result.ok) {
            if (result.data.lockout) {
              deleteShowStatus(result.data.message || "Too many attempts.", "error");
              closeDeleteModal();
              return;
            }
            var msg = (result.data.errors && result.data.errors.otp && result.data.errors.otp[0]) || "Invalid code.";
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
          deleteVerify.disabled = false;
        });
    });
  }

  if (deleteResend) {
    deleteResend.addEventListener("click", function () {
      deleteResend.disabled = true;
      postDelete(deleteCfg.deleteResendOtpUrl)
        .then(function (result) {
          if (!result.ok) {
            deleteShowStatus(
              (result.data.errors && result.data.errors.otp && result.data.errors.otp[0]) || "Could not resend.",
              "error"
            );
            return;
          }
          deleteShowStatus("New code sent.", "success");
          startDeleteTimer(result.data.expires_in || 120);
        })
        .finally(function () {
          if (deleteSeconds <= 0 && deleteResend) deleteResend.disabled = false;
        });
    });
  }

  [deleteClose, deleteCancel].forEach(function (btn) {
    if (!btn) return;
    btn.addEventListener("click", closeDeleteModal);
  });
});
