/* HR dashboard: live interview list (auto-refresh) and per-question evaluation viewer.
 * Evaluation data comes from HR-only endpoints; candidates never receive it. */
document.addEventListener("DOMContentLoaded", function () {
  var cfg = window.AUTOHR_INTERVIEWS || {};
  if (!cfg.listUrl) return;

  var tableBody = document.querySelector("[data-iv-body]");
  var overviewBody = document.querySelector("[data-iv-overview-body]");
  var overviewSummary = document.querySelector("[data-iv-overview-summary]");
  var panelSummary = document.querySelector("[data-iv-summary]");
  var modalEl = document.getElementById("ivDetailModal");
  var modalBody = modalEl ? modalEl.querySelector("[data-iv-detail-body]") : null;
  var modalTitle = modalEl ? modalEl.querySelector("#ivDetailTitle") : null;
  var modalSub = modalEl ? modalEl.querySelector("[data-iv-detail-sub]") : null;
  var modal = modalEl && window.bootstrap ? new bootstrap.Modal(modalEl) : null;
  var openInterviewId = null;
  var REFRESH_MS = 15000;

  var FACTORS = [
    ["communication", "Communication"],
    ["confidence", "Confidence"],
    ["technical", "Technical"],
    ["relevance", "Relevance"],
    ["problem_solving", "Problem solving"],
  ];
  var STAGE_NAMES = { screening: "Screening & Fit", technical: "Technical Depth", behavioral: "Behavioral & Leadership" };
  var VERDICTS = { strong_hire: "Strong hire", hire: "Hire", lean_hire: "Lean hire", no_hire: "No hire" };

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function statusBadge(row) {
    switch (row.status) {
      case "live":
        return '<span class="db-badge db-badge-live iv-live-badge"><i class="bi bi-record-circle-fill"></i> Live now</span>';
      case "completed":
        return '<span class="db-badge db-badge-completed">Completed</span>';
      case "awaiting_consent":
        return '<span class="db-badge db-badge-draft">Awaiting consent</span>';
      case "missed":
        return '<span class="db-badge db-badge-closed">Missed</span>';
      default:
        return '<span class="db-badge db-badge-scheduled">Scheduled</span>';
    }
  }

  function viewButton(row) {
    if (!row.has_details || !row.interview_id) return "";
    return '<button type="button" class="btn-db-secondary btn-sm" data-iv-view="' + esc(row.interview_id) + '">' +
      (row.status === "live" ? "Watch" : "View") + "</button>";
  }

  function scoreText(v) {
    return v == null ? "&mdash;" : Number(v).toFixed(1) + "%";
  }

  function renderTable(rows) {
    if (!tableBody) return;
    if (!rows.length) {
      tableBody.innerHTML = '<tr><td colspan="9" class="text-muted text-center py-4">No interviews scheduled yet.</td></tr>';
      return;
    }
    tableBody.innerHTML = rows.map(function (r) {
      return "<tr" + (r.status === "live" ? ' class="iv-row-live"' : "") + ">" +
        '<td class="fw-semibold">' + esc(r.candidate) + '<div class="small text-muted fw-normal">' + esc(r.email) + "</div></td>" +
        "<td>" + esc(r.role) + "</td>" +
        "<td>" + esc(r.stage) + "</td>" +
        "<td>" + esc(r.date) + "</td>" +
        "<td>" + esc(r.time) + "</td>" +
        "<td>" + r.answered + "/" + r.total_questions + "</td>" +
        "<td>" + scoreText(r.score) + "</td>" +
        "<td>" + statusBadge(r) + "</td>" +
        "<td>" + viewButton(r) + "</td></tr>";
    }).join("");
  }

  function renderOverview(rows, summary) {
    if (overviewSummary) {
      overviewSummary.textContent = summary.live
        ? summary.live + " live now · " + summary.upcoming + " upcoming"
        : summary.upcoming + " upcoming";
    }
    if (!overviewBody) return;
    var active = rows.filter(function (r) {
      return r.status === "live" || r.status === "scheduled" || r.status === "awaiting_consent";
    }).slice(0, 8);
    if (!active.length) {
      overviewBody.innerHTML = '<tr><td colspan="6" class="text-muted text-center py-3">No live or upcoming interviews right now.</td></tr>';
      return;
    }
    overviewBody.innerHTML = active.map(function (r) {
      return "<tr" + (r.status === "live" ? ' class="iv-row-live"' : "") + ">" +
        '<td class="fw-semibold">' + esc(r.candidate) + "</td>" +
        "<td>" + esc(r.role) + "</td>" +
        "<td>" + esc(r.date) + " &middot; " + esc(r.time) + "</td>" +
        "<td>" + r.answered + "/" + r.total_questions + " answered</td>" +
        "<td>" + statusBadge(r) + "</td>" +
        "<td>" + viewButton(r) + "</td></tr>";
    }).join("");
  }

  function renderSummary(summary) {
    if (!panelSummary) return;
    panelSummary.innerHTML =
      '<span class="me-3"><strong>' + summary.live + "</strong> live now</span>" +
      '<span class="me-3"><strong>' + summary.upcoming + "</strong> upcoming</span>" +
      '<span class="me-3"><strong>' + summary.today + "</strong> today</span>" +
      "<span><strong>" + summary.completed + "</strong> completed</span>";
  }

  function refresh() {
    fetch(cfg.listUrl, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data || !data.ok) return;
        renderTable(data.interviews || []);
        renderOverview(data.interviews || [], data.summary || {});
        renderSummary(data.summary || {});
        // Keep an open live interview up to date as new answers arrive.
        if (openInterviewId && modalEl && modalEl.classList.contains("show")) loadDetail(openInterviewId, true);
      })
      .catch(function () {});
  }

  function scoreChip(value) {
    if (value == null) return '<span class="text-muted">&mdash;</span>';
    var v = Number(value);
    var tone = v >= 7 ? "iv-chip-good" : v >= 5 ? "iv-chip-mid" : "iv-chip-low";
    return '<span class="iv-chip ' + tone + '">' + v.toFixed(1) + "</span>";
  }

  function renderDetail(d) {
    if (modalTitle) modalTitle.textContent = d.candidate + " — " + d.role;
    if (modalSub) {
      modalSub.textContent = d.email + (d.started_at ? " · started " + d.started_at : "") +
        (d.ended_at ? " · finished " + d.ended_at : d.status === "in_progress" ? " · in progress (updates live)" : "");
    }
    var html = "";

    // Single-use link status + reset (for candidates whose browser/computer failed mid-interview).
    if (d.status !== "completed") {
      html += '<div class="d-flex flex-wrap align-items-center gap-2 small mb-3 iv-link-status">' +
        '<i class="bi bi-shield-lock-fill text-warning"></i>' +
        (d.link_locked
          ? "<span>Interview link opened on " + esc(d.link_opened_at) + " and locked to that browser.</span>" +
            '<button type="button" class="btn-db-secondary btn-sm ms-auto" data-iv-reset="' + esc(d.id) + '">' +
            '<i class="bi bi-arrow-counterclockwise"></i> Reset link</button>'
          : "<span>Interview link not opened yet. It will lock to the first browser that opens the interview room.</span>") +
        "</div>";
    }

    if (d.evaluation) {
      var ev = d.evaluation;
      html += '<div class="iv-summary-card mb-4"><div class="d-flex flex-wrap align-items-center gap-3 mb-2">' +
        '<div class="iv-big-score">' + Number(ev.composite).toFixed(1) + '%<div class="small text-muted fw-normal">Interview score</div></div>';
      if (d.ranking) {
        html += '<div class="small"><div>Rank <strong>#' + esc(d.ranking.final_rank) + "</strong> · CV " + scoreText(d.ranking.cv_score) +
          " · Composite " + scoreText(d.ranking.composite) + "</div><div>AI verdict: <strong>" +
          esc(VERDICTS[d.ranking.verdict] || d.ranking.verdict || "—") + "</strong>" +
          (d.ranking.hr_override ? " · HR override: <strong>" + esc(VERDICTS[d.ranking.hr_override] || d.ranking.hr_override) + "</strong>" : "") +
          "</div></div>";
      }
      html += '</div><div class="d-flex flex-wrap gap-2 mb-2">' + FACTORS.map(function (f) {
        return '<span class="small text-muted">' + f[1] + " " + scoreChip(ev.averages[f[0]]) + "</span>";
      }).join("") + "</div>";
      if (ev.summary) html += '<p class="small mb-2">' + esc(ev.summary) + "</p>";
      if (ev.strengths && ev.strengths.length) {
        html += '<div class="small"><strong class="text-success">Strengths:</strong> ' + ev.strengths.map(esc).join("; ") + "</div>";
      }
      if (ev.weaknesses && ev.weaknesses.length) {
        html += '<div class="small"><strong class="text-danger">Weaknesses:</strong> ' + ev.weaknesses.map(esc).join("; ") + "</div>";
      }
      html += "</div>";
    } else {
      html += '<div class="alert alert-info small py-2">The overall evaluation appears when the candidate finishes all 3 stages. Answers below are scored as they come in.</div>';
    }

    d.stages.forEach(function (stage) {
      html += '<h3 class="h6 fw-bold mt-3 mb-2">Stage ' + stage.order + ": " + esc(STAGE_NAMES[stage.type] || stage.type) +
        ' <span class="small text-muted fw-normal">(' + esc(stage.status.replace("_", " ")) + ")</span></h3>";
      if (!stage.questions.length) {
        html += '<p class="small text-muted mb-2">Not started yet.</p>';
        return;
      }
      stage.questions.forEach(function (q) {
        html += '<div class="iv-q-card mb-2"><div class="fw-semibold small mb-1">Q' + q.number + ". " + esc(q.question) + "</div>";
        if (!q.answered) {
          html += '<div class="small text-muted">Not answered yet.</div></div>';
          return;
        }
        html += '<div class="iv-answer small mb-2">' + esc(q.transcript) + "</div>";
        if (q.audio_url) {
          html += '<audio controls preload="none" class="w-100 mb-2" src="' + esc(q.audio_url) + '"></audio>';
        }
        html += '<div class="d-flex flex-wrap gap-2 mb-1">' + FACTORS.map(function (f) {
          return '<span class="small text-muted">' + f[1] + " " + scoreChip(q.scores[f[0]]) + "</span>";
        }).join("") + (q.average != null ? '<span class="small ms-auto">Avg ' + scoreChip(q.average) + "</span>" : "") + "</div>";
        if (q.ai_rationale) html += '<div class="small text-muted"><i class="bi bi-robot me-1"></i>' + esc(q.ai_rationale) + "</div>";
        html += "</div>";
      });
    });
    modalBody.innerHTML = html;
  }

  function loadDetail(id, silent) {
    if (!modalBody) return;
    if (!silent) modalBody.innerHTML = '<div class="text-center text-muted py-5">Loading…</div>';
    var url = cfg.detailUrlTemplate.replace("00000000-0000-0000-0000-000000000001", id);
    fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.ok) {
          if (!silent) modalBody.innerHTML = '<div class="alert alert-danger small">' + esc(data.error || "Could not load interview.") + "</div>";
          return;
        }
        renderDetail(data.interview);
      })
      .catch(function () {
        if (!silent) modalBody.innerHTML = '<div class="alert alert-danger small">Network error while loading the interview.</div>';
      });
  }

  function csrfToken() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  document.addEventListener("click", function (event) {
    var resetBtn = event.target.closest("[data-iv-reset]");
    if (!resetBtn || !cfg.resetUrlTemplate) return;
    if (!window.confirm("Reset this candidate's interview link? They will be able to open it once more on any browser. Only do this if they lost access (e.g. their computer crashed).")) return;
    resetBtn.disabled = true;
    var id = resetBtn.getAttribute("data-iv-reset");
    fetch(cfg.resetUrlTemplate.replace("00000000-0000-0000-0000-000000000001", id), {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken(), Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        window.alert(data.ok ? data.message : (data.error || "Could not reset the link."));
        loadDetail(id, true);
      })
      .catch(function () {
        window.alert("Network error while resetting the link.");
        resetBtn.disabled = false;
      });
  });

  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-iv-view]");
    if (!btn) return;
    openInterviewId = btn.getAttribute("data-iv-view");
    loadDetail(openInterviewId, false);
    if (modal) modal.show();
  });
  if (modalEl) {
    modalEl.addEventListener("hidden.bs.modal", function () { openInterviewId = null; });
  }

  refresh();
  setInterval(refresh, REFRESH_MS);
});
