// Final rankings (leaderboard) + HR override UI for the Interviews panel.
// GET  /dashboard/jobs/<job_id>/leaderboard/
// POST /dashboard/rankings/<ranking_id>/override/  {override_verdict, feedback_notes}

document.addEventListener("DOMContentLoaded", function () {
  var cfg = window.AUTOHR_CV || {};
  var card = document.querySelector("[data-lb-card]");
  if (!card) return;

  var jobSelect = card.querySelector("[data-lb-job]");
  var refreshBtn = card.querySelector("[data-lb-refresh]");
  var body = card.querySelector("[data-lb-body]");
  var toast = card.querySelector("[data-lb-toast]");
  var jobLabel = card.querySelector("[data-lb-job-label]");
  var cvJobFilter = document.querySelector("[data-cv-job-filter]");

  var VERDICTS = [
    { value: "strong_hire", label: "Strong Hire", badge: "db-badge-live" },
    { value: "hire", label: "Hire", badge: "db-badge-shortlisted" },
    { value: "lean_hire", label: "Lean Hire", badge: "db-badge-scheduled" },
    { value: "no_hire", label: "No Hire", badge: "db-badge-rejected" },
  ];

  var jobs = [];
  try {
    var jobsEl = document.getElementById("cv-jobs-data");
    jobs = JSON.parse((jobsEl && jobsEl.textContent) || "[]") || [];
  } catch (e) {
    jobs = [];
  }

  var loadSeq = 0;

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

  function showToast(ok, message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.remove("d-none", "alert-success", "alert-danger");
    toast.classList.add(ok ? "alert-success" : "alert-danger");
  }

  function hideToast() {
    if (toast) toast.classList.add("d-none");
  }

  function verdictMeta(value) {
    var v = String(value || "").toLowerCase();
    return VERDICTS.find(function (x) { return x.value === v; }) || null;
  }

  function verdictBadge(value) {
    if (!value) return '<span class="text-muted small">—</span>';
    var meta = verdictMeta(value);
    if (!meta) return '<span class="db-badge db-badge-closed">' + escapeHtml(value) + "</span>";
    return '<span class="db-badge ' + meta.badge + '">' + escapeHtml(meta.label) + "</span>";
  }

  function fmtScore(n) {
    var num = Number(n);
    if (!isFinite(num)) return "—";
    return (Math.round(num * 10) / 10) + "%";
  }

  function setEmpty(message) {
    if (body) body.innerHTML = '<tr><td colspan="8" class="text-muted text-center py-4">' + message + "</td></tr>";
  }

  function populateJobs() {
    if (!jobSelect) return;
    jobSelect.innerHTML = "";
    if (!jobs.length) {
      var opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "Create a job first";
      jobSelect.appendChild(opt);
      jobSelect.disabled = true;
      if (refreshBtn) refreshBtn.disabled = true;
      setEmpty("No jobs yet. Create a job to see final rankings.");
      return;
    }
    jobs.forEach(function (j) {
      var o = document.createElement("option");
      o.value = j.id;
      o.textContent = j.title;
      jobSelect.appendChild(o);
    });
  }

  function overrideOptionsHtml(current) {
    var cur = String(current || "").toLowerCase();
    return ['<option value="">No override (use AI)</option>']
      .concat(VERDICTS.map(function (v) {
        return '<option value="' + v.value + '"' + (v.value === cur ? " selected" : "") + ">" + escapeHtml(v.label) + "</option>";
      }))
      .join("");
  }

  function rowHtml(r) {
    var rid = escapeHtml(r.id);
    return (
      '<tr data-lb-row="' + rid + '">' +
      '<td class="fw-bold">' + escapeHtml(r.final_rank) + "</td>" +
      "<td>" +
      '  <div class="fw-semibold">' + escapeHtml(r.candidate_name) + "</div>" +
      '  <div class="text-muted" style="font-size:11.5px;">' + escapeHtml(r.candidate_email) + "</div>" +
      "</td>" +
      "<td>" + fmtScore(r.cv_score) + "</td>" +
      "<td>" + fmtScore(r.interview_score) + "</td>" +
      '<td class="fw-bold">' + fmtScore(r.composite_score) + "</td>" +
      '<td><div title="' + escapeHtml(r.ai_justification || "") + '">' + verdictBadge(r.decision_verdict) + "</div>" +
      (r.ai_justification
        ? '<button type="button" class="btn btn-link btn-sm p-0 text-decoration-none small" data-lb-why="' + rid + '">Why?</button>'
        : "") +
      "</td>" +
      '<td style="min-width:220px;">' +
      '  <div class="mb-1" data-lb-current="' + rid + '">' + verdictBadge(r.hr_override_verdict) + "</div>" +
      '  <select class="db-select w-100 mb-1" data-lb-verdict="' + rid + '" aria-label="HR override verdict">' + overrideOptionsHtml(r.hr_override_verdict) + "</select>" +
      '  <textarea class="db-input w-100" rows="2" data-lb-notes="' + rid + '" placeholder="HR feedback notes (optional)">' + escapeHtml(r.hr_feedback_notes || "") + "</textarea>" +
      "</td>" +
      '<td class="text-end"><button type="button" class="btn-db-primary btn-sm" data-lb-save="' + rid + '"><i class="bi bi-check2"></i> Save</button></td>' +
      "</tr>" +
      (r.ai_justification
        ? '<tr class="d-none lb-why-row" data-lb-why-row="' + rid + '"><td></td><td colspan="7"><div class="db-insight-box mb-0"><i class="bi bi-stars text-warning"></i> <strong>AI justification:</strong> ' + escapeHtml(r.ai_justification) + "</div></td></tr>"
        : "")
    );
  }

  function wireRows() {
    body.querySelectorAll("[data-lb-why]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var row = body.querySelector('[data-lb-why-row="' + btn.getAttribute("data-lb-why") + '"]');
        if (row) row.classList.toggle("d-none");
      });
    });

    body.querySelectorAll("[data-lb-save]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var rid = btn.getAttribute("data-lb-save");
        var sel = body.querySelector('[data-lb-verdict="' + rid + '"]');
        var notes = body.querySelector('[data-lb-notes="' + rid + '"]');
        var origHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Saving...';
        hideToast();
        fetch(urlFromTemplate(cfg.overrideUrlTemplate, rid, "/dashboard/rankings/" + rid + "/override/"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
            Accept: "application/json",
          },
          body: JSON.stringify({
            override_verdict: sel ? sel.value : "",
            feedback_notes: notes ? notes.value : "",
          }),
        })
          .then(function (r) {
            return r.json().then(function (d) { return { ok: r.ok, data: d }; }, function () {
              return { ok: false, data: { error: "Unexpected server response (" + r.status + ")." } };
            });
          })
          .then(function (res) {
            btn.disabled = false;
            btn.innerHTML = origHtml;
            if (!res.ok || !res.data || !res.data.ok) {
              showToast(false, (res.data && res.data.error) || "Could not save the override.");
              return;
            }
            var saved = res.data.ranking || {};
            var cur = body.querySelector('[data-lb-current="' + rid + '"]');
            if (cur) cur.innerHTML = verdictBadge(saved.hr_override_verdict);
            if (sel) sel.value = saved.hr_override_verdict || "";
            if (notes) notes.value = saved.hr_feedback_notes || "";
            showToast(true, res.data.message || "Ranking override saved.");
          })
          .catch(function () {
            btn.disabled = false;
            btn.innerHTML = origHtml;
            showToast(false, "Network error while saving the override.");
          });
      });
    });
  }

  function loadLeaderboard() {
    var jobId = jobSelect ? jobSelect.value : "";
    if (!jobId || !body) return;
    var seq = ++loadSeq;
    hideToast();
    setEmpty('<span class="spinner-border spinner-border-sm me-1"></span> Loading rankings...');
    if (refreshBtn) refreshBtn.disabled = true;
    fetch(urlFromTemplate(cfg.leaderboardUrlTemplate, jobId, "/dashboard/jobs/" + jobId + "/leaderboard/"), {
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, data: d }; }, function () {
          return { ok: false, data: { error: "Unexpected server response (" + r.status + ")." } };
        });
      })
      .then(function (res) {
        if (seq !== loadSeq) return;
        if (refreshBtn) refreshBtn.disabled = false;
        if (!res.ok || !res.data || !res.data.ok) {
          setEmpty("Could not load rankings.");
          showToast(false, (res.data && res.data.error) || "Could not load the leaderboard.");
          return;
        }
        if (jobLabel) jobLabel.textContent = res.data.job_title ? "— " + res.data.job_title : "";
        var rows = res.data.leaderboard || [];
        if (!rows.length) {
          setEmpty("No final rankings yet for this job. Rankings appear once candidates complete their AI interviews.");
          return;
        }
        body.innerHTML = rows.map(rowHtml).join("");
        wireRows();
      })
      .catch(function () {
        if (seq !== loadSeq) return;
        if (refreshBtn) refreshBtn.disabled = false;
        setEmpty("Could not load rankings.");
        showToast(false, "Network error while loading the leaderboard.");
      });
  }

  populateJobs();

  if (jobSelect) jobSelect.addEventListener("change", loadLeaderboard);
  if (refreshBtn) refreshBtn.addEventListener("click", loadLeaderboard);

  // "Final Rankings" button in the Applications toolbar: carry over the selected job.
  document.querySelectorAll("[data-lb-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var jid = cvJobFilter ? cvJobFilter.value : "";
      if (jid && jobSelect && jobs.some(function (j) { return j.id === jid; })) {
        jobSelect.value = jid;
      }
      loadLeaderboard();
      window.setTimeout(function () {
        card.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 350);
    });
  });

  // Load lazily the first time the Interviews panel is opened.
  var loadedOnce = false;
  document.querySelectorAll('[data-panel-target="interviews"]').forEach(function (nav) {
    nav.addEventListener("click", function () {
      if (loadedOnce) return;
      loadedOnce = true;
      loadLeaderboard();
    });
  });
  document.querySelectorAll("[data-lb-open]").forEach(function (btn) {
    btn.addEventListener("click", function () { loadedOnce = true; });
  });
});
