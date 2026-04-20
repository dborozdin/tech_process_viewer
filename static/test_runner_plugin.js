/* Swagger UI plugin: per-tag test runner with live updates + settings panel.
 *
 * Adds in each tag-section:
 *   • a status header (always visible) — group key + summary X/Y PASS/FAIL + duration
 *   • two buttons: «▶ Run all (group)» and «⚙ Settings»
 *   • <details> with results table (live-updating during run)
 *   • <details> with settings (db config + scenarios for this group)
 *
 * Reads NDJSON stream from POST /api/v1/test-runner/run-stream so each scenario
 * appears in the table as soon as it finishes.
 */
(function () {
  if (window.TestRunnerPluginInstalled) return;
  window.TestRunnerPluginInstalled = true;

  const RUN_STREAM_URL = "/api/v1/test-runner/run-stream";
  const HISTORY_URL    = "/api/v1/test-runner/history";
  const GROUPS_URL     = "/api/v1/test-runner/groups";

  const esc = s =>
    String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  function summaryHTML(passed, failed, total, durationS, started, finished) {
    const okColor = (failed || 0) > 0 ? "#cc3333" : "#28a745";
    const passS = passed != null ? passed : 0;
    const failS = failed != null ? failed : 0;
    const totS  = total  != null ? total  : 0;
    let extra = "";
    if (started && finished) extra = ` | ${esc(started)} → ${esc(finished)} (${durationS||0} с)`;
    else if (started) extra = ` | started ${esc(started)}`;
    return `<b style="color:${okColor};font-size:14px">${passS}/${totS} PASS</b>` +
           ` <span style="color:#cc3333">(${failS} FAIL)</span>` +
           `<span style="color:#666">${extra}</span>`;
  }

  function tableHeaderRow() {
    return `<thead><tr style="background:#005566;color:white">
      <th style="padding:6px;text-align:left">Сценарий</th>
      <th style="padding:6px;text-align:left">Endpoint</th>
      <th style="padding:6px;text-align:right">Длит.</th>
      <th style="padding:6px;text-align:center">Результат</th>
      <th style="padding:6px;text-align:left">Preview / Error</th>
    </tr></thead>`;
  }

  function rowHTML(r) {
    let cls, label;
    if (r.status === "PASS") { cls = "color:#28a745"; label = "PASS"; }
    else if (r.status === "FAIL") { cls = "color:#cc3333"; label = "FAIL"; }
    else if (r.status === "RUNNING") { cls = "color:#ff9800"; label = "▶ RUNNING"; }
    else { cls = "color:#999"; label = "PENDING"; }
    const rowBg = r.status === "RUNNING" ? "background:#fff7e6;" : "";
    const previewOrError = r.status === "PASS"
      ? `<code style="font-size:11px;background:#eef;padding:2px 4px">${esc((r.response_preview||"").slice(0,200))}</code>`
      : (r.status === "FAIL"
          ? `<code style="font-size:11px;background:#fee;padding:2px 4px;color:#900">${esc((r.error||"").slice(0,300))}</code>`
          : `<span style="color:#999">…</span>`);
    return `<tr style="${rowBg}">
      <td style="padding:4px 6px;font-family:monospace">${esc(r.scenario)}</td>
      <td style="padding:4px 6px;font-family:monospace">${esc(r.method||"")} ${esc(r.path||"")}</td>
      <td style="padding:4px 6px;text-align:right">${r.duration_ms != null ? r.duration_ms+" мс" : ""}</td>
      <td style="padding:4px 6px;text-align:center"><b style="${cls}">${label}</b></td>
      <td style="padding:4px 6px">${previewOrError}</td>
    </tr>`;
  }

  function renderFullReport(report) {
    if (!report || !report.results) return `<div style="padding:8px;color:#999">Нет данных.</div>`;
    const s = report.summary || {};
    const rows = report.results.map(rowHTML).join("");
    return `<table style="width:100%;border-collapse:collapse;font-size:13px;background:white">${tableHeaderRow()}<tbody>${rows}</tbody></table>`;
  }

  function normalize(s) {
    return (s || "").toLowerCase().replace(/[\s_]+/g, "-");
  }

  function matchingGroupKeys(tag, knownGroups) {
    const ntag = normalize(tag);
    const matches = [];
    for (const key of knownGroups) {
      const nkey = normalize(key);
      if (ntag === nkey || ntag.includes(nkey) || nkey.includes(ntag)) {
        matches.push(key);
      }
    }
    return matches;
  }

  let cachedGroups = null;  // { groups: {key:{title, scenarios:[id...]}}, db_target:{...} }
  function fetchGroups() {
    if (cachedGroups) return Promise.resolve(cachedGroups);
    return fetch(GROUPS_URL).then(r => r.ok ? r.json() : {groups:{}})
      .then(j => { cachedGroups = j; return j; })
      .catch(() => ({groups:{}}));
  }

  // Read NDJSON stream and emit each line as parsed object via callback.
  async function streamNDJSON(url, body, onEvent, onError) {
    let resp;
    try {
      resp = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body),
      });
    } catch (e) { onError && onError(e); return; }
    if (!resp.ok) { onError && onError(new Error("HTTP " + resp.status)); return; }
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      let idx;
      while ((idx = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, idx).trim();
        buf = buf.slice(idx+1);
        if (line) {
          try { onEvent(JSON.parse(line)); } catch (e) { /* ignore parse */ }
        }
      }
    }
    if (buf.trim()) {
      try { onEvent(JSON.parse(buf)); } catch (e) {}
    }
  }

  function renderSettings(meta, groupKey) {
    const g = (meta.groups || {})[groupKey] || {scenarios:[]};
    const db = meta.db_target || {};
    const dbBlock = `<div style="margin-bottom:8px"><b>Сервер БД:</b> <code>${esc(db.server_port||"")}</code> &nbsp;|&nbsp;
      <b>БД:</b> <code>${esc(db.db||"")}</code> &nbsp;|&nbsp;
      <b>Пользователь:</b> <code>${esc(db.user||"")}</code></div>`;
    const scList = (g.scenarios || []).map(sid => `<li><code>${esc(sid)}</code></li>`).join("");
    const scBlock = `<div><b>Сценарии (${(g.scenarios||[]).length}):</b><ol style="margin:4px 0 0 18px">${scList}</ol></div>`;
    const editBlock = `
      <div style="margin-top:12px;padding-top:10px;border-top:1px dashed #ccc">
        <div style="margin-bottom:4px"><b>✏ Редактирование группы (JSON)</b></div>
        <textarea class="trp-settings-edit" rows="14" style="width:100%;font-family:monospace;font-size:11px;padding:6px"
                  placeholder="Загрузка…">Загрузка…</textarea>
        <div style="margin-top:6px">
          <button type="button" class="trp-btn-save-settings" style="background:#28a745;color:white;border:none;padding:5px 12px;cursor:pointer">💾 Save</button>
          <button type="button" class="trp-btn-reset-settings" style="margin-left:6px;background:#666;color:white;border:none;padding:5px 12px;cursor:pointer">🔄 Reset</button>
          <span class="trp-save-status" style="margin-left:12px;font-size:12px"></span>
        </div>
      </div>
      <div style="margin-top:8px;font-size:12px"><a href="/openapi/test_API_settings.json" target="_blank">📋 Открыть полный test_API_settings.json</a></div>`;
    return dbBlock + scBlock + editBlock;
  }

  // Load full group_def from server and put into textarea
  function loadGroupIntoEditor(row, groupKey) {
    const ta = row.querySelector(".trp-settings-edit");
    const status = row.querySelector(".trp-save-status");
    if (!ta) return;
    fetch("/api/v1/test-runner/settings")
      .then(r => r.json())
      .then(s => {
        const gd = (s.groups || {})[groupKey];
        if (gd) {
          ta.value = JSON.stringify(gd, null, 2);
          status.innerHTML = "";
        } else {
          ta.value = "// group not found";
        }
      })
      .catch(e => { status.innerHTML = `<span style="color:#cc3333">Ошибка загрузки: ${esc(e.message||e)}</span>`; });
  }

  function saveGroupFromEditor(row, groupKey) {
    const ta = row.querySelector(".trp-settings-edit");
    const status = row.querySelector(".trp-save-status");
    let parsed;
    try {
      parsed = JSON.parse(ta.value);
    } catch (e) {
      status.innerHTML = `<span style="color:#cc3333">JSON.parse: ${esc(e.message)}</span>`;
      return;
    }
    if (!parsed || !Array.isArray(parsed.scenarios)) {
      status.innerHTML = `<span style="color:#cc3333">group_def должен иметь поле 'scenarios' (массив)</span>`;
      return;
    }
    status.innerHTML = `<span style="color:#666">Сохранение…</span>`;
    fetch("/api/v1/test-runner/settings", {
      method: "PUT",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({group: groupKey, group_def: parsed}),
    })
      .then(r => r.json().then(j => ({status: r.status, body: j})))
      .then(({status: s, body}) => {
        if (s === 200 && body.success) {
          status.innerHTML = `<span style="color:#28a745">✓ Сохранено (${body.groups_count} групп)</span>`;
          // invalidate cache so next Run uses new scenarios
          cachedGroups = null;
          fetchGroups();
        } else {
          status.innerHTML = `<span style="color:#cc3333">Ошибка ${s}: ${esc(body.message || JSON.stringify(body))}</span>`;
        }
      })
      .catch(e => { status.innerHTML = `<span style="color:#cc3333">Сетевая ошибка: ${esc(e.message||e)}</span>`; });
  }

  function injectInto(section, tagText, groupsMeta) {
    const knownGroups = Object.keys(groupsMeta.groups || {});
    const keys = matchingGroupKeys(tagText, knownGroups);
    if (!keys.length) return;
    // Inject one row per matching group key (skip those already injected)
    for (const k of keys) {
      if (section.querySelector(`.test-runner-row[data-group="${k}"]`)) continue;
      injectGroupRow(section, k, groupsMeta);
    }
  }

  function injectGroupRow(section, key, groupsMeta) {

    const row = document.createElement("div");
    row.className = "test-runner-row";
    row.setAttribute("data-group", key);
    row.style.cssText = "padding:10px 14px;background:#f8f9fa;border-top:1px solid #e8e8e8;border-bottom:1px solid #e8e8e8";
    row.innerHTML = `
      <div class="trp-summary" style="font-size:13px;margin-bottom:8px;color:#444">
        <span class="trp-summary-text" style="color:#999">Нет данных. Нажмите «▶ Run all».</span>
      </div>
      <button type="button" class="trp-btn-run" style="background:#005566;color:white;border:none;padding:6px 14px;cursor:pointer;font-weight:600">▶ Run all (${esc(key)})</button>
      <button type="button" class="trp-btn-settings" style="margin-left:8px;background:#666;color:white;border:none;padding:6px 12px;cursor:pointer">⚙ Settings</button>
      <span class="trp-progress" style="margin-left:12px;color:#666"></span>

      <details class="trp-details-results" style="margin-top:10px">
        <summary style="cursor:pointer;color:#005566;font-weight:600">📊 Результаты последнего прогона (раскрыть)</summary>
        <div class="trp-results" style="margin-top:8px;max-height:520px;overflow:auto"></div>
      </details>

      <details class="trp-details-settings" style="margin-top:6px">
        <summary style="cursor:pointer;color:#666">⚙ Параметры теста для этой группы</summary>
        <div class="trp-settings" style="margin-top:8px;padding:8px;background:white;border:1px solid #e8e8e8">${renderSettings(groupsMeta, key)}</div>
      </details>
    `;
    section.appendChild(row);

    const btnRun = row.querySelector(".trp-btn-run");
    const btnSettings = row.querySelector(".trp-btn-settings");
    const summaryEl = row.querySelector(".trp-summary-text");
    const progressEl = row.querySelector(".trp-progress");
    const detailsResults = row.querySelector(".trp-details-results");
    const resultsEl = row.querySelector(".trp-results");

    // Load history
    fetch(`${HISTORY_URL}?group=${encodeURIComponent(key)}`)
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        if (j && j.results) {
          const s = j.summary || {};
          summaryEl.innerHTML = summaryHTML(s.passed, s.failed, s.total, j.duration_s, j.started_at, j.finished_at);
          resultsEl.innerHTML = renderFullReport(j);
        }
      })
      .catch(() => {});

    btnSettings.addEventListener("click", () => {
      const det = row.querySelector(".trp-details-settings");
      det.open = !det.open;
      if (det.open) loadGroupIntoEditor(row, key);
    });

    // Wire Save / Reset (delegated since textarea is inside settings markup)
    row.addEventListener("click", (e) => {
      if (e.target.classList.contains("trp-btn-save-settings")) {
        saveGroupFromEditor(row, key);
      } else if (e.target.classList.contains("trp-btn-reset-settings")) {
        loadGroupIntoEditor(row, key);
      }
    });

    btnRun.addEventListener("click", async () => {
      btnRun.disabled = true;
      progressEl.textContent = "Запуск…";
      detailsResults.open = true;

      // Live state
      const live = {
        results: [],
        passed: 0,
        failed: 0,
        total: null,
        started_at: null,
      };

      // Initialize empty table; render scenarios as we know about them from groupsMeta
      const planned = (groupsMeta.groups[key].scenarios || []).map(sid =>
        ({scenario: sid, method: "", path: "", duration_ms: null, status: "PENDING", response_preview: "", error: ""}));
      live.total = planned.length;
      summaryEl.innerHTML = summaryHTML(0, 0, live.total, 0, "(running)", "");
      resultsEl.innerHTML = `<table style="width:100%;border-collapse:collapse;font-size:13px;background:white">${tableHeaderRow()}<tbody>${planned.map(rowHTML).join("")}</tbody></table>`;

      const tableBody = () => resultsEl.querySelector("table tbody");

      let updateRow = (idx, r) => {
        const tr = tableBody().children[idx];
        if (tr) {
          tr.outerHTML = rowHTML(r);
          // Scroll to the row for visibility
          const fresh = tableBody().children[idx];
          if (fresh && fresh.scrollIntoView) {
            fresh.scrollIntoView({block: "center", behavior: "smooth"});
          }
        }
      };

      await streamNDJSON(RUN_STREAM_URL, {group: key},
        (ev) => {
          if (ev.type === "start") {
            live.started_at = ev.started_at;
            live.total = ev.total;
            progressEl.innerHTML = `<b style="color:#005566">▶ ${ev.total} сценариев…</b>`;
            summaryEl.innerHTML = summaryHTML(0, 0, ev.total, 0, ev.started_at, "");
            // Mark first row as RUNNING
            if (planned[0]) {
              updateRow(0, {...planned[0], status: "RUNNING"});
            }
          } else if (ev.type === "step") {
            const i = ev.index - 1;
            updateRow(i, ev.step);
            if (ev.step.status === "PASS") live.passed++;
            else if (ev.step.status === "FAIL") live.failed++;
            progressEl.innerHTML =
              `<b style="color:${live.failed>0?'#cc3333':'#28a745'}">${live.passed+live.failed}/${ev.total}</b> ` +
              `(${live.passed} PASS, ${live.failed} FAIL)`;
            summaryEl.innerHTML = summaryHTML(live.passed, live.failed, ev.total, 0, live.started_at, "(running)");
            // Mark NEXT row as RUNNING (so the user sees progress)
            if (i + 1 < planned.length) {
              updateRow(i + 1, {...planned[i + 1], status: "RUNNING"});
            }
          } else if (ev.type === "end") {
            const rep = ev.report;
            const s = rep.summary || {};
            summaryEl.innerHTML = summaryHTML(s.passed, s.failed, s.total, rep.duration_s, rep.started_at, rep.finished_at);
            resultsEl.innerHTML = renderFullReport(rep);
            progressEl.innerHTML = `<b style="color:${(s.failed||0)>0?'#cc3333':'#28a745'}">Готово: ${s.passed||0}/${s.total||0} PASS</b>`;
          }
        },
        (err) => {
          progressEl.innerHTML = `<b style="color:#cc3333">Ошибка: ${esc(err.message||err)}</b>`;
        });

      btnRun.disabled = false;
    });
  }

  function scanAndInject() {
    fetchGroups().then(meta => {
      document.querySelectorAll(".opblock-tag-section").forEach(section => {
        const tagEl = section.querySelector(".opblock-tag a span") ||
                      section.querySelector(".opblock-tag span") ||
                      section.querySelector(".opblock-tag");
        const tag = tagEl ? tagEl.textContent.trim() : "";
        injectInto(section, tag, meta);
      });
    });
  }

  function observe() {
    const target = document.getElementById("swagger-ui-container") || document.body;
    const obs = new MutationObserver(() => scanAndInject());
    obs.observe(target, {childList: true, subtree: true});
    setTimeout(scanAndInject, 800);
  }

  window.TestRunnerPlugin = function () {
    return {
      statePlugins: {},
      afterLoad: function () { setTimeout(observe, 100); }
    };
  };

  if (document.readyState === "complete" || document.readyState === "interactive") {
    setTimeout(observe, 1500);
  } else {
    document.addEventListener("DOMContentLoaded", () => setTimeout(observe, 1500));
  }
})();
