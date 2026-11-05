document.addEventListener("DOMContentLoaded", function () {
  var TECH_CATEGORIES = ["software_development", "data_science", "ai_ml", "cybersecurity"];

  var form = document.querySelector("[data-create-job-form]");
  if (!form) return;

  var generateBtn = document.querySelector("[data-generate-jd]");
  var errorBox = document.querySelector("[data-create-job-errors]");
  var formBox = document.querySelector("[data-create-job-fields]");
  var jdStep = document.querySelector("[data-create-job-jd-step]");
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
    var template =
      kind === "prepare"
        ? form.getAttribute("data-job-url-prepare-form")
        : form.getAttribute("data-job-url-generate");
    if (!template) {
      return (
        "/dashboard/jobs/" +
        jobId +
        (kind === "prepare" ? "/prepare-google-form/" : "/generate-jd/")
      );
    }
    return template.split(jobUrlPlaceholder).join(jobId);
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
    set("[data-preview-shortlist-cv]", form.querySelector('[name="shortlist_after_cv_count"]')?.value || "25");
    set("[data-preview-shortlist-iv]", form.querySelector('[name="shortlist_after_interview_count"]')?.value || "10");
  }

  form.addEventListener("input", syncPreview);
  form.addEventListener("change", function () {
    toggleConditionals();
    syncPreview();
  });
  toggleConditionals();
  syncPreview();

  function showFormErrors(payload) {
    if (!errorBox) return;
    var lines = [];
    if (payload && typeof payload === "object") {
      Object.keys(payload).forEach(function (key) {
        var msgs = payload[key];
        if (Array.isArray(msgs)) {
          msgs.forEach(function (m) {
            lines.push(m);
          });
        }
      });
    }
    if (!lines.length) lines.push("Could not save the job. Check required fields.");
    errorBox.textContent = lines.join(" ");
    errorBox.classList.remove("d-none");
    formBox?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function showJdErrors(payload) {
    if (!jdErrors) return;
    var lines = [];
    if (payload && typeof payload === "object") {
      Object.keys(payload).forEach(function (key) {
        var msgs = payload[key];
        if (Array.isArray(msgs)) {
          msgs.forEach(function (m) {
            lines.push(m);
          });
        }
      });
    }
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

  if (postGoogleBtn) {
    postGoogleBtn.addEventListener("click", function () {
      if (!currentJobId) return;
      if (jdErrors) jdErrors.classList.add("d-none");
      postGoogleBtn.disabled = true;

      var text = (jdTextarea && jdTextarea.value ? jdTextarea.value : aiDraftSnapshot).trim();

      var body = new FormData();
      body.append("finalized_jd", text.trim());

      fetch(jobApiUrl("prepare", currentJobId), {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          Accept: "application/json",
        },
        body: body,
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, status: res.status, data: data };
          });
        })
        .then(function (result) {
          if (handleAuthFailure(result)) return;
          if (!result.ok) {
            var payload = result.data || {};
            if (payload.profile_required && typeof window.openProfileWizard === "function") {
              showJdErrors(
                payload.errors || {
                  profile: ["Complete your HR profile setup before continuing past the job description step."],
                }
              );
              window.openProfileWizard(1);
              return;
            }
            showJdErrors(payload.errors || payload);
            return;
          }
          setStepperActive(3);
          if (jdEditor) jdEditor.classList.add("d-none");
          if (jdComplete) jdComplete.classList.remove("d-none");
          var msg = document.querySelector("[data-jd-complete-text]");
          if (msg && result.data.message) msg.textContent = result.data.message;
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
        currentJobId = result.data.job_id;
        var title = result.data.title || "Draft";
        if (result.data.has_jd && result.data.ai_generated_jd) {
          openJdStep(title, false);
          showJdEditor(result.data.ai_generated_jd, title);
        } else {
          setStepperActive(1);
          if (formBox) formBox.classList.remove("d-none");
          if (jdStep) jdStep.classList.add("d-none");
          var titleInput = form.querySelector('[name="title"]');
          if (titleInput && title) titleInput.value = title;
          syncPreview();
        }
      });
  };
});
