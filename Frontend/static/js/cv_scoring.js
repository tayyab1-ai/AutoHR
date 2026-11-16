document.addEventListener("DOMContentLoaded", function () {
  var cfg = window.AUTOHR_CV || {};
  var jobsEl = document.getElementById("cv-jobs-data");
  var candsEl = document.getElementById("cv-candidates-data");
  if (!jobsEl || !candsEl) return;

  var jobs = [];
  var candidates = [];
  try {
    jobs = JSON.parse(jobsEl.textContent || "[]") || [];
    candidates = JSON.parse(candsEl.textContent || "[]") || [];
  } catch (e) {
    return;
  }

  var jobFilter = document.querySelector("[data-cv-job-filter]");
  var statusFilter = document.querySelector("[data-cv-status-filter]");
  var cfgJobSelect = document.querySelector("[data-cv-cfg-job]");
  var cfgJobLabel = document.querySelector("[data-cv-metrics-job-label]");
  var cfgSkill = document.querySelector("[data-cv-cfg-skill]");
  var cfgExp = document.querySelector("[data-cv-cfg-exp]");
  var cfgEdu = document.querySelector("[data-cv-cfg-edu]");
  var cfgPass = document.querySelector("[data-cv-cfg-pass]");
  var cfgCap = document.querySelector("[data-cv-cfg-cap]");
  var cfgTotalBadge = document.querySelector("[data-cv-cfg-total]");
  var cfgSaveBtn = document.querySelector("[data-cv-save-metrics]");
  var cfgToast = document.querySelector("[data-cv-metrics-toast]");
  var cfgFieldsWrap = document.querySelector("[data-cv-metrics-fields]");

  var listWrap = document.querySelector("[data-cv-candidate-list]");
  var detailWrap = document.querySelector("[data-cv-candidate-detail]");
  var countEl = document.querySelector("[data-cv-candidate-count]");

  var modalBackdrop = document.querySelector("[data-score-cv-backdrop]");
  var openModalBtn = document.querySelector("[data-open-score-cv-modal]");
  var modalForm = document.querySelector("[data-score-cv-form]");
  var modalJobSelect = document.getElementById("scv_job");
  var modalError = document.querySelector("[data-score-cv-error]");
  var modalSubmitBtn = document.querySelector("[data-score-cv-submit]");

  var selectedCandidateId = candidates.length ? candidates[0].id : null;
  var activeDetailTab = "breakdown";

  function getCsrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function escapeHtml(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function urlFromTemplate(tpl, id, fallback) {
    if (!tpl || !cfg.idPlaceholder) return fallback;
    return tpl.split(cfg.idPlaceholder).join(id);
  }

  function showToast(ok, message, tone) {
    if (!cfgToast) return;
    cfgToast.textContent = message;
    cfgToast.classList.remove("d-none", "alert-success", "alert-danger", "alert-warning");
    cfgToast.classList.add(tone ? "alert-" + tone : (ok ? "alert-success" : "alert-danger"));
  }

  function copyText(input, onDone) {
    var fallback = function () {
      input.select();
      try {
        if (document.execCommand("copy")) onDone();
      } catch (e) { /* user can still copy manually from the selected field */ }
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(input.value).then(onDone, fallback);
    } else {
      fallback();
    }
  }

  /* Toast plus a list of copyable invitation links (for invites whose email failed). */
  function showInviteLinksToast(message, tone, links) {
    showToast(tone !== "danger", message, tone);
    if (!cfgToast || !links || !links.length) return;
    var wrap = document.createElement("div");
    wrap.className = "cv-invite-links mt-2";
    links.forEach(function (item) {
      var row = document.createElement("div");
      row.className = "cv-invite-link-row";
      var who = document.createElement("div");
      who.className = "small fw-semibold";
      who.textContent = (item.name || "Candidate") + (item.email ? " (" + item.email + ")" : "");
      if (item.error) {
        var err = document.createElement("span");
        err.className = "fw-normal text-danger ms-1";
        err.textContent = "— " + item.error;
        who.appendChild(err);
      }
      var line = document.createElement("div");
      line.className = "d-flex gap-1 align-items-center";
      var input = document.createElement("input");
      input.type = "text";
      input.readOnly = true;
      input.className = "db-input flex-grow-1";
      input.value = item.url || "";
      input.setAttribute("aria-label", "Invitation link");
      input.addEventListener("focus", function () { input.select(); });
      var copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "btn-db-secondary btn-sm";
      copyBtn.innerHTML = '<i class="bi bi-clipboard"></i> Copy';
      copyBtn.addEventListener("click", function () {
        copyText(input, function () {
          copyBtn.innerHTML = '<i class="bi bi-check2"></i> Copied';
          window.setTimeout(function () { copyBtn.innerHTML = '<i class="bi bi-clipboard"></i> Copy'; }, 1500);
        });
      });
      line.appendChild(input);
      line.appendChild(copyBtn);
      row.appendChild(who);
      row.appendChild(line);
      wrap.appendChild(row);
    });
    cfgToast.appendChild(wrap);
  }

  /* Reload jobs/candidates from the dashboard page's embedded JSON (there is no list API). */
  function reloadCandidates() {
    return fetch(cfg.dashboardUrl || "/dashboard/", {
      headers: { Accept: "text/html" },
      credentials: "same-origin",
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.text();
      })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var cEl = doc.getElementById("cv-candidates-data");
        var jEl = doc.getElementById("cv-jobs-data");
        if (!cEl) throw new Error("No candidate data in page");
        candidates = JSON.parse(cEl.textContent || "[]") || candidates;
        if (jEl) jobs = JSON.parse(jEl.textContent || "[]") || jobs;
        populateJobSelects(jobFilter ? jobFilter.value : "");
        renderCandidates();
      });
  }

  function populateJobSelects(preferredId) {
    var activeFilter = preferredId !== undefined ? preferredId : (jobFilter ? jobFilter.value : "");
    if (jobFilter) {
      var prevF = activeFilter;
      jobFilter.innerHTML = '<option value="">All Jobs</option>';
      jobs.forEach(function (j) {
        var opt = document.createElement("option");
        opt.value = j.id;
        opt.textContent = j.title + " (" + j.applicants + ")";
        jobFilter.appendChild(opt);
      });
      if (prevF && jobs.some(function (j) { return j.id === prevF; })) {
        jobFilter.value = prevF;
      }
    }

    var fillSelect = function (sel, selected) {
      if (!sel) return;
      sel.innerHTML = "";
      if (!jobs.length) {
        var emptyOpt = document.createElement("option");
        emptyOpt.value = "";
        emptyOpt.textContent = "Create a job first";
        sel.appendChild(emptyOpt);
        return;
      }
      jobs.forEach(function (j) {
        var opt = document.createElement("option");
        opt.value = j.id;
        opt.textContent = j.title + " (" + j.department + ")";
        sel.appendChild(opt);
      });
      if (selected && jobs.some(function (j) { return j.id === selected; })) {
        sel.value = selected;
      } else if (jobs.length) {
        sel.value = jobs[0].id;
      }
    };

    var currentCfgId = cfgJobSelect ? cfgJobSelect.value : "";
    fillSelect(cfgJobSelect, currentCfgId || (jobFilter && jobFilter.value) || (jobs[0] && jobs[0].id));
    fillSelect(modalJobSelect, (jobFilter && jobFilter.value) || (cfgJobSelect && cfgJobSelect.value));
    syncMetricsCardFromSelectedJob();
  }

  function findJob(jobId) {
    return jobs.find(function (j) { return j.id === jobId; }) || null;
  }

  function updateMetricsTotalBadge() {
    if (!cfgTotalBadge) return;
    var sum = Number(cfgSkill.value || 0) + Number(cfgExp.value || 0) + Number(cfgEdu.value || 0);
    cfgTotalBadge.textContent = "Total: " + sum + "%";
    cfgTotalBadge.classList.toggle("db-badge-live", sum === 100);
    cfgTotalBadge.classList.toggle("db-badge-rejected", sum !== 100);
  }

  function syncMetricsCardFromSelectedJob() {
    var job = cfgJobSelect ? findJob(cfgJobSelect.value) : null;
    if (cfgFieldsWrap) {
      cfgFieldsWrap.classList.toggle("opacity-50", !job);
    }
    if (!job) {
      if (cfgJobLabel) cfgJobLabel.textContent = "— create a job to configure metrics";
      if (cfgSaveBtn) cfgSaveBtn.disabled = true;
      return;
    }
    if (cfgSaveBtn) cfgSaveBtn.disabled = false;
    if (cfgJobLabel) cfgJobLabel.textContent = "— " + job.title;
    if (cfgSkill) cfgSkill.value = job.cv_skill_weight;
    if (cfgExp) cfgExp.value = job.cv_experience_weight;
    if (cfgEdu) cfgEdu.value = job.cv_education_weight;
    if (cfgPass) cfgPass.value = job.cv_min_passing_score;
    if (cfgCap) cfgCap.value = job.shortlist_after_cv_count || 25;
    updateMetricsTotalBadge();
  }

  [cfgSkill, cfgExp, cfgEdu].forEach(function (input) {
    if (input) input.addEventListener("input", updateMetricsTotalBadge);
  });

  if (cfgJobSelect) {
    cfgJobSelect.addEventListener("change", syncMetricsCardFromSelectedJob);
  }

  if (cfgSaveBtn) {
    cfgSaveBtn.addEventListener("click", function () {
      var jobId = cfgJobSelect ? cfgJobSelect.value : "";
      if (!jobId) return;
      var sum = Number(cfgSkill.value || 0) + Number(cfgExp.value || 0) + Number(cfgEdu.value || 0);
      if (sum !== 100) {
        showToast(false, "Skills, Experience, and Education weights must sum to 100% (currently " + sum + "%).");
        return;
      }
      cfgSaveBtn.disabled = true;
      fetch(urlFromTemplate(cfg.metricsUrlTemplate, jobId, "/dashboard/jobs/" + jobId + "/cv-metrics/"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrf(),
          Accept: "application/json",
        },
        body: JSON.stringify({
          cv_skill_weight: cfgSkill.value,
          cv_experience_weight: cfgExp.value,
          cv_education_weight: cfgEdu.value,
          cv_min_passing_score: cfgPass.value,
          shortlist_after_cv_count: cfgCap.value,
        }),
      })
        .then(function (r) {
          return r.json().then(function (d) { return { ok: r.ok, data: d }; });
        })
        .then(function (res) {
          cfgSaveBtn.disabled = false;
          if (!res.ok || !res.data.ok) {
            showToast(false, (res.data && res.data.error) || "Could not update CV scoring metrics.");
            return;
          }
          jobs = res.data.jobs || jobs;
          candidates = res.data.candidates || candidates;
          updateOverviewKpis(res.data.kpis);
          populateJobSelects(jobFilter ? jobFilter.value : "");
          renderCandidates();
          showToast(true, res.data.message);
        })
        .catch(function () {
          cfgSaveBtn.disabled = false;
          showToast(false, "Network error while saving CV scoring metrics.");
        });
    });
  }

  function updateOverviewKpis(kpis) {
    if (!Array.isArray(kpis)) return;
    var cards = document.querySelectorAll('[data-panel="overview"] .db-kpi-card');
    kpis.forEach(function (kpi, idx) {
      var card = cards[idx];
      if (!card) return;
      var valEl = card.querySelector(".db-kpi-value");
      var trendEl = card.querySelector(".db-kpi-trend");
      if (valEl) valEl.textContent = kpi.value;
      if (trendEl) trendEl.innerHTML = '<i class="bi bi-arrow-up-short"></i>' + escapeHtml(kpi.trend);
    });
  }

  function filteredCandidates() {
    var jid = jobFilter ? jobFilter.value : "";
    var st = statusFilter ? statusFilter.value : "";
    return candidates.filter(function (c) {
      if (jid && c.job_id !== jid) return false;
      if (st && c.status !== st) return false;
      return true;
    });
  }

  function statusBadgeHtml(c) {
    if (c.status === "shortlisted") return '<span class="db-badge db-badge-shortlisted">Shortlisted</span>';
    if (c.status === "interview_invited") return '<span class="db-badge db-badge-scheduled">Invited to Interview</span>';
    if (c.status === "interview_scheduled") return '<span class="db-badge db-badge-interviewing">Interview Scheduled</span>';
    if (c.status === "interview_in_progress") return '<span class="db-badge db-badge-interviewing">In Progress</span>';
    if (c.status === "interview_completed") return '<span class="db-badge db-badge-live">Interview Completed</span>';
    if (c.status === "interviewing") return '<span class="db-badge db-badge-interviewing">Interviewing</span>';
    if (c.status === "rejected") return '<span class="db-badge db-badge-rejected">Not Progressing</span>';
    return '<span class="db-badge db-badge-scheduled">Screened</span>';
  }

  function metricBarHtml(label, score, weight, contribution, rationale) {
    return (
      '<div class="cv-metric-card">' +
      '  <div class="d-flex justify-content-between align-items-center small mb-1">' +
      '    <span class="fw-semibold">' + escapeHtml(label) + ' <span class="text-muted fw-normal">(' + escapeHtml(weight) + '% weight)</span></span>' +
      '    <span><strong>' + escapeHtml(score) + '%</strong> <span class="text-muted">(+' + escapeHtml(contribution) + ' pts)</span></span>' +
      "  </div>" +
      '  <div class="db-score-bar-bg"><div class="db-score-bar-fill" style="width:' + Number(score || 0) + '%;"></div></div>' +
      (rationale ? '<p class="text-muted mb-0 mt-1" style="font-size:12px;">' + escapeHtml(rationale) + "</p>" : "") +
      "</div>"
    );
  }

  function renderCandidateDetail(c) {
    if (!detailWrap) return;
    if (!c) {
      detailWrap.innerHTML =
        '<div class="db-card-body text-muted small">No matching applications yet. Click <strong>Upload &amp; Score CV</strong> above to test scoring against a job\'s rubric.</div>';
      return;
    }

    var thresholdBadge = c.meets_threshold
      ? '<span class="db-badge db-badge-live mt-1">Pass (&ge; ' + escapeHtml(c.min_passing_score) + '%)</span>'
      : '<span class="db-badge db-badge-rejected mt-1">Below ' + escapeHtml(c.min_passing_score) + '% cutoff</span>';

    var skillsHtml = (c.skills || []).map(function (s) {
      return '<span class="db-skill-chip"><span>' + escapeHtml(s) + "</span></span>";
    }).join("") || '<span class="text-muted small">No explicit skills extracted.</span>';

    var matchedHtml = (c.matched_skills || []).map(function (s) {
      return '<span class="cv-chip-matched"><i class="bi bi-check2"></i>' + escapeHtml(s) + "</span>";
    }).join("") || '<span class="text-muted small">None listed</span>';

    var missingHtml = (c.missing_skills || []).map(function (s) {
      return '<span class="cv-chip-missing"><i class="bi bi-x"></i>' + escapeHtml(s) + "</span>";
    }).join("") || '<span class="text-muted small">None missing</span>';

    var strengthsHtml = (c.strengths || []).map(function (item) {
      return "<li>" + escapeHtml(item) + "</li>";
    }).join("");

    var concernsHtml = (c.concerns || []).map(function (item) {
      return "<li>" + escapeHtml(item) + "</li>";
    }).join("");

    var resumeLink = c.resume_file_url
      ? '<a class="btn-db-secondary btn-sm text-decoration-none" href="' + escapeHtml(c.resume_file_url) + '" target="_blank" rel="noopener"><i class="bi bi-file-earmark-text"></i> View CV</a>'
      : "";

    var isShortlisted = c.status === "shortlisted" || c.status === "interview_invited" || c.status === "interview_scheduled";
    var inviteBtn = isShortlisted
      ? '<button type="button" class="btn btn-sm btn-primary ms-1" data-cv-invite="' + escapeHtml(c.id) + '"><i class="bi bi-calendar2-check"></i> ' + (c.status === "interview_invited" ? "Re-send Invite" : "Invite to Interview") + "</button>"
      : "";

    detailWrap.innerHTML =
      '<div class="db-card-header flex-wrap gap-2">' +
      '  <div class="d-flex align-items-center gap-3">' +
      '    <span class="avatar-circle" style="width:48px;height:48px;font-size:16px;">' + escapeHtml(c.initials) + "</span>" +
      "    <div>" +
      '      <h2 class="db-card-title mb-0">' + escapeHtml(c.name) + "</h2>" +
      '      <div class="text-muted small">' + escapeHtml(c.role) + " &middot; " + escapeHtml(c.city) + " &middot; " + escapeHtml(c.email) + "</div>" +
      "    </div>" +
      "  </div>" +
      '  <div class="d-flex flex-wrap align-items-center gap-2">' +
      statusBadgeHtml(c) +
      resumeLink +
      inviteBtn +
      "  </div>" +
      "</div>" +
      '<div class="db-card-body">' +
      '  <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">' +
      '    <div class="db-tab-bar mb-0">' +
      '      <button type="button" class="db-tab-btn ' + (activeDetailTab === "breakdown" ? "is-active" : "") + '" data-cv-detail-tab="breakdown">Score Breakdown</button>' +
      '      <button type="button" class="db-tab-btn ' + (activeDetailTab === "overview" ? "is-active" : "") + '" data-cv-detail-tab="overview">CV Profile &amp; Notes</button>' +
      "    </div>" +
      '    <div class="d-flex flex-wrap gap-1">' +
      '      <button type="button" class="btn-db-secondary btn-sm" data-cv-decision="shortlisted"><i class="bi bi-check2 text-success"></i> Shortlist</button>' +
      '      <button type="button" class="btn-db-secondary btn-sm" data-cv-decision="rejected"><i class="bi bi-x text-danger"></i> Reject</button>' +
      (c.hr_decision ? '<button type="button" class="btn btn-link btn-sm text-muted" data-cv-decision="auto">Reset to Auto</button>' : "") +
      "    </div>" +
      "  </div>" +
      '  <div class="db-tab-panel ' + (activeDetailTab === "breakdown" ? "is-active" : "") + '" data-cv-tab-pane="breakdown">' +
      '    <div class="row g-3 align-items-center mb-3">' +
      '      <div class="col-md-4 text-center">' +
      '        <div class="db-score-ring">' + escapeHtml(c.overall_score) + "%</div>" +
      '        <div class="small fw-semibold">Weighted Overall</div>' +
      thresholdBadge +
      "      </div>" +
      '      <div class="col-md-8">' +
      metricBarHtml("Skills Match", c.skills_score, c.weights.skills, c.weighted_contributions.skills, c.rationales.skills) +
      metricBarHtml("Experience Match", c.exp_score, c.weights.experience, c.weighted_contributions.experience, c.rationales.experience) +
      metricBarHtml("Education Match", c.edu_score, c.weights.education, c.weighted_contributions.education, c.rationales.education) +
      "      </div>" +
      "    </div>" +
      '    <div class="row g-3 mb-2">' +
      '      <div class="col-md-6"><p class="small text-muted fw-semibold mb-1">Matched Skills</p><div class="d-flex flex-wrap gap-1">' + matchedHtml + "</div></div>" +
      '      <div class="col-md-6"><p class="small text-muted fw-semibold mb-1">Missing Skills</p><div class="d-flex flex-wrap gap-1">' + missingHtml + "</div></div>" +
      "    </div>" +
      '    <div class="db-insight-box"><i class="bi bi-stars text-warning"></i> <strong>AI Summary:</strong> ' + escapeHtml(c.insight) + "</div>" +
      "  </div>" +
      '  <div class="db-tab-panel ' + (activeDetailTab === "overview" ? "is-active" : "") + '" data-cv-tab-pane="overview">' +
      '    <div class="row g-3 mb-3">' +
      '      <div class="col-md-6"><p class="small text-muted mb-1 fw-semibold">Experience (' + escapeHtml(c.experience_years) + ' yrs)</p><p class="small mb-0">' + escapeHtml(c.experience) + "</p></div>" +
      '      <div class="col-md-6"><p class="small text-muted mb-1 fw-semibold">Education (' + escapeHtml(c.highest_degree) + ')</p><p class="small mb-0">' + escapeHtml(c.education) + "</p></div>" +
      "    </div>" +
      '    <p class="small text-muted mb-1 fw-semibold">Extracted Skills</p>' +
      '    <div class="db-skill-list mb-3">' + skillsHtml + "</div>" +
      (strengthsHtml ? '<p class="small text-muted mb-1 fw-semibold">Strengths</p><ul class="small mb-3 ps-3">' + strengthsHtml + "</ul>" : "") +
      (concernsHtml ? '<p class="small text-muted mb-1 fw-semibold">Concerns / Gaps</p><ul class="small mb-0 ps-3">' + concernsHtml + "</ul>" : "") +
      "  </div>" +
      "</div>";

    detailWrap.querySelectorAll("[data-cv-detail-tab]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        activeDetailTab = btn.getAttribute("data-cv-detail-tab");
        renderCandidateDetail(c);
      });
    });

    detailWrap.querySelectorAll("[data-cv-decision]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var dec = btn.getAttribute("data-cv-decision");
        var origHtml = btn.innerHTML;
        btn.disabled = true;
        fetch(urlFromTemplate(cfg.decisionUrlTemplate, c.id, "/dashboard/applications/" + c.id + "/decision/"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
            Accept: "application/json",
          },
          body: JSON.stringify({ decision: dec }),
        })
          .then(function (r) {
            return r.json().then(function (d) { return { ok: r.ok, data: d }; });
          })
          .then(function (res) {
            if (!res.ok || !res.data || !res.data.ok) {
              btn.disabled = false;
              btn.innerHTML = origHtml;
              showToast(false, (res.data && res.data.error) || "Could not update the candidate decision.");
              return;
            }
            candidates = res.data.candidates || candidates;
            updateOverviewKpis(res.data.kpis);
            renderCandidates();
          })
          .catch(function () {
            btn.disabled = false;
            btn.innerHTML = origHtml;
            showToast(false, "Network error while updating the candidate decision.");
          });
      });
    });

    detailWrap.querySelectorAll("[data-cv-invite]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var appId = btn.getAttribute("data-cv-invite");
        var origInviteHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Inviting...';
        fetch(urlFromTemplate(cfg.inviteUrlTemplate, appId, "/dashboard/applications/" + appId + "/invite/"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
            Accept: "application/json",
          },
        })
          .then(function (r) {
            return r.json().then(function (d) { return { httpOk: r.ok, data: d || {} }; }, function () {
              return { httpOk: false, data: { error: "Unexpected server response (" + r.status + ")." } };
            });
          })
          .then(function (out) {
            var res = out.data;
            if (!out.httpOk || !res.ok) {
              // Includes HTTP 409 (candidate not eligible for an invitation).
              btn.disabled = false;
              btn.innerHTML = origInviteHtml;
              showToast(false, res.error || "Failed to create invitation.");
              return;
            }
            var inv = res.invitation || {};
            var email = inv.candidate_email || c.email || "the candidate";
            c.status = "interview_invited";
            renderCandidates();
            if (inv.email_sent) {
              showToast(true, "Invitation emailed to " + email + ".");
            } else {
              showInviteLinksToast(
                "Invitation created, but the email could not be sent" +
                  (inv.email_error ? ": " + inv.email_error : ".") +
                  " Copy the link below and send it to the candidate manually.",
                "warning",
                [{ name: c.name, email: inv.candidate_email || c.email, url: inv.invitation_url }]
              );
            }
          })
          .catch(function () {
            btn.disabled = false;
            btn.innerHTML = origInviteHtml;
            showToast(false, "Network error while sending invitation.");
          });
      });
    });
  }

  function renderCandidates() {
    var visible = filteredCandidates();
    if (countEl) countEl.textContent = String(visible.length);
    if (!listWrap) return;

    if (!visible.length) {
      listWrap.innerHTML =
        '<p class="text-muted small px-3 py-3 mb-0">No CVs scored yet for this filter. Use <strong>Upload &amp; Score CV</strong> to evaluate a resume.</p>';
      selectedCandidateId = null;
      renderCandidateDetail(null);
      return;
    }

    if (!visible.some(function (c) { return c.id === selectedCandidateId; })) {
      selectedCandidateId = visible[0].id;
    }

    listWrap.innerHTML = visible.map(function (c) {
      var active = c.id === selectedCandidateId ? " is-selected" : "";
      return (
        '<div class="db-candidate-card' + active + '" data-cv-card="' + escapeHtml(c.id) + '">' +
        '  <span class="avatar-circle" style="width:38px;height:38px;font-size:13px;">' + escapeHtml(c.initials) + "</span>" +
        '  <div class="flex-grow-1">' +
        '    <div class="d-flex justify-content-between align-items-center">' +
        '      <span class="fw-semibold" style="font-size:13.5px;">' + escapeHtml(c.name) + "</span>" +
        '      <span class="fw-bold" style="font-size:13px; color:' + (c.meets_threshold ? "#059669" : "#dc2626") + ';">' + escapeHtml(c.overall_score) + "%</span>" +
        "    </div>" +
        '    <div class="text-muted" style="font-size:11.5px;">' + escapeHtml(c.role) + " &middot; " + escapeHtml(c.city) + "</div>" +
        '    <div class="db-score-bar-bg"><div class="db-score-bar-fill" style="width:' + Number(c.score || 0) + '%;"></div></div>' +
        '    <div class="d-flex justify-content-between text-muted mt-1" style="font-size:11px;"><span>' + escapeHtml(c.status) + "</span><span>" + escapeHtml(c.applied) + "</span></div>" +
        "  </div>" +
        "</div>"
      );
    }).join("");

    listWrap.querySelectorAll("[data-cv-card]").forEach(function (card) {
      card.addEventListener("click", function () {
        selectedCandidateId = card.getAttribute("data-cv-card");
        renderCandidates();
      });
    });

    var current = visible.find(function (c) { return c.id === selectedCandidateId; }) || visible[0];
    renderCandidateDetail(current);
  }

  if (jobFilter) {
    jobFilter.addEventListener("change", function () {
      if (jobFilter.value && cfgJobSelect) {
        cfgJobSelect.value = jobFilter.value;
        syncMetricsCardFromSelectedJob();
      }
      renderCandidates();
    });
  }

  if (statusFilter) {
    statusFilter.addEventListener("change", renderCandidates);
  }

  function closeModal() {
    if (!modalBackdrop) return;
    modalBackdrop.classList.add("d-none");
    modalBackdrop.setAttribute("aria-hidden", "true");
  }

  if (openModalBtn && modalBackdrop) {
    openModalBtn.addEventListener("click", function () {
      if (!jobs.length) {
        showToast(false, "Create at least one job first before scoring CVs.");
        return;
      }
      if (modalError) modalError.classList.add("d-none");
      if (modalJobSelect && cfgJobSelect && cfgJobSelect.value) {
        modalJobSelect.value = cfgJobSelect.value;
      }
      modalBackdrop.classList.remove("d-none");
      modalBackdrop.setAttribute("aria-hidden", "false");
    });
  }

  document.querySelectorAll("[data-score-cv-close]").forEach(function (btn) {
    btn.addEventListener("click", closeModal);
  });

  if (modalForm) {
    modalForm.addEventListener("submit", function (event) {
      event.preventDefault();
      if (modalError) modalError.classList.add("d-none");
      if (!modalJobSelect || !modalJobSelect.value) {
        if (modalError) {
          modalError.textContent = "Please create and select a job posting first.";
          modalError.classList.remove("d-none");
        }
        return;
      }
      var body = new FormData(modalForm);
      if (modalSubmitBtn) {
        modalSubmitBtn.disabled = true;
        modalSubmitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Evaluating CV...';
      }
      fetch(cfg.scoreUrl || "/dashboard/applications/score-cv/", {
        method: "POST",
        headers: { "X-CSRFToken": getCsrf(), Accept: "application/json" },
        body: body,
      })
        .then(function (r) {
          return r.json().then(function (d) { return { ok: r.ok, data: d }; });
        })
        .then(function (res) {
          if (modalSubmitBtn) {
            modalSubmitBtn.disabled = false;
            modalSubmitBtn.innerHTML = '<i class="bi bi-stars"></i> Score CV';
          }
          if (!res.ok || !res.data.ok) {
            if (modalError) {
              modalError.textContent = (res.data && res.data.error) || "Could not evaluate CV.";
              modalError.classList.remove("d-none");
            }
            return;
          }
          jobs = res.data.jobs || jobs;
          candidates = res.data.candidates || candidates;
          if (res.data.application) {
            selectedCandidateId = res.data.application.id;
          }
          updateOverviewKpis(res.data.kpis);
          populateJobSelects(jobFilter ? jobFilter.value : "");
          renderCandidates();
          modalForm.reset();
          closeModal();
          showToast(true, res.data.message);
        })
        .catch(function () {
          if (modalSubmitBtn) {
            modalSubmitBtn.disabled = false;
            modalSubmitBtn.innerHTML = '<i class="bi bi-stars"></i> Score CV';
          }
          if (modalError) {
            modalError.textContent = "Network error while scoring CV.";
            modalError.classList.remove("d-none");
          }
        });
    });
  }

  var syncFormBtn = document.querySelector("[data-cv-sync-form]");
  if (syncFormBtn) {
    syncFormBtn.addEventListener("click", function () {
      var currentJobId = jobFilter ? jobFilter.value : "";
      var url = currentJobId
        ? urlFromTemplate(cfg.syncFormUrlTemplate, currentJobId, "/dashboard/jobs/" + currentJobId + "/sync-form/")
        : (cfg.syncAllFormsUrl || "/dashboard/forms/sync-all/");

      var origHtml = syncFormBtn.innerHTML;
      syncFormBtn.disabled = true;
      syncFormBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Syncing...';

      fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrf(), Accept: "application/json" },
      })
        .then(function (r) {
          return r.json().then(function (d) { return { ok: r.ok, data: d }; });
        })
        .then(function (res) {
          syncFormBtn.disabled = false;
          syncFormBtn.innerHTML = origHtml;
          if (!res.ok || !res.data.ok) {
            showToast(false, (res.data && (res.data.message || res.data.error)) || "Could not sync Google Form responses.");
            return;
          }
          jobs = res.data.jobs || jobs;
          candidates = res.data.candidates || candidates;
          updateOverviewKpis(res.data.kpis);
          populateJobSelects(jobFilter ? jobFilter.value : "");
          renderCandidates();
          showToast(true, res.data.message || "Synced Google Form responses.");
        })
        .catch(function () {
          syncFormBtn.disabled = false;
          syncFormBtn.innerHTML = origHtml;
          showToast(false, "Network error while syncing Google Form responses.");
        });
    });
  }

  var bulkInviteBtn = document.querySelector("[data-cv-bulk-invite]");
  if (bulkInviteBtn) {
    bulkInviteBtn.addEventListener("click", function () {
      var currentJobId = jobFilter ? jobFilter.value : "";
      if (!currentJobId) {
        showToast(false, "Please select a specific job from the dropdown to bulk-invite its shortlisted candidates.");
        return;
      }
      var origHtml = bulkInviteBtn.innerHTML;
      bulkInviteBtn.disabled = true;
      bulkInviteBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Inviting...';

      fetch(urlFromTemplate(cfg.bulkInviteUrlTemplate, currentJobId, "/dashboard/jobs/" + currentJobId + "/invite-shortlisted/"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrf(),
          Accept: "application/json",
        },
      })
        .then(function (r) {
          return r.json().then(function (d) { return { httpOk: r.ok, data: d || {} }; }, function () {
            return { httpOk: false, data: { error: "Unexpected server response (" + r.status + ")." } };
          });
        })
        .then(function (out) {
          var res = out.data;
          bulkInviteBtn.disabled = false;
          bulkInviteBtn.innerHTML = origHtml;
          if (!out.httpOk || !res.ok) {
            showToast(false, res.error || "Failed to send bulk invitations.");
            return;
          }
          var message = res.message || ("Created " + (res.invited_count || 0) + " invitation(s).");
          var invited = Array.isArray(res.candidates) ? res.candidates : [];
          var unsent = invited.filter(function (x) { return x && x.email_sent === false; });

          // Optimistically mark invited candidates, then reload the real list from the server.
          invited.forEach(function (x) {
            var cand = candidates.find(function (cc) { return cc.id === x.application_id; });
            if (cand) cand.status = "interview_invited";
          });
          renderCandidates();

          var report = function () {
            if (unsent.length) {
              showInviteLinksToast(
                message + " " + unsent.length + " email(s) could not be sent. Copy these links and send them manually:",
                "warning",
                unsent.map(function (x) {
                  return { name: x.candidate_name, email: x.candidate_email, url: x.invitation_url, error: x.email_error };
                })
              );
            } else {
              showToast(true, message);
            }
          };
          reloadCandidates().then(report, report);
        })
        .catch(function () {
          bulkInviteBtn.disabled = false;
          bulkInviteBtn.innerHTML = origHtml;
          showToast(false, "Network error during bulk invitations.");
        });
    });
  }

  populateJobSelects("");
  renderCandidates();
});

