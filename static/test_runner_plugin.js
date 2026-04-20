/* Swagger UI plugin: Run-all button + result panel per tag.
 *
 * Adds a "▶ Run all" button on each tag-section header. Clicking POSTs to
 * /api/v1/test-runner/run with the matching group key, then renders a results
 * table inside a <details> right under the tag section. Loads existing history
 * (GET /api/v1/test-runner/history?group=...) on initial render.
 *
 * Plugged via SwaggerUIBundle({plugins:[TestRunnerPlugin]}).
 */
(function () {
  if (window.TestRunnerPluginInstalled) return;
  window.TestRunnerPluginInstalled = true;

  const RUN_URL = "/api/v1/test-runner/run";
  const HISTORY_URL = "/api/v1/test-runner/history";

  function htmlEscape(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function renderReport(report) {
    if (!report || !report.results) {
      return `<div style="padding:8px;color:#999">Нет данных. Нажмите «▶ Run all».</div>`;
    }
    const s = report.summary || {};
    const totalRow =
      `<div style="margin:6px 0;font-weight:600">` +
      `Запуск: ${htmlEscape(report.started_at)} → ${htmlEscape(report.finished_at)} ` +
      `(${report.duration_s ?? "?"} с) | ` +
      `<span style="color:#28a745">${s.passed ?? 0} PASS</span> / ` +
      `<span style="color:#cc3333">${s.failed ?? 0} FAIL</span> ` +
      `из ${s.total ?? 0}` +
      `</div>`;

    const rows = report.results.map(r => {
      const cls = r.status === "PASS" ? "color:#28a745" : "color:#cc3333";
      const previewOrError = r.status === "PASS"
        ? `<code style="font-size:11px;background:#eef;padding:2px 4px">${htmlEscape((r.response_preview||"").slice(0,200))}</code>`
        : `<code style="font-size:11px;background:#fee;padding:2px 4px;color:#900">${htmlEscape((r.error||"").slice(0,300))}</code>`;
      return `<tr>` +
        `<td style="padding:4px 6px;font-family:monospace">${htmlEscape(r.scenario)}</td>` +
        `<td style="padding:4px 6px;font-family:monospace">${htmlEscape(r.method)} ${htmlEscape(r.path)}</td>` +
        `<td style="padding:4px 6px;text-align:right">${r.duration_ms ?? 0} мс</td>` +
        `<td style="padding:4px 6px;text-align:center"><b style="${cls}">${htmlEscape(r.status)}</b></td>` +
        `<td style="padding:4px 6px">${previewOrError}</td>` +
        `</tr>`;
    }).join("");

    return totalRow +
      `<table style="width:100%;border-collapse:collapse;font-size:13px;background:white">` +
      `<thead><tr style="background:#005566;color:white">` +
      `<th style="padding:6px;text-align:left">Сценарий</th>` +
      `<th style="padding:6px;text-align:left">Endpoint</th>` +
      `<th style="padding:6px;text-align:right">Длит.</th>` +
      `<th style="padding:6px;text-align:center">Результат</th>` +
      `<th style="padding:6px;text-align:left">Preview / Error</th>` +
      `</tr></thead><tbody>${rows}</tbody></table>`;
  }

  /** Map OpenAPI tag display name → settings.json group key.
   * Group keys in settings.json are unprefixed (e.g. "products"); but Smorest
   * tag names are blueprint titles like "products" or "characteristics" or for
   * BOM the pseudo-group "products-bom" (we don't have separate BOM tag, so we
   * route products-bom from any "products" tag — first match wins). For
   * simplicity, we prefer exact group match and fall back to a contains check.
   */
  function tagToGroupKey(tag, knownGroups) {
    const lower = (tag || "").toLowerCase().replace(/\s+/g, "-");
    if (knownGroups.includes(lower)) return lower;
    // partial: pick first known whose key is a substring of tag
    return knownGroups.find(g => lower.includes(g)) || null;
  }

  let cachedGroupKeys = null;
  function fetchGroupKeys() {
    if (cachedGroupKeys) return Promise.resolve(cachedGroupKeys);
    return fetch("/api/v1/test-runner/groups")
      .then(r => r.ok ? r.json() : {groups: {}})
      .then(j => { cachedGroupKeys = Object.keys(j.groups || {}); return cachedGroupKeys; })
      .catch(() => []);
  }

  function injectButtonInto(section, tagText, knownGroups) {
    if (section.querySelector(".test-runner-row")) return;
    const key = tagToGroupKey(tagText, knownGroups);
    if (!key) return;

    const row = document.createElement("div");
    row.className = "test-runner-row";
    row.style.cssText = "padding:8px 12px;background:#f8f9fa;border-top:1px solid #e8e8e8;border-bottom:1px solid #e8e8e8";
    row.innerHTML =
      `<button type="button" class="btn try-out__btn" style="background:#005566;color:white;border:none;padding:6px 14px;cursor:pointer;font-weight:600">` +
      `▶ Run all (${key})` +
      `</button>` +
      `<span class="test-runner-status" style="margin-left:12px;color:#666"></span>` +
      `<details class="test-runner-details" style="margin-top:8px"><summary style="cursor:pointer;color:#005566">Последний результат</summary>` +
      `<div class="test-runner-output" style="margin-top:8px">Загрузка истории…</div>` +
      `</details>`;

    section.appendChild(row);

    const btn = row.querySelector("button");
    const status = row.querySelector(".test-runner-status");
    const details = row.querySelector(".test-runner-details");
    const output = row.querySelector(".test-runner-output");

    // Load existing history
    fetch(`${HISTORY_URL}?group=${encodeURIComponent(key)}`)
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        if (j && j.results) output.innerHTML = renderReport(j);
        else output.innerHTML = `<div style="padding:8px;color:#999">Нет истории — нажмите «▶ Run all».</div>`;
      })
      .catch(() => { output.innerHTML = `<div style="color:#cc3333">Ошибка загрузки истории.</div>`; });

    btn.addEventListener("click", function () {
      btn.disabled = true;
      status.textContent = "Запуск…";
      details.open = true;
      output.innerHTML = `<div style="padding:8px;color:#999">Выполняется… (это может занять минуту)</div>`;
      fetch(RUN_URL, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({group: key}),
      })
        .then(r => r.json())
        .then(j => {
          output.innerHTML = renderReport(j);
          const s = j.summary || {};
          status.innerHTML = `<b style="color:${(s.failed||0)===0?'#28a745':'#cc3333'}">${s.passed||0}/${s.total||0} PASS</b>`;
          btn.disabled = false;
        })
        .catch(e => {
          output.innerHTML = `<div style="color:#cc3333;padding:8px">Ошибка: ${htmlEscape(e.message)}</div>`;
          status.textContent = "Ошибка";
          btn.disabled = false;
        });
    });
  }

  function scanAndInject() {
    fetchGroupKeys().then(keys => {
      // Each tag block in Swagger UI is .opblock-tag-section, the title is .opblock-tag span
      document.querySelectorAll(".opblock-tag-section").forEach(section => {
        // Find the tag name in the header
        const tagEl = section.querySelector(".opblock-tag a span") ||
                      section.querySelector(".opblock-tag span") ||
                      section.querySelector(".opblock-tag");
        const tag = tagEl ? tagEl.textContent.trim() : "";
        injectButtonInto(section, tag, keys);
      });
    });
  }

  // Re-scan whenever Swagger UI re-renders (DOM mutations)
  function observe() {
    const target = document.getElementById("swagger-ui-container") || document.body;
    const obs = new MutationObserver(() => scanAndInject());
    obs.observe(target, {childList: true, subtree: true});
    setTimeout(scanAndInject, 800);
  }

  // Plugin object for SwaggerUI presets
  window.TestRunnerPlugin = function () {
    return {
      statePlugins: {},
      afterLoad: function () { setTimeout(observe, 100); }
    };
  };

  // Also auto-init if loaded after Swagger UI mounted
  if (document.readyState === "complete" || document.readyState === "interactive") {
    setTimeout(observe, 1500);
  } else {
    document.addEventListener("DOMContentLoaded", () => setTimeout(observe, 1500));
  }
})();
