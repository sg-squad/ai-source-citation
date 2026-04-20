(function () {
  "use strict";

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }


  function highlightMatch(text, expected) {
    if (!text) return "";

    const safeText = escapeHtml(text);

    if (!expected) {
        return safeText;
    }

    const escapedExpected = expected
        .replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // escape regex chars

    const regex = new RegExp(`(${escapedExpected})`, "gi");

    return safeText.replace(regex, "<strong>$1</strong>");
    }

  function hasExpectedAnswerMatch(answerText, expectedAnswer) {
    if (!expectedAnswer) {
        return null;
    }

    if (!answerText) {
        return false;
    }

    const normalizedText = String(answerText).toLowerCase();
    const normalizedExpected = String(expectedAnswer).toLowerCase();

    return normalizedText.includes(normalizedExpected);
    }

  function renderExpectedAnswerStatus(result) {
    if (!result.expected_answer) {
        return `
        <p class="result-meta">
            <strong>Answer check:</strong> Not configured
        </p>
        `;
    }

    const found = hasExpectedAnswerMatch(result.answer_text || "", result.expected_answer);

    if (found) {
        return `
        <p class="result-meta">
            <strong>Answer check:</strong> <strong>Expected value found</strong>
        </p>
        `;
    }

    return `
        <div class="detail-block">
        <h3>Expected value not found</h3>
        <p class="code-like">${escapeHtml(result.expected_answer)}</p>
        </div>
    `;
    }  

  function renderList(items) {
    if (!items || items.length === 0) {
      return '<p class="empty-state">None</p>';
    }

    return `
      <ul class="chip-list">
        ${items.map((item) => `<li class="chip">${escapeHtml(item)}</li>`).join("")}
      </ul>
    `;
  }


  function renderUrlList(items) {
    if (!items || items.length === 0) {
      return '<p class="empty-state">None</p>';
    }

    return `
      <ul class="chip-list">
        ${items
          .map((item) => {
            const url = escapeHtml(item);
            return `<li class="chip"><a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a></li>`;
          })
          .join("")}
      </ul>
    `;
  }

  function renderCard(result) {
    const statusClass = result.status === "passed" ? "result-card--passed" : "result-card--failed";
    const citationLinksHtml = (() => {
      const links = result.citation_links || [];
      if (!links || !links.length) {
        return '<p class="empty-state">None</p>';
      }
      return `
        <ul class="chip-list">
          ${links
            .map((item) => {
              const url = escapeHtml(item.url || "");
              const healthLabel = item.status_code !== null && item.status_code !== undefined
                ? String(item.status_code)
                : (item.error ? `ERR: ${escapeHtml(item.error)}` : "ERR");
              const healthClass = item.is_ok
                ? "chip--health-ok"
                : (item.is_blocked ? "chip--health-blocked" : "chip--health-failed");
              const classes = `${item.matched ? "chip chip--matched" : "chip"} ${healthClass}`;
              return `<li class="${classes}"><a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a> <span class="chip-health">(${healthLabel})</span></li>`;
            })
            .join("")}
        </ul>
      `;
    })();

    const statusLabel = result.status === "passed" ? "PASS" : "FAIL";
    const reasonHtml = result.status === "failed"
      ? `<p><strong>Failure reason:</strong> ${escapeHtml(result.failure_reason || "check failed")}</p>`
      : "";

    return `
      <details class="result-card ${statusClass}">
        <summary class="result-summary">
          ${escapeHtml(statusLabel)} — ${escapeHtml(result.question || "Unnamed check")}
        </summary>

        <p class="result-meta">
          Provider: ${escapeHtml(result.provider || "")}
        </p>

        ${reasonHtml}
        ${renderExpectedAnswerStatus(result)}
        
        <div class="detail-grid">
          <section class="detail-block">
            <h3>Expected result</h3>
            <p class="code-like">${escapeHtml(result.expected_answer || "No expected answer configured")}</p>
          </section>

          <section class="detail-block">
            <h3>Actual answer text</h3>
            <p class="code-like">
                ${highlightMatch(result.answer_text || "", result.expected_answer)}
            </p>
          </section>

          <section class="detail-block">
            <h3>Expected sources</h3>
            ${renderList(result.expected_sources || [])}
          </section>

          <section class="detail-block">
            <h3>Matched sources</h3>
            ${renderList(result.matched_sources || [])}
          </section>

          <section class="detail-block">
            <h3>Expected URLs</h3>
            ${renderUrlList(result.expected_urls || [])}
          </section>

          <section class="detail-block">
            <h3>Matched URLs</h3>
            ${renderUrlList(result.matched_urls || [])}
          </section>

          <section class="detail-block">
            <h3>Missing URLs</h3>
            ${renderUrlList(result.missing_urls || [])}
          </section>

          <section class="detail-block">
            <h3>Citation domains</h3>
            ${renderList(result.citation_domains || [])}
          </section>

          <section class="detail-block">
            <h3>Citation URLs</h3>
            ${citationLinksHtml}
          </section>

          <section class="detail-block">
            <h3>Manual recreation</h3>
            <p>
              <a href="${escapeHtml(result.search_url)}" target="_blank" rel="noopener noreferrer">
                Launch this search in the browser
              </a>
            </p>
          </section>
        </div>
      </details>
    `;
  }

  function render() {
    const app = document.getElementById("app");
    const dataEl = document.getElementById("report-data");

    if (!app || !dataEl) {
      return;
    }

    const payload = JSON.parse(dataEl.textContent);
    const run = payload.run || {};
    const summary = payload.summary || {};
    const results = payload.results || [];

    const failures = results.filter((item) => item.status === "failed");
    const passes = results.filter((item) => item.status === "passed");

    app.innerHTML = `
      <header class="overview">
        <h1>AI Source Citation Test Report</h1>

        <div class="overview-grid">
          <div>
            <strong>Provider</strong><br>
            ${escapeHtml(run.provider || "unknown")}
          </div>
          <div>
            <strong>Timestamp</strong><br>
            ${escapeHtml(run.timestamp || "unknown")}
          </div>
        </div>

        <div class="metrics-grid" aria-label="Test result overview">
          <div class="metric">
            <div class="metric-label">Checks executed</div>
            <div class="metric-value">${escapeHtml(summary.checks_run ?? 0)}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Passes</div>
            <div class="metric-value">${escapeHtml(summary.checks_passed ?? 0)}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Failures</div>
            <div class="metric-value">${escapeHtml(summary.checks_failed ?? 0)}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Citations checked</div>
            <div class="metric-value">${escapeHtml(summary.total_citations_checked ?? 0)}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Healthy citations</div>
            <div class="metric-value">${escapeHtml(summary.healthy_citations ?? 0)}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Blocked citations</div>
            <div class="metric-value">${escapeHtml(summary.blocked_citations ?? 0)}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Failed citations</div>
            <div class="metric-value">${escapeHtml(summary.failed_citations ?? 0)}</div>
          </div>
        </div>
      </header>

      <section aria-labelledby="failures-heading">
        <h2 id="failures-heading" class="section-heading">Failures</h2>
        ${failures.length ? failures.map(renderCard).join("") : '<p class="empty-state">No failures.</p>'}
      </section>

      <section aria-labelledby="passes-heading">
        <h2 id="passes-heading" class="section-heading">Passes</h2>
        ${passes.length ? passes.map(renderCard).join("") : '<p class="empty-state">No passes.</p>'}
      </section>
    `;
  }

  render();
})();