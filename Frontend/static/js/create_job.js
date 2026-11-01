document.addEventListener("DOMContentLoaded", function () {
  var TECH_CATEGORIES = ["software_development", "data_science", "ai_ml", "cybersecurity"];

  var form = document.querySelector("[data-create-job-form]");
  if (!form) return;

  var generateBtn = document.querySelector("[data-generate-jd]");
  var errorBox = document.querySelector("[data-create-job-errors]");
  var formBox = document.querySelector("[data-create-job-fields]");
  var resultBox = document.querySelector("[data-create-job-result]");

  function getCsrfToken() {
    var input = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
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

  function showErrors(payload) {
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
  }

  function submitJob() {
    if (errorBox) errorBox.classList.add("d-none");
    if (generateBtn) {
      generateBtn.disabled = true;
      generateBtn.classList.add("is-loading");
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
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          showErrors(result.data.errors || result.data);
          return;
        }
        if (formBox) formBox.classList.add("d-none");
        if (resultBox) resultBox.classList.remove("d-none");
        var msg = document.querySelector("[data-create-job-success-text]");
        if (msg && result.data.message) msg.textContent = result.data.message;
      })
      .catch(function () {
        showErrors({ _: ["Network error while saving the job."] });
      })
      .finally(function () {
        if (generateBtn) {
          generateBtn.disabled = false;
          generateBtn.classList.remove("is-loading");
        }
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
});
