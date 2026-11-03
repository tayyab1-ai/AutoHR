document.addEventListener("DOMContentLoaded", function () {
  var cfg = window.AUTOHR_AUTH || {};
  var signupForm = document.querySelector("[data-signup-form]");
  var loginForm = document.querySelector("[data-login-form]");
  var backdrop = document.querySelector("[data-otp-backdrop]");
  var otpInput = document.querySelector("#otp_input");
  var otpTimerEl = document.querySelector("[data-otp-timer]");
  var otpEmailDisplay = document.querySelector("[data-otp-email-display]");
  var otpStatus = document.querySelector("[data-otp-status]");
  var resendBtn = document.querySelector("[data-otp-resend]");
  var verifyBtn = document.querySelector("[data-otp-verify]");
  var changeEmailBtn = document.querySelector("[data-otp-change-email]");
  var signupGlobalError = document.querySelector("[data-signup-global-error]");
  var loginError = document.querySelector("[data-login-error]");

  var timerInterval = null;
  var secondsLeft = 0;
  var otpMode = "signup";
  var pendingSignup = { email: "", password: "", confirm_password: "" };
  var otpTitleEl = document.querySelector("[data-otp-title]");
  var verifyBtnLabel = verifyBtn ? verifyBtn.textContent : "";
  var resetForm = document.querySelector("[data-reset-form]");
  var resetError = document.querySelector("[data-reset-error]");
  var forgotToggle = document.querySelector("[data-forgot-toggle]");
  var forgotPanel = document.querySelector("[data-forgot-panel]");

  function getCookie(name) {
    var match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  function csrfToken() {
    var input =
      document.querySelector("[data-login-form] input[name=csrfmiddlewaretoken]") ||
      document.querySelector("[data-signup-form] input[name=csrfmiddlewaretoken]");
    return (input && input.value) || getCookie("csrftoken");
  }

  function showEl(el, text, type) {
    if (!el) return;
    el.textContent = text || "";
    el.classList.remove("d-none", "alert-danger", "alert-success", "alert-warning");
    el.classList.add(type || "alert-danger");
    if (!text) el.classList.add("d-none");
  }

  function validateSignupClient() {
    var email = document.getElementById("su_email").value.trim();
    var password = document.getElementById("su_password").value;
    var confirm = document.getElementById("su_confirm").value;
    var errors = [];
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.push("Enter a valid email address.");
    if (password.length < 8) errors.push("Password must be at least 8 characters.");
    if (!/[A-Za-z]/.test(password)) errors.push("Password must include at least one letter.");
    if (!/\d/.test(password)) errors.push("Password must include at least one number.");
    if (password !== confirm) errors.push("Passwords do not match.");
    return { ok: errors.length === 0, errors: errors, email: email.toLowerCase(), password: password, confirm: confirm };
  }

  function formatTimer(secs) {
    var m = Math.floor(secs / 60);
    var s = secs % 60;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function stopTimer() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = null;
  }

  function startTimer(duration) {
    stopTimer();
    secondsLeft = duration;
    if (otpTimerEl) otpTimerEl.textContent = formatTimer(secondsLeft);
    if (resendBtn) resendBtn.disabled = true;
    timerInterval = setInterval(function () {
      secondsLeft -= 1;
      if (otpTimerEl) otpTimerEl.textContent = formatTimer(Math.max(0, secondsLeft));
      if (secondsLeft <= 0) {
        stopTimer();
        if (resendBtn) resendBtn.disabled = false;
      }
    }, 1000);
  }

  function openOtpModal(email, mode) {
    otpMode = mode || "signup";
    if (otpMode === "reset") {
      pendingSignup.email = email;
      pendingSignup.password = document.getElementById("rp_password").value;
      pendingSignup.confirm_password = document.getElementById("rp_confirm").value;
      if (otpTitleEl) otpTitleEl.textContent = "Confirm password reset";
      if (verifyBtn) verifyBtn.textContent = "Verify & update password";
      if (changeEmailBtn) changeEmailBtn.textContent = "Cancel";
    } else {
      pendingSignup.email = email;
      pendingSignup.password = document.getElementById("su_password").value;
      pendingSignup.confirm_password = document.getElementById("su_confirm").value;
      if (otpTitleEl) otpTitleEl.textContent = "Verify your email";
      if (verifyBtn) verifyBtn.textContent = verifyBtnLabel || "Verify & create account";
      if (changeEmailBtn) changeEmailBtn.textContent = "Change email";
    }
    if (otpEmailDisplay) otpEmailDisplay.textContent = email;
    if (otpInput) otpInput.value = "";
    showEl(otpStatus, "", "alert-danger");
    backdrop.classList.remove("d-none");
    backdrop.setAttribute("aria-hidden", "false");
    startTimer(120);
    if (otpInput) otpInput.focus();
  }

  function closeOtpModal() {
    stopTimer();
    backdrop.classList.add("d-none");
    backdrop.setAttribute("aria-hidden", "true");
  }

  function resetSignupForm() {
    if (signupForm) {
      signupForm.reset();
      signupForm.classList.remove("was-validated");
    }
    closeOtpModal();
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    }).then(function (res) {
      return res
        .json()
        .then(function (data) {
          return { ok: res.ok, status: res.status, data: data };
        })
        .catch(function () {
          return {
            ok: false,
            status: res.status,
            data: { errors: { __all__: ["Server error. Try again or contact support."] } },
          };
        });
    });
  }

  if (signupForm) {
    signupForm.addEventListener("submit", function (e) {
      e.preventDefault();
      showEl(signupGlobalError, "");
      var v = validateSignupClient();
      if (!v.ok) {
        showEl(signupGlobalError, v.errors.join(" "));
        signupForm.classList.add("was-validated");
        return;
      }
      var btn = signupForm.querySelector("[data-signup-submit]");
      if (btn) btn.disabled = true;
      postJson(cfg.sendOtpUrl, {
        email: v.email,
        password: v.password,
        confirm_password: v.confirm,
      })
        .then(function (result) {
          if (!result.ok) {
            var msg = "Could not send verification code.";
            if (result.data.errors) {
              msg = Object.keys(result.data.errors)
                .map(function (k) {
                  return result.data.errors[k].join(" ");
                })
                .join(" ");
            }
            showEl(signupGlobalError, msg);
            return;
          }
          openOtpModal(v.email, "signup");
          startTimer(result.data.expires_in || 120);
        })
        .catch(function () {
          showEl(signupGlobalError, "Network error. Try again.");
        })
        .finally(function () {
          if (btn) btn.disabled = false;
        });
    });
  }

  if (verifyBtn) {
    verifyBtn.addEventListener("click", function () {
      var otp = (otpInput && otpInput.value.trim()) || "";
      if (otp.length !== 6) {
        showEl(otpStatus, "Enter the 6-digit code.", "alert-warning");
        return;
      }
      verifyBtn.disabled = true;
      var verifyUrl = otpMode === "reset" ? cfg.resetVerifyOtpUrl : cfg.verifyOtpUrl;
      postJson(verifyUrl, {
        email: pendingSignup.email,
        otp: otp,
      })
        .then(function (result) {
          if (result.data.lockout) {
            if (otpMode === "reset") {
              showEl(resetError, result.data.message);
              closeOtpModal();
            } else {
              showEl(signupGlobalError, result.data.message);
              resetSignupForm();
            }
            return;
          }
          if (!result.ok) {
            var errMsg = "Verification failed.";
            if (result.data.errors && result.data.errors.otp) errMsg = result.data.errors.otp.join(" ");
            showEl(otpStatus, errMsg, "alert-danger");
            if (result.data.expired) closeOtpModal();
            return;
          }
          closeOtpModal();
          window.location.href =
            result.data.redirect || (otpMode === "reset" ? "/login/?reset=1" : "/login/?registered=1");
        })
        .catch(function () {
          showEl(otpStatus, "Network error. Try again.", "alert-danger");
        })
        .finally(function () {
          verifyBtn.disabled = false;
        });
    });
  }

  if (resendBtn) {
    resendBtn.addEventListener("click", function () {
      if (resendBtn.disabled) return;
      resendBtn.disabled = true;
      var resendUrl = otpMode === "reset" ? cfg.resetResendOtpUrl : cfg.resendOtpUrl;
      postJson(resendUrl, {
        email: pendingSignup.email,
        password: pendingSignup.password,
        confirm_password: pendingSignup.confirm_password,
      })
        .then(function (result) {
          if (!result.ok) {
            showEl(otpStatus, (result.data.errors && result.data.errors.otp && result.data.errors.otp[0]) || "Could not resend.", "alert-danger");
            return;
          }
          showEl(otpStatus, result.data.message, "alert-success");
          startTimer(result.data.expires_in || 120);
        })
        .finally(function () {
          if (secondsLeft > 0) resendBtn.disabled = true;
        });
    });
  }

  if (changeEmailBtn) {
    changeEmailBtn.addEventListener("click", function () {
      closeOtpModal();
    });
  }

  if (forgotToggle && forgotPanel) {
    forgotToggle.addEventListener("click", function () {
      forgotPanel.classList.toggle("d-none");
    });
  }

  if (resetForm) {
    resetForm.addEventListener("submit", function (e) {
      e.preventDefault();
      showEl(resetError, "");
      var email = document.getElementById("rp_email").value.trim().toLowerCase();
      var password = document.getElementById("rp_password").value;
      var confirm = document.getElementById("rp_confirm").value;
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showEl(resetError, "Enter a valid email address.");
        return;
      }
      if (password.length < 8 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
        showEl(resetError, "Password must be 8+ chars with at least one letter and one number.");
        return;
      }
      if (password !== confirm) {
        showEl(resetError, "Passwords do not match.");
        return;
      }
      var btn = resetForm.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
      postJson(cfg.resetSendOtpUrl, {
        email: email,
        password: password,
        confirm_password: confirm,
      })
        .then(function (result) {
          if (!result.ok) {
            var msg = "Could not send reset code.";
            if (result.data.errors) {
              msg = Object.keys(result.data.errors)
                .map(function (k) {
                  return result.data.errors[k].join(" ");
                })
                .join(" ");
            }
            showEl(resetError, msg);
            return;
          }
          openOtpModal(email, "reset");
          startTimer(result.data.expires_in || 120);
        })
        .catch(function () {
          showEl(resetError, "Network error. Try again.");
        })
        .finally(function () {
          if (btn) btn.disabled = false;
        });
    });
  }

  document.querySelectorAll("[data-otp-close]").forEach(function (btn) {
    btn.addEventListener("click", closeOtpModal);
  });

  if (loginForm) {
    loginForm.addEventListener("submit", function (e) {
      e.preventDefault();
      showEl(loginError, "");
      var email = document.getElementById("si_email").value.trim().toLowerCase();
      var password = document.getElementById("si_password").value;
      if (!email || !password) {
        showEl(loginError, "Email and password are required.");
        return;
      }
      var submitBtn = loginForm.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      postJson(cfg.loginUrl, { email: email, password: password })
        .then(function (result) {
          if (!result.ok) {
            var msg = "Invalid email or password.";
            if (result.data.errors && result.data.errors.__all__) msg = result.data.errors.__all__.join(" ");
            showEl(loginError, msg);
            return;
          }
          window.location.href = result.data.redirect || "/dashboard/";
        })
        .catch(function () {
          showEl(loginError, "Network error. Try again.");
        })
        .finally(function () {
          if (submitBtn) submitBtn.disabled = false;
        });
    });
  }
});
