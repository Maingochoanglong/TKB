"use strict";
// Giao diện xếp TKB: soạn kịch bản (tkb/kich_ban.py), kiểm tra, tải file Excel, xếp TKB qua máy chủ trên máy này.
// Các ô nhập sinh từ /api/schema (tkb/rules.py), nên quy định mới thêm ở rules.py tự có ô ở đây.

const TOKEN = window.TKB_TOKEN;
const DRAFT_KEY = "tkb-ban-nhap-v1";
const TAB_KEY = "tkb-tab";
let S = null; // schema từ máy chủ
let st = null; // {scenario, run, label}
let poller = null;
let logNext = 0;
let stopAt = 0;

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---------------------------------------------------------------- máy chủ, bản nháp, thông báo
async function api(method, path, body, opts = {}) {
  const headers = { "X-TKB-Token": TOKEN, ...(opts.headers || {}) };
  let payload = body;
  if (body !== undefined && !(body instanceof ArrayBuffer)) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, { method, headers, body: payload });
  } catch {
    throw new Error("Không kết nối được chương trình: cửa sổ chạy giao diện đã đóng? Mở lại rồi tải lại trang.");
  }
  if (opts.blob && res.ok) return res.blob();
  let data;
  try { data = await res.json(); } catch { data = { error: `Lỗi ${res.status}` }; }
  if (!res.ok) throw new Error(data.error || `Lỗi ${res.status}`);
  return data;
}

function saveDraft() {
  try { localStorage.setItem(DRAFT_KEY, JSON.stringify(st)); } catch { /* không lưu được bản nháp: bỏ qua */ }
}
let saveTimer = null;
function changed() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveDraft, 300);
  updateCounts();
}
function loadDraft() {
  try { return JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); } catch { return null; }
}

function notify(html, kind = "", action = null) {
  const box = $("#notice");
  box.className = `notice ${kind}`;
  box.innerHTML = `<div>${html}</div><div class="actions"></div>`;
  if (action) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost";
    b.textContent = action.label;
    b.onclick = () => { box.hidden = true; action.fn(); };
    $(".actions", box).append(b);
  }
  const close = document.createElement("button");
  close.type = "button";
  close.className = "icon";
  close.title = "Đóng";
  close.textContent = "✕";
  close.onclick = () => { box.hidden = true; };
  $(".actions", box).append(close);
  box.hidden = false;
}
const fail = (err) => notify(esc(err.message || err), "error");

// ---------------------------------------------------------------- ô nhập theo loại ô
// Loại ô: yes (Có/Không), int / order (số nguyên dương), text, role (chức vụ).
function input(kind, value, attrs, cls = "") {
  const a = Object.entries(attrs).map(([k, v]) => `data-${k}="${esc(v)}"`).join(" ");
  if (kind === "yes") return `<input type="checkbox" ${a} ${value ? "checked" : ""}>`;
  if ((kind === "int" || kind === "order") && (value === null || value === undefined || typeof value === "number")) {
    return `<input type="number" min="0" step="1" ${a} value="${esc(value)}" class="${cls}">`;
  }
  const list = kind === "role" ? 'list="role-list"' : "";
  return `<input type="text" ${a} ${list} value="${esc(value)}" class="${cls}" spellcheck="false">`;
}
function readInput(el) {
  if (el.type === "checkbox") return el.checked;
  if (el.type === "number") {
    if (el.value === "") return null;
    const n = Number(el.value);
    return Number.isInteger(n) ? n : el.value;
  }
  return el.value;
}
const colTitle = (c) => `title="${esc(c.note)}"`;

// ---------------------------------------------------------------- tab 1: khung giờ, quy định chung
function renderGeneral() {
  const g = st.scenario.general;
  $("#general-form").innerHTML = S.general.map((c) => `
    <label class="gen-row"><span>${esc(c.header)}</span>
      <span class="val">${input(c.kind, g[c.key], { f: "general", k: c.key })}</span>
      <small>${esc(c.note)}</small></label>`).join("");
}

function renderDays() {
  const days = st.scenario.days;
  const head = `<thead><tr><th class="left">Ngày</th>${S.day.map((c) => `<th ${colTitle(c)}>${esc(c.header)}</th>`).join("")}</tr></thead>`;
  const body = S.days.map((name, d) => `<tr><td class="left">${esc(name)}</td>${S.day.map((c) =>
    `<td>${input(c.kind, (days[d] || {})[c.key], { f: "day", i: d, k: c.key })}</td>`).join("")}</tr>`).join("");
  $("#day-table").innerHTML = head + `<tbody>${body}</tbody>`;
}

function periodCount() {
  const g = st.scenario.general;
  const m = Number.isInteger(g.morning_periods) ? g.morning_periods : 0;
  const a = Number.isInteger(g.afternoon_periods) ? g.afternoon_periods : 0;
  return { m, total: m + a };
}
function syncPeriods() {
  const { total } = periodCount();
  const rows = st.scenario.periods;
  if (total <= 0 || total > 15) return;
  while (rows.length < total) rows.push(Object.fromEntries(S.period.map((c) => [c.key, c.kind === "yes" ? false : null])));
  rows.length = total;
}
function renderPeriods() {
  const { m } = periodCount();
  const head = `<thead><tr><th>Tiết</th><th>Buổi</th>${S.period.map((c) => `<th ${colTitle(c)}>${esc(c.header)}</th>`).join("")}</tr></thead>`;
  const body = st.scenario.periods.map((row, i) => `<tr><td class="num">${i + 1}</td><td>${i < m ? "Sáng" : "Chiều"}</td>${
    S.period.map((c) => `<td>${input(c.kind, row[c.key], { f: "period", i, k: c.key })}</td>`).join("")}</tr>`).join("");
  $("#period-table").innerHTML = head + `<tbody>${body}</tbody>`;
}

// ---------------------------------------------------------------- tab 2: môn học
const subjectKept = (s) => String(s.name || "").trim() !== "" ||
  Object.values(s.lessons || {}).some((v) => v !== null && v !== "");
function subjectRowNumbers() { // số dòng trong sheet CHƯƠNG TRÌNH HỌC của file Excel (dòng 1 là tiêu đề)
  let r = 1;
  return st.scenario.subjects.map((s) => (subjectKept(s) ? ++r : null));
}
function renderSubjects() {
  const sc = st.scenario;
  const nums = subjectRowNumbers();
  const head = `<thead><tr><th>Dòng</th><th class="left stick">Môn học</th>${
    sc.grades.map((g) => `<th class="group-grade">Khối ${esc(g)}</th>`).join("")}${
    S.subject.map((c) => `<th ${colTitle(c)}>${esc(c.header)}</th>`).join("")}<th></th></tr></thead>`;
  const body = sc.subjects.map((s, i) => `<tr data-row="${nums[i] ?? ""}">
    <td class="num">${nums[i] ?? "—"}</td>
    <td class="left stick">${input("text", s.name, { f: "subject", i, k: "name" }, "wide")}</td>
    ${sc.grades.map((g) => `<td>${input("int", (s.lessons || {})[g], { f: "lessons", i, k: g })}</td>`).join("")}
    ${S.subject.map((c) => `<td>${input(c.kind, (s.rules || {})[c.key], { f: "rule", i, k: c.key })}</td>`).join("")}
    <td><button type="button" class="icon" data-act="del-subject" data-i="${i}" title="Xóa môn">✕</button></td></tr>`).join("");
  $("#subject-table").innerHTML = head + `<tbody>${body}</tbody>`;
  renderRoleList();
}
function refreshSubjectNumbers() {
  const nums = subjectRowNumbers();
  $$("#subject-table tbody tr").forEach((tr, i) => {
    tr.dataset.row = nums[i] ?? "";
    tr.cells[0].textContent = nums[i] ?? "—";
  });
}
function newSubjectRules() {
  return Object.fromEntries(S.subject.map((c) => [c.key, c.kind === "yes" ? false : c.kind === "text" ? "" : null]));
}

// ---------------------------------------------------------------- tab 3: giáo viên
function renderRoleList() {
  const names = st.scenario.subjects.map((s) => String(s.name || "").trim()).filter(Boolean);
  $("#role-list").innerHTML = [...new Set([...S.roles, ...names])].map((r) => `<option value="${esc(r)}">`).join("");
  $("#subject-list").innerHTML = [...new Set(names)].map((r) => `<option value="${esc(r)}">`).join("");
  $("#session-list").innerHTML = S.custom.sessions.map((r) => `<option value="${esc(r)}">`).join("");
}
function renderStaff() {
  const head = `<thead><tr><th>Dòng</th>${S.staff.map((c, j) =>
    `<th ${colTitle(c)} class="${j === 0 ? "left stick" : ""}">${esc(c.header)}</th>`).join("")}<th></th></tr></thead>`;
  const body = st.scenario.staff.map((t, i) => `<tr data-row="${i + 2}"><td class="num">${i + 2}</td>${
    S.staff.map((c, j) => `<td class="${j === 0 ? "left stick" : ""}">${
      input(c.kind, t[c.key], { f: "staff", i, k: c.key }, j === 0 ? "wide" : "")}</td>`).join("")}
    <td class="nowrap">
      <button type="button" class="icon" data-act="up" data-i="${i}" title="Lên">↑</button>
      <button type="button" class="icon" data-act="down" data-i="${i}" title="Xuống">↓</button>
      <button type="button" class="icon" data-act="del-staff" data-i="${i}" title="Xóa dòng">✕</button></td></tr>`).join("");
  $("#staff-table").innerHTML = head + `<tbody>${body}</tbody>`;
  updateCounts();
}
function newStaffRow() {
  return Object.fromEntries(S.staff.map((c) => [c.key, c.kind === "yes" ? false : c.kind === "int" ? null : ""]));
}
const isHomeroom = (t) => String(t.role || "").trim().toLowerCase() === S.roles[0].toLowerCase();
function updateCounts() {
  if (!st) return;
  const staff = st.scenario.staff.filter((t) => String(t.name || "").trim() || String(t.role || "").trim());
  const subjects = st.scenario.subjects.filter((s) => String(s.name || "").trim());
  $("#count-gv").textContent = staff.length || "";
  $("#count-mon").textContent = subjects.length || "";
  $("#count-luat").textContent = (st.scenario.custom || []).length || "";
  const classes = staff.filter(isHomeroom).length;
  const quota = staff.reduce((n, t) => n + (Number.isInteger(t.lessons) ? t.lessons : 0), 0);
  $("#staff-summary").textContent = `${staff.length} người, ${classes} lớp (mỗi Chủ Nhiệm một lớp), tổng định mức ` +
    `${quota} tiết/tuần. Chức Vụ: ${S.roles.join(", ")} hoặc đúng tên một môn (GV chuyên biệt); không ghi số thứ tự.`;
}

// Dán từ Excel: các cột theo thứ tự của sheet NHÂN SỰ, cách nhau bằng Tab.
function parsePasted(text) {
  const yes = (v) => ["có", "co", "x", "1", "true", "yes", "c"].includes(String(v).trim().toLowerCase());
  const rows = [];
  for (const line of text.replace(/\r/g, "").split("\n")) {
    if (!line.trim()) continue;
    const cells = line.split("\t");
    if (cells[0].trim().toLowerCase() === S.staff[0].header.toLowerCase()) continue; // dòng tiêu đề
    const row = newStaffRow();
    S.staff.forEach((c, j) => {
      const v = (cells[j] ?? "").trim();
      if (c.kind === "yes") row[c.key] = yes(v);
      else if (c.kind === "int") row[c.key] = v === "" ? null : (/^\d+$/.test(v) ? Number(v) : v);
      else row[c.key] = v;
    });
    rows.push(row);
  }
  return rows;
}

// ---------------------------------------------------------------- tab 4: luật riêng
// Mỗi dòng một luật thuộc một kiểu luật chung (tkb/luat_rieng.py); ô nào kiểu luật không dùng thì khóa.
const kindOf = (row) => S.custom.kinds.find((k) => k.label === row.kind || k.key === row.kind) || S.custom.kinds[0];
const RULE_INPUT = {
  subject: (v, a) => `<input type="text" list="subject-list" class="wide" ${a} value="${esc(v)}" spellcheck="false">`,
  other: (v, a) => `<input type="text" list="subject-list" class="wide" ${a} value="${esc(v)}" spellcheck="false">`,
  sessions: (v, a) => `<input type="text" list="session-list" ${a} value="${esc(v)}" spellcheck="false">`,
  role: (v, a) => `<input type="text" list="role-list" class="wide" ${a} value="${esc(v)}" spellcheck="false">`,
  number: (v, a) => `<input type="number" min="1" step="1" ${a} value="${esc(v)}">`,
};
function describeRule(row) {
  const k = kindOf(row).key;
  const who = (row.subject || "…") + (row.grades ? ` khối ${row.grades}` : "");
  const where = [row.sessions && `buổi ${String(row.sessions).toLowerCase()}`, row.days,
    row.periods && `tiết ${row.periods}`].filter(Boolean).join(" ") || "…";
  const text = {
    khong_xep: `${who} không xếp vào ${where}`,
    chi_xep: `${who} chỉ xếp vào ${where}`,
    lien_2: `${who} học 2 tiết liền`,
    truoc: `${who} học trước ${row.other || "…"} trong buổi`,
    gv_ngay: `${row.role ? `mỗi GV ${row.role}` : "mỗi giáo viên"} dạy tối đa ${row.number || "…"} tiết mỗi ngày`,
    cung_luc: `${who}: tối đa ${row.number || "…"} lớp học cùng lúc`,
  }[k];
  return text + (row.hard ? " (bắt buộc)" : ` (ưu tiên mức ${row.level || 2})`);
}
function renderRules() {
  const rows = st.scenario.custom;
  const cols = S.custom.columns.filter((c) => !["kind", "hard", "level"].includes(c.key));
  const head = `<thead><tr><th>Dòng</th><th class="left">Luật đọc là</th><th class="left">Kiểu luật</th>${
    cols.map((c) => `<th>${esc(c.header)}</th>`).join("")}<th>Bắt buộc</th><th>Mức</th><th></th></tr></thead>`;
  const body = rows.map((row, i) => {
    const kind = kindOf(row);
    const cells = cols.map((c) => {
      const a = `data-f="rulec" data-i="${i}" data-k="${c.key}" ${kind.uses.includes(c.key) ? "" : "disabled"}`;
      const make = RULE_INPUT[c.key] || ((v, at) => `<input type="text" ${at} value="${esc(v)}" spellcheck="false">`);
      return `<td>${make(row[c.key] ?? "", a)}</td>`;
    }).join("");
    const levels = [1, 2, 3].map((n) => `<option value="${n}" ${Number(row.level || 2) === n ? "selected" : ""}>${n}</option>`).join("");
    return `<tr data-row="${i + 2}"><td class="num">${i + 2}</td>
      <td class="say">${esc(describeRule(row))}</td>
      <td class="left"><select data-f="rulec" data-i="${i}" data-k="kind">${S.custom.kinds.map((k) =>
        `<option value="${esc(k.label)}" ${k.key === kind.key ? "selected" : ""}>${esc(k.label)}</option>`).join("")}</select></td>
      ${cells}
      <td><input type="checkbox" data-f="rulec" data-i="${i}" data-k="hard" ${row.hard ? "checked" : ""}></td>
      <td><select data-f="rulec" data-i="${i}" data-k="level" ${row.hard ? "disabled" : ""}>${levels}</select></td>
      <td><button type="button" class="icon" data-act="del-rule" data-i="${i}" title="Xóa luật">✕</button></td></tr>`;
  }).join("");
  $("#rule-table").innerHTML = rows.length ? head + `<tbody>${body}</tbody>` : "";
  $("#rule-empty").hidden = rows.length > 0;
  updateCounts();
}
function newRule(label) {
  const row = Object.fromEntries(S.custom.columns.map((c) => [c.key, ""]));
  return { ...row, kind: label, number: null, hard: true, level: null };
}

// ---------------------------------------------------------------- tab 5: cài đặt chạy, kiểm tra, xếp
function renderRun() {
  const run = st.run;
  $("#mode-options").innerHTML = S.modes.map((m) => `<label class="mode">
    <input type="radio" name="mode" value="${esc(m.key)}" data-run="mode" ${run.mode === m.key ? "checked" : ""}>
    <span><b>${esc(m.label)}</b><small>${esc(m.note)}</small></span></label>`).join("");
  $$("[data-run]").forEach((el) => {
    const k = el.dataset.run;
    if (k === "mode") return;
    if (k === "time_preset") {
      el.value = ["600", "1200", "0"].includes(String(run.time_limit)) ? String(run.time_limit) : "custom";
      return;
    }
    if (el.type === "checkbox") el.checked = !!run[k];
    else el.value = run[k] ?? "";
  });
  $('[data-run="time_limit"]').hidden = $('[data-run="time_preset"]').value !== "custom";
  $("#saved-hint").textContent = st.scenario.saved
    ? "— file vào có sheet TKB đã xếp" : "— file vào chưa có TKB đã xếp";
  $("#out-dir").value = S.out_dir;
}

function jumpTo(sheet, row) {
  const [tab, table] = sheet === S.sheets.staff ? ["gv", "staff"] : sheet === S.sheets.custom ? ["luat", "rule"]
    : ["mon", "subject"];
  showTab(tab);
  const tr = $(`#${table}-table tr[data-row="${row}"]`);
  if (!tr) return;
  tr.scrollIntoView({ block: "center", behavior: "smooth" });
  tr.classList.remove("flash");
  void tr.offsetWidth;
  tr.classList.add("flash");
}
function msgItem(text, cls) {
  const m = text.match(new RegExp(`(${S.sheets.staff}|${S.sheets.program}|${S.sheets.custom})[:,]? *(?:[Dd]òng (\\d+)|.*?[Dd]òng (\\d+))`));
  const body = m ? `<a href="#" data-jump="${esc(m[1])}|${m[2] || m[3]}">${esc(text)}</a>` : esc(text);
  return `<li class="${cls}">${body}</li>`;
}
function renderCheck(res) {
  const items = [];
  if (!res.errors.length) items.push(`<li class="ok">Kịch bản hợp lệ, xếp TKB được.</li>`);
  items.push(...res.errors.map((t) => msgItem(t, "err")));
  items.push(...res.warnings.map((t) => msgItem(t, "warn")));
  items.push(...res.info.map((t) => `<li class="info">${esc(t)}</li>`));
  $("#check-result").innerHTML = `<ul class="msgs">${items.join("")}</ul>`;
}
async function check() {
  $("#check-result").innerHTML = `<div class="status"><span class="spinner"></span>Đang kiểm tra…</div>`;
  const res = await api("POST", "/api/check", { scenario: st.scenario, run: st.run });
  renderCheck(res);
  return res;
}

const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
function setRunning(on) {
  $("#btn-run").disabled = on;
  $("#btn-check").disabled = on;
  $("#btn-stop").hidden = !on;
  if (!on) $("#btn-kill").hidden = true;
}
async function startRun() {
  const res = await check();
  if (res.errors.length) {
    notify("Kịch bản còn lỗi (xem phần Kiểm tra): sửa rồi bấm Xếp TKB lại.", "error");
    return;
  }
  await api("POST", "/api/run", { scenario: st.scenario, run: st.run });
  $("#log").textContent = "";
  $("#run-result").innerHTML = "";
  logNext = 0;
  stopAt = 0;
  startPolling();
}
function startPolling() {
  setRunning(true);
  $("#log-card").hidden = false;
  $("#run-status").hidden = false;
  clearInterval(poller);
  poller = setInterval(pollOnce, 1000);
  pollOnce();
}
async function pollOnce() {
  let s;
  try { s = await api("GET", `/api/status?since=${logNext}`); } catch (err) { clearInterval(poller); fail(err); return; }
  const log = $("#log");
  if (s.lines.length) {
    const atEnd = log.scrollTop + log.clientHeight >= log.scrollHeight - 30;
    log.textContent += s.lines.join("\n") + "\n";
    if (atEnd) log.scrollTop = log.scrollHeight;
  }
  logNext = s.next;
  const last = log.textContent.trim().split("\n").filter((l) => l.trim()).pop() || "";
  $("#log-info").textContent = s.elapsed !== undefined ? `${mmss(s.elapsed)}` : "";
  if (s.running) {
    const what = s.stopping ? "Đang dừng: chờ xếp xong vùng đang xếp rồi ghi TKB tốt nhất…" : "Đang xếp TKB…";
    $("#run-status").innerHTML = `<span class="spinner"></span><div><b>${what}</b> ${mmss(s.elapsed)}<br><small>${esc(last)}</small></div>`;
    if (s.stopping && stopAt && Date.now() - stopAt > 15000) $("#btn-kill").hidden = false;
    return;
  }
  clearInterval(poller);
  setRunning(false);
  $("#run-status").hidden = true;
  if (s.exit !== null) renderResult(s);
}
function renderResult(s) {
  const sum = s.summary || { files: [] };
  const titles = {
    0: ["Đã xếp xong TKB, đạt mọi luật bắt buộc.", "good"],
    2: ["Đã xếp TKB nhưng còn vi phạm luật bắt buộc (xem nhật ký).", "bad"],
    3: ["Chế độ bù giờ không đủ tiết: không ra TKB. Bảng tiết thiếu ở file thống kê; tăng số tiết bù tối đa, sửa nhân sự hoặc chọn Tuyển thêm.", "bad"],
  };
  const [title, cls] = titles[s.exit] || [s.stopping ? "Đã dừng trước khi có TKB." : "Không xếp được TKB.", "bad"];
  const files = sum.files.map((p) => {
    const name = p.split(/[\\/]/).pop();
    return `<li><span>${esc(name)}</span><span class="actions">
      <button type="button" class="ghost" data-act="open" data-path="${esc(p)}">Mở</button>
      <a class="btn ghost" href="/api/file?path=${encodeURIComponent(p)}&t=${encodeURIComponent(TOKEN)}">Tải</a>
      ${/_cap_nhat\.xlsx$/i.test(name) ? `<button type="button" class="ghost" data-act="load" data-path="${esc(p)}" title="Mở file vào cập nhật (có người cần tuyển, TKB đã xếp) để sửa tiếp">Nạp vào giao diện</button>` : ""}
      </span></li>`;
  }).join("");
  $("#run-result").innerHTML = `<div class="result ${cls}">
    <b>${esc(title)}</b>
    ${sum.error ? `<pre class="errbox">${esc(sum.error.replace(/^LỖI: /, ""))}</pre>` : ""}
    ${sum.code ? `<div>Mã kết quả <span class="big">${esc(sum.code)}</span><br><small>Cùng mã là cùng TKB (chạy lại với cùng file vào và cài đặt).</small></div>` : ""}
    ${files ? `<ul class="files">${files}</ul>` : ""}
    <div class="actions"><button type="button" class="ghost" data-act="open" data-path="">Mở thư mục kết quả</button></div>
  </div>`;
}

// ---------------------------------------------------------------- dựng cả trang
function renderHelp() {
  const dl = (cols) => cols.map((c) => `<dt>${esc(c.header)}</dt><dd>${esc(c.note)}</dd>`).join("");
  $("#help-khung").innerHTML = dl([...S.general, ...S.day, ...S.period]);
  $("#help-mon").innerHTML = dl(S.subject);
  $("#help-gv").innerHTML = dl(S.staff);
  $("#paste-cols").textContent = S.staff.map((c) => c.header).join(" | ");
  $("#kind-list").innerHTML = S.custom.kinds.map((k) => `<dt>${esc(k.label)}</dt><dd>${esc(k.note)}</dd>`).join("");
  $("#new-kind").innerHTML = S.custom.kinds.map((k) => `<option value="${esc(k.label)}">${esc(k.label)}</option>`).join("");
}
function renderAll() {
  syncPeriods();
  renderGeneral();
  renderDays();
  renderPeriods();
  renderSubjects();
  renderStaff();
  renderRules();
  renderRun();
  $("#file-label").textContent = st.label || "Kịch bản mới";
  updateCounts();
}
function showTab(name) {
  $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${name}`));
  try { localStorage.setItem(TAB_KEY, name); } catch { /* bỏ qua */ }
}

async function newScenario(ask = true) {
  if (ask && !confirm("Bỏ kịch bản đang làm và tạo kịch bản mới (quy định mặc định, chưa có nhân sự)?")) return;
  const data = await api("GET", "/api/new");
  st = { scenario: data.scenario, run: { ...S.run_defaults }, label: "Kịch bản mới" };
  renderAll();
  changed();
}
function useImported(data, label) {
  st = { scenario: data.scenario, run: { ...S.run_defaults, ...(st ? st.run : {}), name: data.name }, label };
  renderAll();
  changed();
  const warns = data.warnings.map((w) => `<li>${esc(w)}</li>`).join("");
  notify(`Đã mở ${esc(label)}: ${st.scenario.staff.length} dòng nhân sự, ${st.scenario.subjects.length} môn.` +
    (st.scenario.saved ? " File có sheet TKB đã xếp: xếp lại sẽ giữ TKB đó nếu vẫn đúng luật." : "") +
    (warns ? `<ul>${warns}</ul>` : ""), warns ? "" : "ok");
}

// ---------------------------------------------------------------- sự kiện
function onEdit(e) {
  const el = e.target;
  const d = el.dataset;
  if (!d.f && !d.run) return;
  if (d.run) {
    const k = d.run;
    if (k === "time_preset") {
      if (el.value !== "custom") st.run.time_limit = Number(el.value);
      $('[data-run="time_limit"]').hidden = el.value !== "custom";
    } else if (k === "mode") {
      st.run.mode = el.value;
    } else {
      st.run[k] = readInput(el);
    }
    changed();
    return;
  }
  const sc = st.scenario;
  const v = readInput(el);
  const i = Number(d.i);
  if (d.f === "general") {
    sc.general[d.k] = v;
    if ((d.k === "morning_periods" || d.k === "afternoon_periods") && e.type === "change") {
      syncPeriods();
      renderPeriods();
    }
  } else if (d.f === "day") {
    sc.days[i][d.k] = v;
  } else if (d.f === "period") {
    sc.periods[i][d.k] = v;
  } else if (d.f === "subject") {
    sc.subjects[i].name = v;
    if (e.type === "change") { refreshSubjectNumbers(); renderRoleList(); }
  } else if (d.f === "lessons") {
    sc.subjects[i].lessons[d.k] = v;
    if (e.type === "change") refreshSubjectNumbers();
  } else if (d.f === "rule") {
    sc.subjects[i].rules[d.k] = v;
  } else if (d.f === "staff") {
    sc.staff[i][d.k] = v;
  } else if (d.f === "rulec") {
    const row = sc.custom[i];
    row[d.k] = d.k === "level" ? Number(v) : v;
    if (d.k === "kind" || d.k === "hard") {
      const kind = kindOf(row);
      for (const c of S.custom.columns) {
        if (!["kind", "hard", "level"].includes(c.key) && !kind.uses.includes(c.key)) row[c.key] = c.key === "number" ? null : "";
      }
      row.level = row.hard ? null : (row.level || 2);
      if (e.type === "change") renderRules();
    } else {
      el.closest("tr").querySelector("td.say").textContent = describeRule(row);
    }
  }
  changed();
}

async function onClick(e) {
  const jump = e.target.closest("[data-jump]");
  if (jump) {
    e.preventDefault();
    const [sheet, row] = jump.dataset.jump.split("|");
    jumpTo(sheet, row);
    return;
  }
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const sc = st.scenario;
  const i = Number(btn.dataset.i);
  switch (btn.dataset.act) {
    case "del-subject":
      if (!confirm(`Xóa môn "${sc.subjects[i].name || "(chưa đặt tên)"}"?`)) return;
      sc.subjects.splice(i, 1);
      renderSubjects();
      break;
    case "del-staff":
      sc.staff.splice(i, 1);
      renderStaff();
      break;
    case "del-rule":
      sc.custom.splice(i, 1);
      renderRules();
      break;
    case "up":
    case "down": {
      const j = btn.dataset.act === "up" ? i - 1 : i + 1;
      if (j < 0 || j >= sc.staff.length) return;
      [sc.staff[i], sc.staff[j]] = [sc.staff[j], sc.staff[i]];
      renderStaff();
      $(`#staff-table [data-act="${btn.dataset.act}"][data-i="${j}"]`)?.focus();
      break;
    }
    case "open":
      await api("POST", "/api/open", { path: btn.dataset.path }).catch(fail);
      return;
    case "load":
      if (!confirm("Nạp file vào cập nhật vào giao diện (thay kịch bản đang soạn)?")) return;
      try {
        const data = await api("POST", "/api/import_path", { path: btn.dataset.path });
        useImported(data, btn.dataset.path.split(/[\\/]/).pop());
        showTab("gv");
      } catch (err) { fail(err); }
      return;
    default:
      return;
  }
  changed();
}

function wire() {
  window.addEventListener("pagehide", () => { if (st) saveDraft(); }); // đóng, tải lại trang: lưu ngay bản nháp
  document.addEventListener("input", onEdit);
  document.addEventListener("change", onEdit);
  document.addEventListener("click", (e) => onClick(e).catch(fail));
  $$(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("#btn-new").onclick = () => newScenario().catch(fail);
  $("#file-open").onchange = async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try {
      const data = await api("POST", "/api/import", await file.arrayBuffer(),
        { headers: { "X-File-Name": encodeURIComponent(file.name) } });
      useImported(data, file.name);
    } catch (err) { fail(err); }
  };
  $("#btn-export").onclick = async () => {
    try {
      const blob = await api("POST", "/api/export", { scenario: st.scenario, name: st.run.name }, { blob: true });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${st.run.name || "kich_ban"}.xlsx`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    } catch (err) { fail(err); }
  };
  $("#btn-add-subject").onclick = () => {
    const lessons = Object.fromEntries(st.scenario.grades.map((g) => [String(g), null]));
    st.scenario.subjects.push({ name: "", lessons, rules: newSubjectRules() });
    renderSubjects();
    changed();
    $$("#subject-table tbody tr").pop()?.querySelector("input")?.focus();
  };
  $("#btn-add-grade").onclick = () => {
    const sc = st.scenario;
    const g = (sc.grades.length ? Math.max(...sc.grades) : 0) + 1;
    sc.grades.push(g);
    sc.subjects.forEach((s) => { s.lessons[String(g)] = null; });
    renderSubjects();
    changed();
  };
  $("#btn-del-grade").onclick = () => {
    const sc = st.scenario;
    const g = sc.grades[sc.grades.length - 1];
    if (g === undefined || !confirm(`Bớt cột Khối ${g} (xóa số tiết của khối này)?`)) return;
    sc.grades.pop();
    sc.subjects.forEach((s) => { delete s.lessons[String(g)]; });
    renderSubjects();
    changed();
  };
  $("#btn-add-rule").onclick = () => {
    st.scenario.custom.push(newRule($("#new-kind").value));
    renderRules();
    changed();
    $$("#rule-table tbody tr").pop()?.querySelector("input:not([disabled])")?.focus();
  };
  $("#btn-add-staff").onclick = () => {
    st.scenario.staff.push(newStaffRow());
    renderStaff();
    changed();
    $$("#staff-table tbody tr").pop()?.querySelector("input")?.focus();
  };
  $("#btn-paste").onclick = () => { $("#paste-text").value = ""; $("#paste-dialog").showModal(); };
  $("#paste-dialog").addEventListener("close", () => {
    const how = $("#paste-dialog").returnValue;
    if (how !== "append" && how !== "replace") return;
    const rows = parsePasted($("#paste-text").value);
    if (!rows.length) return;
    st.scenario.staff = how === "replace" ? rows : [...st.scenario.staff, ...rows];
    renderStaff();
    changed();
    notify(`Đã dán ${rows.length} dòng nhân sự.`, "ok");
  });
  $("#btn-check").onclick = () => check().catch(fail);
  $("#btn-run").onclick = () => startRun().catch(fail);
  $("#btn-stop").onclick = async () => {
    stopAt = Date.now();
    try {
      await api("POST", "/api/stop", {});
    } catch (err) {
      fail(err);
      $("#btn-kill").hidden = false;
    }
  };
  $("#btn-kill").onclick = async () => {
    if (!confirm("Dừng hẳn: không ghi TKB của lần chạy này. Tiếp tục?")) return;
    await api("POST", "/api/kill", {}).catch(fail);
  };
  $("#btn-out-dir").onclick = async () => {
    try {
      const res = await api("POST", "/api/settings", { out_dir: $("#out-dir").value });
      S.out_dir = res.out_dir;
      renderRun();
      notify(`Thư mục kết quả: ${esc(res.out_dir)}`, "ok");
    } catch (err) { fail(err); }
  };
  $("#btn-open-dir").onclick = () => api("POST", "/api/open", { path: "" }).catch(fail);
}

async function init() {
  wire();
  try {
    S = await api("GET", "/api/schema");
  } catch (err) { fail(err); return; }
  const draft = loadDraft();
  if (draft && draft.scenario && draft.scenario.version === S.version) {
    st = { ...draft, run: { ...S.run_defaults, ...(draft.run || {}) } };
    st.scenario.custom ||= [];
    renderAll();
    notify("Đã mở lại kịch bản đang soạn lần trước (lưu tự động trên máy này).", "",
      { label: "Tạo mới", fn: () => newScenario().catch(fail) });
  } else {
    await newScenario(false).catch(fail);
  }
  renderHelp();
  let tab = "khung";
  try { tab = localStorage.getItem(TAB_KEY) || tab; } catch { /* bỏ qua */ }
  showTab(tab);
  if (S.running) startPolling();
}

init();
