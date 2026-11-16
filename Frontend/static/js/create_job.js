document.addEventListener("DOMContentLoaded", function () {
  var TECH_CATEGORIES = ["software_development", "data_science", "ai_ml", "cybersecurity"];

  var form = document.querySelector("[data-create-job-form]");
  if (!form) return;

  var generateBtn = document.querySelector("[data-generate-jd]");
  var errorBox = document.querySelector("[data-create-job-errors]");
  var formBox = document.querySelector("[data-create-job-fields]");
  var jdStep = document.querySelector("[data-create-job-jd-step]");
  var applicationFormStep = document.querySelector("[data-create-job-form-step]");
  var stepper = document.querySelector("[data-create-job-stepper]");

  var jdLoading = document.querySelector("[data-jd-loading]");
  var jdEditor = document.querySelector("[data-jd-editor]");
  var jdComplete = document.querySelector("[data-jd-complete]");
  var jdErrors = document.querySelector("[data-jd-errors]");
  var jdPreview = document.querySelector("[data-jd-preview]");
  var jdTextarea = document.querySelector("[data-jd-textarea]");
  var jdTitle = document.querySelector("[data-jd-step-title]");
  var toggleEditBtn = document.querySelector("[data-jd-toggle-edit]");
  var previewModeBtn = document.querySelector("[data-jd-preview-mode]");
  var postGoogleBtn = document.querySelector("[data-post-google-form]");
  var jdRetryWrap = document.querySelector("[data-jd-retry-wrap]");
  var jdRetryBtn = document.querySelector("[data-jd-retry]");

  var currentJobId = null;
  var aiDraftSnapshot = "";
  var jobUrlPlaceholder =
    form.getAttribute("data-job-url-id-placeholder") || "00000000-0000-0000-0000-000000000001";

  function jobApiUrl(kind, jobId) {
    var attrMap = {
      prepare: "data-job-url-prepare-form",
      "save-draft": "data-job-url-save-draft-jd",
      generate: "data-job-url-generate",
      "form-config": "data-job-url-form-config",
      "form-save": "data-job-url-form-save",
      "create-form": "data-job-url-create-form",
      "confirm-form": "data-job-url-confirm-form",
    };
    var attr = attrMap[kind] || "data-job-url-generate";
    var template = form.getAttribute(attr);
    if (!template) {
      var suffixMap = {
        prepare: "/prepare-google-form/",
        "save-draft": "/save-draft-jd/",
        generate: "/generate-jd/",
        "form-config": "/form-config/",
        "form-save": "/form-config/save/",
        "create-form": "/create-google-form/",
        "confirm-form": "/confirm-google-form/",
      };
      var suffix = suffixMap[kind] || "/generate-jd/";
      return "/dashboard/jobs/" + jobId + suffix;
    }
    return template.split(jobUrlPlaceholder).join(jobId);
  }

  function isProfileComplete() {
    return form.getAttribute("data-profile-complete") === "1";
  }

  function currentJdText() {
    return (jdTextarea && jdTextarea.value ? jdTextarea.value : aiDraftSnapshot).trim();
  }

  function postJdForm(jobId, kind) {
    var body = new FormData();
    body.append("finalized_jd", currentJdText());
    return fetch(jobApiUrl(kind, jobId), {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        Accept: "application/json",
      },
      body: body,
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  var profileGateModal = document.querySelector("[data-profile-gate-modal]");
  var profileGateComplete = document.querySelector("[data-profile-gate-complete]");
  var profileGateExit = document.querySelector("[data-profile-gate-exit]");

  function openProfileGateModal() {
    if (!profileGateModal) return;
    profileGateModal.classList.remove("d-none");
    profileGateModal.setAttribute("aria-hidden", "false");
  }

  function closeProfileGateModal() {
    if (!profileGateModal) return;
    profileGateModal.classList.add("d-none");
    profileGateModal.setAttribute("aria-hidden", "true");
  }

  if (profileGateComplete) {
    profileGateComplete.addEventListener("click", function () {
      closeProfileGateModal();
      if (typeof window.openProfileWizard === "function") {
        window.openProfileWizard();
      }
    });
  }

  if (profileGateExit) {
    profileGateExit.addEventListener("click", function () {
      closeProfileGateModal();
      var jobsNav = document.querySelector('[data-panel-target="jobs"]');
      if (jobsNav) jobsNav.click();
    });
  }

  function getCsrfToken() {
    var input = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function handleAuthFailure(result) {
    if (result && result.status === 401 && result.data && result.data.redirect) {
      window.location.href = result.data.redirect;
      return true;
    }
    return false;
  }

  function setStepperActive(step) {
    if (!stepper) return;
    stepper.querySelectorAll("[data-step-indicator]").forEach(function (el) {
      var n = el.getAttribute("data-step-indicator");
      el.classList.toggle("is-active", String(step) === n);
      el.classList.toggle("is-done", Number(n) < Number(step));
    });
  }

  function wireChipInput(inputId, listId, hiddenName) {
    var input = document.getElementById(inputId);
    var list = document.getElementById(listId);
    var hidden = form.querySelector('[name="' + hiddenName + '"]');
    if (!input || !list || !hidden) return;
    var items = [];

    function render() {
      list.innerHTML = "";
      items.forEach(function (value, index) {
        var chip = document.createElement("span");
        chip.className = "db-skill-chip";
        chip.innerHTML = "<span></span><button type=\"button\" aria-label=\"Remove\">&times;</button>";
        chip.querySelector("span").textContent = value;
        chip.querySelector("button").addEventListener("click", function () {
          items.splice(index, 1);
          render();
          syncPreview();
        });
        list.appendChild(chip);
      });
      hidden.value = items.join(", ");
    }

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === ",") {
        event.preventDefault();
        var value = input.value.trim().replace(/,$/, "");
        if (value && items.indexOf(value) === -1) {
          items.push(value);
          render();
          syncPreview();
        }
        input.value = "";
      }
    });
  }

  wireChipInput("required-skill-input", "required-skill-list", "required_skills_csv");
  wireChipInput("programming-skill-input", "programming-skill-list", "programming_languages_csv");
  wireChipInput("framework-skill-input", "framework-skill-list", "frameworks_csv");
  wireChipInput("tools-skill-input", "tools-skill-list", "tools_csv");
  wireChipInput("cloud-skill-input", "cloud-skill-list", "cloud_platforms_csv");

  function addRepeatRow(name, value) {
    var list = form.querySelector('[data-repeat-list="' + name + '"]');
    if (!list) return;
    var row = document.createElement("div");
    row.className = "db-repeat-row d-flex gap-2 mb-2";
    row.innerHTML =
      '<input type="text" class="db-input flex-grow-1" name="' +
      name +
      '" style="width:100%;" placeholder="Enter text" value="' +
      (value || "").replace(/"/g, "&quot;") +
      '">' +
      '<button type="button" class="btn-db-secondary btn-sm" data-remove-repeat aria-label="Remove">&times;</button>';
    row.querySelector("[data-remove-repeat]").addEventListener("click", function () {
      row.remove();
      if (!list.querySelector('input[name="' + name + '"]')) {
        addRepeatRow(name, "");
      }
    });
    list.appendChild(row);
  }

  form.querySelectorAll("[data-add-repeat]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      addRepeatRow(btn.getAttribute("data-add-repeat"), "");
    });
  });

  addRepeatRow("key_responsibilities", "");
  addRepeatRow("daily_tasks", "");

  function selectedText(selectEl) {
    if (!selectEl || !selectEl.options.length) return "—";
    var opt = selectEl.options[selectEl.selectedIndex];
    return opt && opt.value ? opt.textContent : "—";
  }

  function toggleConditionals() {
    var category = form.querySelector('[name="job_category"]');
    var catVal = category ? category.value : "";
    var progPanel = form.querySelector('[data-conditional="programming_languages"]');
    if (progPanel) {
      progPanel.classList.toggle("d-none", TECH_CATEGORIES.indexOf(catVal) === -1);
    }
    var tone = form.querySelector('[name="job_post_tone"]');
    var toneVal = tone ? tone.value : "";
    var customPanel = form.querySelector('[data-conditional="custom_tone"]');
    if (customPanel) {
      customPanel.classList.toggle("d-none", toneVal !== "custom");
    }
  }

  function formatSalary() {
    var min = form.querySelector('[name="min_salary"]');
    var max = form.querySelector('[name="max_salary"]');
    var period = form.querySelector('[name="salary_period"]');
    var minV = min && min.value ? Number(min.value) : null;
    var maxV = max && max.value ? Number(max.value) : null;
    if (minV === null && maxV === null) return "Not disclosed";
    var label = selectedText(period).toLowerCase();
    var lo = minV !== null ? "PKR " + minV.toLocaleString("en-PK") : null;
    var hi = maxV !== null ? maxV.toLocaleString("en-PK") : null;
    if (lo && hi) return lo + " – " + hi + " / " + label;
    if (lo) return lo + "+ / " + label;
    return "Up to PKR " + hi + " / " + label;
  }

  function syncPreview() {
    var title = form.querySelector('[name="title"]');
    var pt = document.querySelector("[data-preview-title]");
    if (pt) pt.textContent = (title && title.value.trim()) || "Untitled role";

    var set = function (sel, val) {
      var el = document.querySelector(sel);
      if (el) el.textContent = val || "—";
    };

    set("[data-preview-company]", form.querySelector('[name="company_name"]')?.value);
    set("[data-preview-department]", selectedText(form.querySelector('[name="department"]')));
    set("[data-preview-category]", selectedText(form.querySelector('[name="job_category"]')));
    set("[data-preview-employment]", selectedText(form.querySelector('[name="employment_type"]')));
    set("[data-preview-workmode]", selectedText(form.querySelector('[name="work_mode"]')));
    set("[data-preview-urgency]", selectedText(form.querySelector('[name="urgency_level"]')));
    set("[data-preview-city]", selectedText(form.querySelector('[name="city"]')));
    set("[data-preview-hires]", form.querySelector('[name="target_hires"]')?.value);

    var deadline = form.querySelector('[name="application_deadline"]');
    set("[data-preview-deadline]", deadline && deadline.value ? deadline.value : "—");

    var minExp = form.querySelector('[name="min_experience_years"]')?.value;
    var maxExp = form.querySelector('[name="max_experience_years"]')?.value;
    var expText = "—";
    if (minExp !== undefined && minExp !== "") {
      expText = minExp + (maxExp ? " – " + maxExp : "+") + " years";
    }
    set("[data-preview-exp]", expText);

    var fresh = form.querySelector('[name="fresh_graduate_eligible"]:checked');
    set("[data-preview-fresh]", fresh ? (fresh.value === "yes" ? "Yes" : "No") : "—");
    set("[data-preview-education]", selectedText(form.querySelector('[name="min_education_level"]')));
    set("[data-preview-salary]", formatSalary());

    var skillsHidden = form.querySelector('[name="required_skills_csv"]');
    set("[data-preview-skills]", skillsHidden && skillsHidden.value ? skillsHidden.value.replace(/,/g, ", ") : "—");
    set("[data-preview-tone]", selectedText(form.querySelector('[name="job_post_tone"]')));
    var wSkill = Number(form.querySelector('[name="cv_skill_weight"]')?.value || 50);
    var wExp = Number(form.querySelector('[name="cv_experience_weight"]')?.value || 30);
    var wEdu = Number(form.querySelector('[name="cv_education_weight"]')?.value || 20);
    var minPass = form.querySelector('[name="cv_min_passing_score"]')?.value || "60";
    set("[data-preview-cv-weights]", wSkill + "% / " + wExp + "% / " + wEdu + "%");
    set("[data-preview-cv-cutoff]", minPass + "%");
    var weightBadge = document.querySelector("[data-cv-weight-total]");
    if (weightBadge) {
      var sum = wSkill + wExp + wEdu;
      weightBadge.textContent = "Total: " + sum + "%";
      weightBadge.classList.toggle("db-badge-live", sum === 100);
      weightBadge.classList.toggle("db-badge-rejected", sum !== 100);
    }
    set("[data-preview-shortlist-cv]", form.querySelector('[name="shortlist_after_cv_count"]')?.value || "25");
    set("[data-preview-shortlist-iv]", form.querySelector('[name="shortlist_after_interview_count"]')?.value || "10");
  }

  form.querySelectorAll("[data-cv-preset]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var parts = (btn.getAttribute("data-cv-preset") || "").split(",");
      if (parts.length < 4) return;
      var setVal = function (name, val) {
        var el = form.querySelector('[name="' + name + '"]');
        if (el) el.value = val;
      };
      setVal("cv_skill_weight", parts[0]);
      setVal("cv_experience_weight", parts[1]);
      setVal("cv_education_weight", parts[2]);
      setVal("cv_min_passing_score", parts[3]);
      syncPreview();
    });
  });

  form.addEventListener("input", syncPreview);
  form.addEventListener("change", function () {
    toggleConditionals();
    syncPreview();
  });
  toggleConditionals();
  syncPreview();

  /* Flatten an error value (string | list | {field: string|list}) into strings. */
  function flattenErrors(value, out) {
    out = out || [];
    if (value == null) return out;
    if (typeof value === "string") {
      if (value.trim()) out.push(value);
    } else if (Array.isArray(value)) {
      value.forEach(function (v) { flattenErrors(v, out); });
    } else if (typeof value === "object") {
      if (typeof value.message === "string" && value.message.trim()) {
        out.push(value.message);
      } else {
        Object.keys(value).forEach(function (k) { flattenErrors(value[k], out); });
      }
    }
    return out;
  }

  /* Messages from a payload's error keys (array/object values, plus a top-level `error` string). */
  function payloadErrorLines(payload) {
    var lines = [];
    if (payload && typeof payload === "object") {
      Object.keys(payload).forEach(function (key) {
        var msgs = payload[key];
        if (Array.isArray(msgs) || (msgs && typeof msgs === "object")) {
          flattenErrors(msgs, lines);
        } else if ((key === "error" || key === "errors") && typeof msgs === "string") {
          lines.push(msgs);
        }
      });
    }
    return lines;
  }

  /* First readable error from data.errors (preferred keys first, then any key), then data.error. */
  function firstErrorMessage(data, fallback) {
    data = data || {};
    var errors = data.errors;
    if (errors) {
      if (typeof errors === "string" || Array.isArray(errors)) {
        var direct = flattenErrors(errors);
        if (direct.length) return direct[0];
      } else if (typeof errors === "object") {
        var preferred = ["google", "__all__", "form_url", "job", "fields"];
        var keys = preferred.filter(function (k) { return k in errors; }).concat(
          Object.keys(errors).filter(function (k) { return preferred.indexOf(k) === -1; })
        );
        for (var i = 0; i < keys.length; i++) {
          var msgs = flattenErrors(errors[keys[i]]);
          if (msgs.length) return msgs[0];
        }
      }
    }
    if (typeof data.error === "string" && data.error.trim()) return data.error;
    return fallback;
  }

  function showFormErrors(payload) {
    if (!errorBox) return;
    var lines = payloadErrorLines(payload);
    if (!lines.length) lines.push("Could not save the job. Check required fields.");
    errorBox.textContent = lines.join(" ");
    errorBox.classList.remove("d-none");
    formBox?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function showJdErrors(payload) {
    if (!jdErrors) return;
    var lines = payloadErrorLines(payload);
    if (!lines.length) lines.push("Something went wrong while generating the description.");
    jdErrors.textContent = lines.join(" ");
    jdErrors.classList.remove("d-none");
  }

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function formatInline(text) {
    var safe = escapeHtml(text);
    safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    safe = safe.replace(/__(.+?)__/g, "<strong>$1</strong>");
    safe = safe.replace(/\*(.+?)\*/g, "<em>$1</em>");
    return safe;
  }

  function isSectionTitle(line) {
    if (line.length > 90 || line.indexOf(".") !== -1 && !/^(How to Apply|Equal Opportunity)/i.test(line)) {
      return false;
    }
    if (/^Apply Here:/i.test(line)) return false;
    if (/^[•\-\*]/.test(line)) return false;
    if (/^\d+\./.test(line)) return false;
    return /^[A-Z]/.test(line) && !line.endsWith(".");
  }

  function renderFormattedJd(text) {
    if (!jdPreview) return;
    var lines = (text || "").split("\n");
    var html = [];
    var inList = false;

    function closeList() {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
    }

    lines.forEach(function (raw) {
      var line = raw.replace(/\r$/, "");
      var trimmed = line.trim();
      if (!trimmed) {
        closeList();
        return;
      }

      var hashMatch = trimmed.match(/^#{1,4}\s+(.+)$/);
      if (hashMatch) {
        closeList();
        html.push("<h4 class=\"db-jd-heading\">" + formatInline(hashMatch[1]) + "</h4>");
        return;
      }

      if (/^Apply Here:/i.test(trimmed)) {
        closeList();
        var after = trimmed.replace(/^Apply Here:\s*/i, "");
        html.push(
          "<p class=\"db-jd-apply\"><strong>Apply Here:</strong> " +
            '<span class="db-jd-apply-blank">' +
            (after ? formatInline(after) : "&nbsp;") +
            "</span></p>"
        );
        return;
      }

      if (/^[•\-\*]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
        if (!inList) {
          html.push("<ul class=\"db-jd-list\">");
          inList = true;
        }
        var item = trimmed.replace(/^[•\-\*]\s+/, "").replace(/^\d+\.\s+/, "");
        html.push("<li>" + formatInline(item) + "</li>");
        return;
      }

      if (isSectionTitle(trimmed)) {
        closeList();
        html.push("<h4 class=\"db-jd-heading\">" + formatInline(trimmed) + "</h4>");
        return;
      }

      closeList();
      html.push("<p>" + formatInline(trimmed) + "</p>");
    });

    closeList();
    jdPreview.innerHTML = html.join("");
  }

  function showJdEditor(text, title) {
    aiDraftSnapshot = text;
    if (jdRetryWrap) jdRetryWrap.classList.add("d-none");
    if (jdTitle && title) jdTitle.textContent = "AI Job Description — " + title;
    if (jdTextarea) jdTextarea.value = text;
    renderFormattedJd(text);
    if (jdLoading) jdLoading.classList.add("d-none");
    if (jdEditor) jdEditor.classList.remove("d-none");
    if (jdPreview) {
      jdPreview.classList.remove("d-none");
      jdPreview.style.display = "block";
    }
    if (jdTextarea) {
      jdTextarea.classList.add("d-none");
      jdTextarea.style.display = "none";
    }
    if (toggleEditBtn) toggleEditBtn.classList.remove("d-none");
    if (previewModeBtn) previewModeBtn.classList.add("d-none");
  }

  function openJdStep(title, showLoading) {
    setStepperActive(2);
    if (formBox) formBox.classList.add("d-none");
    if (jdStep) jdStep.classList.remove("d-none");
    if (jdLoading) jdLoading.classList.toggle("d-none", !showLoading);
    if (jdEditor) jdEditor.classList.add("d-none");
    if (jdComplete) jdComplete.classList.add("d-none");
    if (jdRetryWrap) jdRetryWrap.classList.add("d-none");
    if (jdErrors) jdErrors.classList.add("d-none");
    if (jdTitle) jdTitle.textContent = title ? "AI Job Description — " + title : "AI Job Description";
    jdStep.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function showJdRetry() {
    if (jdLoading) jdLoading.classList.add("d-none");
    if (jdEditor) jdEditor.classList.add("d-none");
    if (jdRetryWrap) jdRetryWrap.classList.remove("d-none");
  }

  function handleGenerateResponse(data, title) {
    var jdText = (data.ai_generated_jd || "").trim();
    if (data.ai_ok && jdText.length > 0) {
      showJdEditor(jdText, title || data.title);
      return;
    }
    if (data.errors) {
      showJdErrors(data.errors);
    } else if (!data.ai_ok) {
      showJdErrors({ ai: ["AI did not return a job description. Try Retry."] });
    }
    showJdRetry();
  }

  function runGenerateJd(jobId, title) {
    if (jdRetryWrap) jdRetryWrap.classList.add("d-none");
    if (jdErrors) jdErrors.classList.add("d-none");
    if (jdLoading) jdLoading.classList.remove("d-none");
    if (jdEditor) jdEditor.classList.add("d-none");

    return fetchGenerateJd(jobId)
      .then(function (genResult) {
        if (handleAuthFailure(genResult)) return;
        if (!genResult.ok) {
          showJdErrors(genResult.data.errors || genResult.data);
          showJdRetry();
          return;
        }
        showJdEditor(genResult.data.ai_generated_jd || "", title || genResult.data.title);
      })
      .catch(function () {
        showJdErrors({ ai: ["Network error while generating the description."] });
        showJdRetry();
      })
      .finally(function () {
        if (jdLoading) jdLoading.classList.add("d-none");
      });
  }

  function fetchGenerateJd(jobId) {
    return fetch(jobApiUrl("generate", jobId), {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        Accept: "application/json",
      },
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function submitJob() {
    if (errorBox) errorBox.classList.add("d-none");
    if (generateBtn) {
      generateBtn.disabled = true;
      generateBtn.classList.add("is-loading");
      generateBtn.dataset.loadingLabel = generateBtn.innerHTML;
      generateBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Validating &amp; generating…';
    }

    fetch(form.action, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        Accept: "application/json",
      },
      body: new FormData(form),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, status: res.status, data: data };
        });
      })
      .then(function (result) {
        if (handleAuthFailure(result)) return;
        if (!result.ok) {
          showFormErrors(result.data.errors || result.data);
          return;
        }
        currentJobId = result.data.job_id;
        openJdStep(result.data.title, !result.data.ai_ok);
        handleGenerateResponse(result.data, result.data.title);
      })
      .catch(function () {
        showFormErrors({ _: ["Network error while saving the job."] });
      })
      .finally(function () {
        if (generateBtn) {
          generateBtn.disabled = false;
          generateBtn.classList.remove("is-loading");
          if (generateBtn.dataset.loadingLabel) {
            generateBtn.innerHTML = generateBtn.dataset.loadingLabel;
          }
        }
      });
  }

  if (toggleEditBtn && jdTextarea && jdPreview) {
    toggleEditBtn.addEventListener("click", function () {
      jdPreview.style.display = "none";
      jdTextarea.classList.remove("d-none");
      jdTextarea.style.display = "block";
      toggleEditBtn.classList.add("d-none");
      if (previewModeBtn) previewModeBtn.classList.remove("d-none");
      jdTextarea.focus();
    });
  }

  if (previewModeBtn && jdTextarea && jdPreview) {
    previewModeBtn.addEventListener("click", function () {
      renderFormattedJd(jdTextarea.value);
      jdTextarea.classList.add("d-none");
      jdTextarea.style.display = "none";
      jdPreview.style.display = "block";
      previewModeBtn.classList.add("d-none");
      if (toggleEditBtn) toggleEditBtn.classList.remove("d-none");
    });
  }

  var formFieldList = document.querySelector("[data-form-field-list]");
  var formConfigErrors = document.querySelector("[data-form-config-errors]");
  var formConfigSuccess = document.querySelector("[data-form-config-success]");
  var formTitleInput = document.querySelector("[data-form-title]");
  var formDescInput = document.querySelector("[data-form-description]");
  var formAllowMultiple = document.querySelector("[data-form-allow-multiple]");
  var formCatalogSections = null;

  function showFormConfigError(msg) {
    if (!formConfigErrors) return;
    formConfigErrors.textContent = msg;
    formConfigErrors.classList.remove("d-none");
    if (formConfigSuccess) formConfigSuccess.classList.add("d-none");
  }

  function showFormConfigSuccess(msg) {
    if (!formConfigSuccess) return;
    formConfigSuccess.textContent = msg;
    formConfigSuccess.classList.remove("d-none");
    if (formConfigErrors) formConfigErrors.classList.add("d-none");
  }

  function openApplicationFormStep() {
    setStepperActive(3);
    if (formBox) formBox.classList.add("d-none");
    if (jdStep) jdStep.classList.add("d-none");
    if (applicationFormStep) {
      applicationFormStep.classList.remove("d-none");
      applicationFormStep.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (currentJobId) loadFormConfig(currentJobId);
  }

  function renderFormFieldCatalog(catalog, selected) {
    if (!formFieldList || !catalog) return;
    formFieldList.innerHTML = "";
    catalog.forEach(function (section) {
      var wrap = document.createElement("div");
      wrap.className = "form-catalog-section mb-3";
      wrap.innerHTML = "<div class=\"fw-semibold small mb-2\">" + section.title + "</div>";
      section.fields.forEach(function (field) {
        var id = "ff_" + field.key;
        var checked = selected.indexOf(field.key) !== -1;
        var row = document.createElement("div");
        row.className = "form-check";
        row.innerHTML =
          "<input class=\"form-check-input\" type=\"checkbox\" id=\"" +
          id +
          "\" data-form-field=\"" +
          field.key +
          "\" " +
          (checked ? "checked" : "") +
          ">" +
          "<label class=\"form-check-label small\" for=\"" +
          id +
          "\">" +
          field.label +
          (field.required ? " *" : "") +
          "</label>";
        wrap.appendChild(row);
      });
      formFieldList.appendChild(wrap);
    });
  }

  function collectSelectedFormFields() {
    var keys = [];
    if (!formFieldList) return keys;
    formFieldList.querySelectorAll("[data-form-field]:checked").forEach(function (el) {
      keys.push(el.getAttribute("data-form-field"));
    });
    return keys;
  }

  function loadFormConfig(jobId) {
    return fetch(jobApiUrl("form-config", jobId), { headers: { Accept: "application/json" } })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (!data.ok) return;
        formCatalogSections = data.catalog;
        var cfg = data.config || {};
        if (formTitleInput) formTitleInput.value = cfg.application_form_title || data.job.title + " - Candidate Application";
        if (formDescInput) formDescInput.value = cfg.form_description || (data.profile_defaults && data.profile_defaults.default_form_description) || "";
        if (formAllowMultiple) formAllowMultiple.checked = !!cfg.allow_multiple_responses;
        var jobTitleEl = document.querySelector("[data-form-job-title]");
        if (jobTitleEl) jobTitleEl.textContent = data.job.title;
        var deadlineEl = document.querySelector("[data-form-job-deadline]");
        if (deadlineEl) deadlineEl.textContent = data.job.application_deadline || "—";
        renderFormFieldCatalog(data.catalog, cfg.selected_fields || []);
        if (formReviewResumeFolder && cfg.resume_drive_folder_url) {
          formReviewResumeFolder.value = cfg.resume_drive_folder_url;
        }
        return data;
      });
  }

  function postJson(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, data: data };
      });
    });
  }

  var formSelectAll = document.querySelector("[data-form-select-all]");
  var formSelectRequired = document.querySelector("[data-form-select-required]");
  if (formSelectAll) {
    formSelectAll.addEventListener("click", function () {
      if (!formFieldList) return;
      formFieldList.querySelectorAll("[data-form-field]").forEach(function (el) {
        el.checked = true;
      });
    });
  }
  if (formSelectRequired) {
    formSelectRequired.addEventListener("click", function () {
      if (!formCatalogSections || !formFieldList) return;
      formFieldList.querySelectorAll("[data-form-field]").forEach(function (el) {
        el.checked = false;
      });
      formCatalogSections.forEach(function (section) {
        section.fields.forEach(function (field) {
          if (field.required) {
            var input = formFieldList.querySelector('[data-form-field="' + field.key + '"]');
            if (input) input.checked = true;
          }
        });
      });
    });
  }

  var formSaveBtn = document.querySelector("[data-form-save-config]");
  if (formSaveBtn) {
    formSaveBtn.addEventListener("click", function () {
      if (!currentJobId) return;
      var payload = {
        application_form_title: formTitleInput ? formTitleInput.value : "",
        form_description: formDescInput ? formDescInput.value : "",
        selected_fields: collectSelectedFormFields(),
        allow_multiple_responses: formAllowMultiple ? formAllowMultiple.checked : false,
      };
      postJson(jobApiUrl("form-save", currentJobId), payload).then(function (result) {
        if (!result.ok) {
          showFormConfigError(firstErrorMessage(result.data, "Could not save."));
          return;
        }
        showFormConfigSuccess(result.data.message || "Saved.");
      });
    });
  }

  var formGenerateBtn = document.querySelector("[data-form-generate]");
  var formReview = document.querySelector("[data-form-review]");
  var formReviewUrl = document.querySelector("[data-form-review-url]");
  var formReviewResumeFolder = document.querySelector("[data-form-resume-folder]");
  var formReviewOpen = document.querySelector("[data-form-review-open]");
  var formReviewEdit = document.querySelector("[data-form-review-edit]");
  var formConfirmBtn = document.querySelector("[data-form-confirm]");

  function showFormReview(resultData) {
    if (!formReview) return;
    formReview.classList.remove("d-none");
    var url = resultData.form_url || "";
    var editUrl = resultData.form_edit_url || url.replace("/viewform", "/edit");
    if (formReviewUrl) formReviewUrl.value = url;
    if (formReviewResumeFolder) {
      formReviewResumeFolder.value = resultData.resume_drive_folder_url || formReviewResumeFolder.value || "";
    }
    if (formReviewOpen) formReviewOpen.href = url;
    if (formReviewEdit) formReviewEdit.href = editUrl;
    showFormConfigSuccess(resultData.message || "Form created — review the link below.");
  }

  function openJobCompleteStep(formUrl, message, finalizedJd) {
    setStepperActive(4);
    if (formBox) formBox.classList.add("d-none");
    if (applicationFormStep) applicationFormStep.classList.add("d-none");
    if (jdStep) jdStep.classList.remove("d-none");
    if (jdEditor) jdEditor.classList.add("d-none");
    if (jdComplete) jdComplete.classList.remove("d-none");
    if (finalizedJd && jdTextarea) {
      jdTextarea.value = finalizedJd;
      aiDraftSnapshot = finalizedJd;
      renderFormattedJd(finalizedJd);
    }
    var msg = document.querySelector("[data-jd-complete-text]");
    if (msg) msg.textContent = message || "Application link saved in your job description.";
    var link = document.querySelector("[data-form-url-open]");
    if (link && formUrl) {
      link.href = formUrl;
      link.classList.remove("d-none");
    }
    if (jdStep) jdStep.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (formGenerateBtn) {
    formGenerateBtn.addEventListener("click", function () {
      if (!currentJobId) return;
      formGenerateBtn.disabled = true;
      if (formReview) formReview.classList.add("d-none");
      var payload = {
        application_form_title: formTitleInput ? formTitleInput.value : "",
        form_description: formDescInput ? formDescInput.value : "",
        selected_fields: collectSelectedFormFields(),
        allow_multiple_responses: formAllowMultiple ? formAllowMultiple.checked : false,
        finalized_jd: currentJdText(),
      };
      postJson(jobApiUrl("create-form", currentJobId), payload)
        .then(function (result) {
          if (!result.ok) {
            if (result.data.profile_required) {
              openProfileGateModal();
              return;
            }
            var errMsg = firstErrorMessage(result.data, "Could not create form.");
            if (result.data.integrations_settings) {
              errMsg += ' Open Account → Integrations (or "Profile & integrations") and reconnect Google Workspace.';
            }
            showFormConfigError(errMsg);
            if (result.data.integrations_settings && window.AUTOHR_ACCOUNT && document.querySelector('[data-panel="account"]')) {
              var goBtn = document.createElement("button");
              goBtn.type = "button";
              goBtn.className = "btn btn-sm btn-outline-danger mt-2";
              goBtn.textContent = "Open integrations settings";
              goBtn.addEventListener("click", function () {
                var nav = document.querySelector('[data-panel-target="account"]');
                if (nav) nav.click();
                window.setTimeout(function () {
                  var el = document.getElementById("account-integrations");
                  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
                }, 200);
              });
              var errBox = document.querySelector("[data-form-config-errors]");
              if (errBox && !errBox.querySelector("[data-form-goto-integrations]")) {
                goBtn.setAttribute("data-form-goto-integrations", "1");
                errBox.appendChild(goBtn);
              }
            }
            return;
          }
          showFormReview(result.data);
        })
        .finally(function () {
          formGenerateBtn.disabled = false;
        });
    });
  }

  if (formConfirmBtn) {
    formConfirmBtn.addEventListener("click", function () {
      if (!currentJobId) return;
      var url = formReviewUrl ? formReviewUrl.value.trim() : "";
      if (!url) {
        showFormConfigError("Paste or keep the Google Form link before continuing.");
        return;
      }
      formConfirmBtn.disabled = true;
      var folderUrl = formReviewResumeFolder ? formReviewResumeFolder.value.trim() : "";
      postJson(jobApiUrl("confirm-form", currentJobId), {
        form_url: url,
        resume_drive_folder_url: folderUrl,
      })
        .then(function (result) {
          if (!result.ok) {
            showFormConfigError(firstErrorMessage(result.data, "Could not save form link."));
            return;
          }
          openJobCompleteStep(
            result.data.form_url || url,
            result.data.message || "Application link saved in your job description.",
            result.data.finalized_jd
          );
        })
        .finally(function () {
          formConfirmBtn.disabled = false;
        });
    });
  }

  if (postGoogleBtn) {
    postGoogleBtn.addEventListener("click", function () {
      if (!currentJobId) return;
      if (jdErrors) jdErrors.classList.add("d-none");
      postGoogleBtn.disabled = true;

      if (!isProfileComplete()) {
        postJdForm(currentJobId, "save-draft")
          .then(function (result) {
            if (handleAuthFailure(result)) return;
            if (!result.ok) {
              showJdErrors(result.data.errors || result.data);
              return;
            }
            aiDraftSnapshot = currentJdText();
            openProfileGateModal();
          })
          .catch(function () {
            showJdErrors({ _: ["Network error while saving your draft."] });
          })
          .finally(function () {
            postGoogleBtn.disabled = false;
          });
        return;
      }

      postJdForm(currentJobId, "prepare")
        .then(function (result) {
          if (handleAuthFailure(result)) return;
          if (!result.ok) {
            var payload = result.data || {};
            if (payload.profile_required) {
              form.setAttribute("data-profile-complete", "0");
              return postJdForm(currentJobId, "save-draft").then(function (draftResult) {
                if (draftResult.ok) openProfileGateModal();
                else showJdErrors(draftResult.data.errors || draftResult.data);
              });
            }
            showJdErrors(payload.errors || payload);
            return;
          }
          aiDraftSnapshot = currentJdText();
          openApplicationFormStep();
        })
        .catch(function () {
          showJdErrors({ _: ["Network error while saving the finalized description."] });
        })
        .finally(function () {
          postGoogleBtn.disabled = false;
        });
    });
  }

  if (jdRetryBtn) {
    jdRetryBtn.addEventListener("click", function () {
      if (!currentJobId) return;
      jdRetryBtn.disabled = true;
      runGenerateJd(currentJobId, jdTitle ? jdTitle.textContent.replace(/^AI Job Description — /, "") : "")
        .finally(function () {
          jdRetryBtn.disabled = false;
        });
    });
  }

  if (generateBtn) {
    generateBtn.addEventListener("click", function () {
      submitJob();
    });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    submitJob();
  });

  window.loadJobDraft = function (jobId) {
    if (!jobId) return Promise.resolve();
    return fetch("/dashboard/jobs/" + jobId + "/draft/", {
      headers: { Accept: "application/json" },
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok || !result.data.ok) return;
        var d = result.data;
        currentJobId = d.job_id;
        var title = d.title || "Draft";
        var step = Number(d.resume_step) || 2;
        var sub = d.resume_substep || "";

        if (step === 4) {
          openJobCompleteStep(d.form_url, "Continue your draft from the publish step.", d.jd_text || d.approved_jd);
          return;
        }
        if (step === 3) {
          openApplicationFormStep();
          var resumeReview = sub === "form_review";
          loadFormConfig(currentJobId).then(function () {
            if (resumeReview) {
              showFormReview({
                form_url: d.form_url,
                form_edit_url: d.form_edit_url,
                resume_drive_folder_url: d.resume_drive_folder_url,
                message: "Continue reviewing your Google Form.",
              });
            } else if (formReview) {
              formReview.classList.add("d-none");
            }
          });
          return;
        }
        if (step === 2) {
          if (sub === "jd_generate") {
            openJdStep(title, false);
            showJdRetry();
          } else {
            openJdStep(title, false);
            var jdBody = d.jd_text || d.approved_jd || d.ai_generated_jd || "";
            if (jdBody) showJdEditor(jdBody, title);
            else showJdRetry();
          }
          return;
        }
        setStepperActive(1);
        if (formBox) formBox.classList.remove("d-none");
        if (jdStep) jdStep.classList.add("d-none");
        if (applicationFormStep) applicationFormStep.classList.add("d-none");
        var titleInput = form.querySelector('[name="title"]');
        if (titleInput && title) titleInput.value = title;
        syncPreview();
      });
  };
});
