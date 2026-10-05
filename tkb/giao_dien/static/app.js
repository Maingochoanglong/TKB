"use strict";
// Giao diện xếp TKB: soạn kịch bản (tkb/kich_ban.py), kiểm tra, tải file Excel, xếp TKB qua máy chủ trên máy này.
// Các ô nhập sinh từ /api/schema (tkb/rules.py), nên quy định mới thêm ở rules.py tự có ô ở đây.

const TOKEN = window.TKB_TOKEN;
const DRAFT_KEY = "tkb-ban-nhap-v1";
const TAB_KEY = "tkb-tab";
const GRID_KEY = "tkb-mon-bang";
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

// ---------------------------------------------------------------- tên môn, chức vụ
// Khóa so khớp tên môn/chức vụ như staff.subject_key: không phân biệt hoa thường, dấu câu và chữ "và".
const key = (s) => String(s ?? "").normalize("NFC").toLowerCase().replace(/[^\p{L}\p{N}_\s]/gu, " ")
  .split(/\s+/).filter((w) => w && w !== "và").join(" ");
const named = (s) => String(s.name || "").trim();
const subjectNames = () => st.scenario.subjects.map(named).filter(Boolean);
const RR = () => S.role_rules; // khóa cột quy định của môn theo chức vụ có sẵn
const rulesOf = (name) => (st.scenario.subjects.find((s) => key(s.name) === key(name)) || {}).rules || {};
const HOMEROOM = () => S.roles[0];
const isHomeroomRole = (role) => key(role) === key(HOMEROOM());
const isHomeroom = (t) => isHomeroomRole(t.role);
// Chức vụ của một ô Chức Vụ: tên chức vụ có sẵn hoặc chức vụ của bước 3 cùng khóa; không có thì null.
function roleOf(text) {
  const k = key(text);
  if (!k) return null;
  const builtin = S.roles.find((r) => key(r) === k);
  if (builtin) return { name: builtin, builtin: true };
  const i = st.scenario.roles.findIndex((r) => key(r.name) === k);
  return i >= 0 ? { name: st.scenario.roles[i].name, index: i } : null;
}
const teachersOf = (name) => st.scenario.staff.filter((t) => key(t.role) && key(t.role) === key(name)).length;
// Như kich_ban.from_excel: chức vụ trùng tên môn mà nhân sự đang dùng thành một chức vụ của bước 3.
function addImplicitRoles() {
  const subjects = Object.fromEntries(subjectNames().map((n) => [key(n), n]));
  for (const t of st.scenario.staff) {
    const k = key(t.role);
    if (k && !roleOf(t.role) && subjects[k]) st.scenario.roles.push({ name: String(t.role).trim(), subjects: [subjects[k]] });
  }
}
// Ai dạy một môn: [chữ, có người dạy chưa].
function whoTeaches(name) {
  const r = rulesOf(name);
  const rr = RR();
  if (r[rr.homeroom_only]) return [["Chỉ GVCN"], true];
  const out = [];
  if (r[rr.homeroom_take]) out.push("GVCN nhận trọn");
  else if (r[rr.homeroom_fill]) out.push(`GVCN nhận thêm (${r[rr.homeroom_fill]})`);
  const roles = st.scenario.roles.filter((role) => named(role) && (role.subjects || []).some((s) => key(s) === key(name)));
  out.push(...roles.map((role) => role.name.trim()));
  if (!r[rr.general_forbidden]) out.push(S.roles[1]);
  if (r[rr.manager_grade]) out.push(`${S.roles[2]} (khối ${r[rr.manager_grade]})`);
  return [out, roles.length > 0 || !r[rr.general_forbidden] || !!r[rr.homeroom_take]];
}
function renameSubject(from, to) {
  if (!key(from) || key(from) === key(to)) return;
  for (const role of st.scenario.roles) role.subjects = (role.subjects || []).map((s) => (key(s) === key(from) ? to : s));
  for (const rule of st.scenario.rules) {
    for (const k of ["subject", "other"]) rule[k] = listOf(rule[k]).map((x) => (key(x) === key(from) ? to : x)).join(", ");
  }
}
function renameRole(from, to) {
  if (!key(from) || key(from) === key(to)) return;
  for (const t of st.scenario.staff) if (key(t.role) === key(from)) t.role = to;
  for (const rule of st.scenario.rules) {
    rule.role = listOf(rule.role).map((x) => (key(x) === key(from) ? to : x)).join(", ");
  }
}

// ---------------------------------------------------------------- hộp thoại chi tiết (môn, giáo viên)
let detail = null; // {kind: "subject" | "staff", i}
function openDetail(kind, i) {
  detail = { kind, i };
  renderDetail();
  $("#detail-dialog").showModal();
}
function formRow(label, html, note = "") {
  return `<label class="gen-row"><span>${esc(label)}</span><span class="val">${html}</span>${note ? `<small>${esc(note)}</small>` : ""}</label>`;
}
function renderDetail() {
  if (!detail) return;
  const sc = st.scenario;
  const i = detail.i;
  let html = "";
  if (detail.kind === "subject") {
    const s = sc.subjects[i];
    $("#detail-title").textContent = named(s) || "Môn mới";
    html += `<fieldset><legend>Môn học</legend>
      ${formRow("Tên môn", input("text", s.name, { f: "subject", i, k: "name" }, "wide"))}
      <div class="lessons">${sc.grades.map((g) => `<label><span>Khối ${esc(g)}</span>${
        input("int", (s.lessons || {})[g], { f: "lessons", i, k: g })}</label>`).join("")}</div>
      <small>Số tiết/tuần từng khối; trống hoặc 0: khối đó không học.</small></fieldset>`;
    const used = new Set();
    const groups = [...S.subject_groups, { label: "Khác", keys: S.subject.map((c) => c.key) }];
    for (const g of groups) {
      const cols = S.subject.filter((c) => g.keys.includes(c.key) && !used.has(c.key));
      cols.forEach((c) => used.add(c.key));
      if (!cols.length) continue;
      let extra = "";
      if (g.keys.includes(RR().general_forbidden)) {
        const roles = sc.roles.filter((r) => (r.subjects || []).some((x) => key(x) === key(s.name))).map(named);
        extra = `<p class="muted">Chức vụ GV chuyên biệt dạy môn này: <b>${esc(roles.join(", ") || "chưa có")}</b>
          (chọn ở bước 3, Chức vụ).</p>`;
      }
      html += `<fieldset><legend>${esc(g.label)}</legend>${cols.map((c) =>
        formRow(c.header, input(c.kind, (s.rules || {})[c.key], { f: "rule", i, k: c.key }), c.note)).join("")}${extra}</fieldset>`;
    }
  } else {
    const t = sc.staff[i];
    $("#detail-title").textContent = `Dòng ${i + 2}: ${String(t.name || "").trim() || "Giáo viên mới"}`;
    html = `<fieldset>${S.staff.map((c) => {
      let field = input(c.kind, t[c.key], { f: "staff", i, k: c.key }, "wide");
      if (c.key === "role") field = roleSelect(t.role, i);
      if (c.key === "class" && !isHomeroom(t)) field = `<input type="text" disabled placeholder="Chỉ Chủ Nhiệm ghi Lớp">`;
      if (c.key === "history") return formBlock(c.header, `<div id="hist-box">${historyBox(t, i)}</div>`, c.note);
      if (c.key === "off") return formBlock(c.header, `<div id="off-box">${offBox(t, i)}</div>`, c.note);
      return formRow(c.header, field, c.note);
    }).join("")}</fieldset>`;
  }
  $("#detail-body").innerHTML = html;
}

// ---------------------------------------------------------------- giáo viên: lớp đang dạy, buổi nghỉ
// Hai cột chữ của sheet NHÂN SỰ, chọn bằng ô đánh dấu. Chữ ghi ra đúng cách chương trình đọc (staff.parse_classes,
// staff.parse_off); mục không đọc được giữ nguyên chữ để nút Kiểm tra báo lỗi, bấm ✕ để bỏ.
function formBlock(label, html, note = "") {
  return `<div class="gen-row block"><span>${esc(label)}</span><div class="val">${html}</div>${note ? `<small>${esc(note)}</small>` : ""}</div>`;
}
const fold = (s) => String(s ?? "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d")
  .replace(/\s+/g, " ").trim();
const classKey = (c) => String(c ?? "").toLowerCase().replace(/\s+/g, "");
function classOrder(c) { // như staff.class_sort_key: khối, phần chữ, số
  const m = String(c).match(/^(\d+)\D*?(\p{L}*)(\d*)$/u);
  return m ? [Number(m[1]), m[2].toUpperCase(), Number(m[3] || 0)] : [Infinity, String(c), 0];
}
const byClass = (a, b) => {
  const [x, y] = [classOrder(a), classOrder(b)];
  return x[0] - y[0] || (x[1] < y[1] ? -1 : x[1] > y[1] ? 1 : 0) || x[2] - y[2];
};
function schoolClasses() { // các lớp của trường: cột Lớp của các dòng Chủ Nhiệm
  const seen = new Map();
  for (const t of st.scenario.staff) {
    const c = String(t.class || "").trim();
    if (isHomeroom(t) && c && !seen.has(classKey(c))) seen.set(classKey(c), c);
  }
  return [...seen.values()].sort(byClass);
}
const histList = (t) => String(t.history || "").split(/[,;]/).map((c) => c.trim()).filter(Boolean);
function setHistory(t, list) {
  const known = new Set(schoolClasses().map(classKey));
  const uniq = [...new Map(list.map((c) => [classKey(c), c])).values()];
  t.history = [...uniq.filter((c) => known.has(classKey(c))).sort(byClass), ...uniq.filter((c) => !known.has(classKey(c)))]
    .join(", ");
}
function historyBox(t, i) {
  if (isHomeroom(t)) return `<p class="muted">Chủ Nhiệm dạy lớp mình; cột này dành cho GV bộ môn, chuyên biệt.</p>`;
  const classes = schoolClasses();
  if (!classes.length) return `<p class="muted">Chưa có lớp nào: ghi Lớp cho các Chủ Nhiệm trước.</p>`;
  const chosen = new Set(histList(t).map(classKey));
  const grades = [...new Set(classes.map((c) => classOrder(c)[0]))];
  const rows = grades.map((g) => {
    const list = classes.filter((c) => classOrder(c)[0] === g);
    return `<div class="grade-row"><button type="button" class="ghost small" data-act="hist-grade" data-i="${i}" data-g="${g}"
      title="Chọn hoặc bỏ cả khối">Khối ${g}</button><div class="checks">${list.map((c) => `<label class="check-item">
      <input type="checkbox" data-f="hist" data-i="${i}" data-c="${esc(c)}" ${chosen.has(classKey(c)) ? "checked" : ""}> ${esc(c)}</label>`).join("")}</div></div>`;
  }).join("");
  const known = new Set(classes.map(classKey));
  const unknown = histList(t).filter((c) => !known.has(classKey(c)));
  return rows + unknown.map((c) => `<p class="warn-text">Không có Chủ Nhiệm lớp "${esc(c)}"
    <button type="button" class="icon" data-act="hist-drop" data-i="${i}" data-c="${esc(c)}" title="Bỏ lớp này">✕</button></p>`).join("");
}
// Khung giờ của kịch bản: ngày học (liền nhau từ Thứ 2) và các buổi của từng ngày.
const SESSIONS = () => S.custom.sessions; // ["Sáng", "Chiều"]
function frameDays() {
  const days = st.scenario.days || [];
  const out = [];
  for (let d = 0; d < days.length && days[d] && days[d].morning_days; d++) {
    out.push({ d, sessions: [SESSIONS()[0], ...(days[d].afternoon_days ? [SESSIONS()[1]] : [])] });
  }
  return out;
}
const sessionOf = (word) => SESSIONS().find((s) => fold(s) === word);
function offState(text) {
  const o = { fixed: new Set(), any: Object.fromEntries([...SESSIONS(), ""].map((s) => [s, 0])), other: [] };
  const days = frameDays();
  for (const part of String(text || "").split(/[,;]/)) {
    const raw = part.trim();
    if (!raw) continue;
    const item = fold(raw);
    let m = item.match(/^(\w+)\s*(?:thu|t)?\s*(\d)$/);
    if (m && sessionOf(m[1])) {
      const s = sessionOf(m[1]);
      const day = days.find((x) => x.d === Number(m[2]) - 2);
      if (day && day.sessions.includes(s)) o.fixed.add(`${day.d}|${s}`);
      else o.other.push({ raw, note: day ? "buổi này vốn nghỉ, chương trình bỏ qua" : "không có ngày này trong khung giờ" });
      continue;
    }
    m = item.match(/^(\d+)\s*buoi(?:\s+(\w+))?(?:\s+bat k[yi])?$/);
    if (m && (!m[2] || sessionOf(m[2]))) o.any[m[2] ? sessionOf(m[2]) : ""] += Number(m[1]);
    else o.other.push({ raw, note: "không đọc được" });
  }
  return o;
}
function offText(o) {
  const parts = [];
  for (const { d } of frameDays()) for (const s of SESSIONS()) if (o.fixed.has(`${d}|${s}`)) parts.push(`${s} T${d + 2}`);
  for (const s of SESSIONS()) if (o.any[s] > 0) parts.push(`${o.any[s]} buổi ${s.toLowerCase()}`);
  if (o.any[""] > 0) parts.push(`${o.any[""]} buổi`);
  return [...parts, ...o.other.map((x) => x.raw)].join(", ");
}
function offBox(t, i) {
  const o = offState(t.off);
  const days = frameDays();
  const [morning] = SESSIONS();
  const cn = isHomeroom(t);
  const locked = (s, on) => cn && s === morning && !on; // GVCN không nghỉ buổi sáng (tiết luôn do GVCN dạy)
  const grid = `<table class="grid off-grid"><thead><tr><th></th>${days.map(({ d }) => `<th>${esc(S.days[d])}</th>`).join("")}</tr></thead>
    <tbody>${SESSIONS().map((s) => `<tr><th>${esc(s)}</th>${days.map(({ d, sessions }) => {
      if (!sessions.includes(s)) return `<td class="muted">—</td>`;
      const on = o.fixed.has(`${d}|${s}`);
      return `<td><input type="checkbox" data-f="off-fixed" data-i="${i}" data-d="${d}" data-s="${esc(s)}" ${on ? "checked" : ""}
        ${locked(s, on) ? "disabled title=\"GVCN không nghỉ buổi sáng\"" : ""} aria-label="${esc(`${s} ${S.days[d]}`)}"></td>`;
    }).join("")}</tr>`).join("")}</tbody></table>`;
  const anyInput = (s, label) => `<label class="any-off"><input type="number" min="0" step="1" data-f="off-any" data-i="${i}"
    data-s="${esc(s)}" value="${o.any[s] || ""}" placeholder="0" ${locked(s, o.any[s] > 0) ? "disabled" : ""}> ${esc(label)}</label>`;
  return `<p class="muted">Buổi cố định: đánh dấu buổi nghỉ.</p>${grid}
    <p class="muted">Nghỉ thêm buổi bất kỳ (chương trình tự chọn buổi cho TKB tốt nhất):</p>
    <div class="any-row">${SESSIONS().map((s) => anyInput(s, `buổi ${s.toLowerCase()}`)).join("")}${anyInput("", "buổi sáng hoặc chiều")}</div>
    <div id="off-note">${offNote(t, i)}</div>`;
}
function offNote(t, i) {
  const o = offState(t.off);
  const days = frameDays();
  const notes = [];
  for (const s of [...SESSIONS(), ""]) { // như staff.parse_off: số buổi bất kỳ không quá số buổi còn lại
    const free = days.reduce((n, { d, sessions }) => n + sessions.filter((x) => (!s || x === s) && !o.fixed.has(`${d}|${x}`)).length, 0);
    if (o.any[s] > free) notes.push(`<p class="warn-text">Xin nghỉ ${o.any[s]} buổi ${s ? s.toLowerCase() : "bất kỳ"} nhưng chỉ còn ${free} buổi để chọn.</p>`);
  }
  if (isHomeroom(t) && ([...o.fixed].some((k) => k.endsWith(`|${SESSIONS()[0]}`)) || o.any[SESSIONS()[0]] > 0)) {
    notes.push(`<p class="warn-text">GVCN không nghỉ buổi sáng được (tiết Luôn do GVCN dạy, bước 1).</p>`);
  }
  notes.push(...o.other.map((x, k) => `<p class="warn-text">"${esc(x.raw)}": ${esc(x.note)}
    <button type="button" class="icon" data-act="off-drop" data-i="${i}" data-k="${k}" title="Bỏ mục này">✕</button></p>`));
  return `<p class="preview">Ghi vào file: <b>${esc(t.off || "không nghỉ buổi nào")}</b></p>${notes.join("")}`;
}

// ---------------------------------------------------------------- tab 2: môn học
let subjectGrid = false; // true: bảng đầy đủ mọi cột quy định
const subjectKept = (s) => String(s.name || "").trim() !== "" ||
  Object.values(s.lessons || {}).some((v) => v !== null && v !== "");
function subjectRowNumbers() { // số dòng trong sheet CHƯƠNG TRÌNH HỌC của file Excel (dòng 1 là tiêu đề)
  let r = 1;
  return st.scenario.subjects.map((s) => (subjectKept(s) ? ++r : null));
}
const SHOWN_IN_WHO = () => new Set(Object.values(RR()));
function ruleChips(s) {
  const skip = SHOWN_IN_WHO();
  return S.subject.filter((c) => !skip.has(c.key)).map((c) => {
    const v = (s.rules || {})[c.key];
    if (c.kind === "yes") return v ? c.header : "";
    return v === null || v === undefined || v === "" ? "" : `${c.header}: ${v}`;
  }).filter(Boolean).map((t) => `<span class="chip">${esc(t)}</span>`).join("");
}
function renderSubjects() {
  const sc = st.scenario;
  const nums = subjectRowNumbers();
  const grades = sc.grades.map((g) => `<th class="group-grade">Khối ${esc(g)}</th>`).join("");
  const lessonCells = (s, i) => sc.grades.map((g) => `<td>${input("int", (s.lessons || {})[g], { f: "lessons", i, k: g })}</td>`).join("");
  let head;
  let body;
  if (subjectGrid) {
    head = `<thead><tr><th>Dòng</th><th class="left stick">Môn học</th>${grades}${
      S.subject.map((c) => `<th ${colTitle(c)}>${esc(c.header)}</th>`).join("")}<th></th></tr></thead>`;
    body = sc.subjects.map((s, i) => `<tr data-row="${nums[i] ?? ""}">
      <td class="num">${nums[i] ?? "—"}</td>
      <td class="left stick">${input("text", s.name, { f: "subject", i, k: "name" }, "wide")}</td>
      ${lessonCells(s, i)}
      ${S.subject.map((c) => `<td>${input(c.kind, (s.rules || {})[c.key], { f: "rule", i, k: c.key })}</td>`).join("")}
      <td><button type="button" class="icon" data-act="del-subject" data-i="${i}" title="Xóa môn">✕</button></td></tr>`).join("");
  } else {
    head = `<thead><tr><th>Dòng</th><th class="left stick">Môn học</th>${grades}<th class="left">Ai dạy</th>
      <th class="left">Quy định khác</th><th></th></tr></thead>`;
    body = sc.subjects.map((s, i) => {
      const [who, ok] = whoTeaches(s.name);
      const whoText = ok ? esc(who.join(", ")) : `<span class="warn-text" title="Bộ Môn không dạy môn này và chưa có chức vụ nào dạy: thêm chức vụ ở bước 3">⚠ chưa có ai</span>`;
      return `<tr data-row="${nums[i] ?? ""}">
      <td class="num">${nums[i] ?? "—"}</td>
      <td class="left stick">${input("text", s.name, { f: "subject", i, k: "name" }, "wide")}</td>
      ${lessonCells(s, i)}
      <td class="left who">${whoText}</td>
      <td class="left chips">${ruleChips(s)}</td>
      <td class="nowrap"><button type="button" class="ghost small" data-act="edit-subject" data-i="${i}">Sửa</button>
        <button type="button" class="icon" data-act="del-subject" data-i="${i}" title="Xóa môn">✕</button></td></tr>`;
    }).join("");
  }
  $("#subject-table").innerHTML = head + `<tbody>${body}</tbody>`;
  $("#subject-table").classList.toggle("compact", !subjectGrid);
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

// ---------------------------------------------------------------- tab 3: chức vụ
// Ba chức vụ có sẵn sửa các cột quy định của môn (data-f="rule": Có; "rule-not": Không); chức vụ tự đặt là một dòng
// của sheet CHỨC VỤ (dòng i của danh sách là dòng i + 2 của sheet).
function subjectChecks(opts) {
  const sc = st.scenario;
  return `<div class="checks">${sc.subjects.map((s, i) => {
    if (!named(s)) return "";
    const only = !!(s.rules || {})[RR().homeroom_only];
    const { checked, attrs, disabled } = opts(s, i, only);
    return `<label class="check-item ${disabled ? "off" : ""}" ${disabled ? `title="${esc(disabled)}"` : ""}>
      <input type="checkbox" ${attrs} ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}> ${esc(named(s))}</label>`;
  }).join("")}</div>`;
}
function roleCard(title, badge, teachers, body, extra = "") {
  return `<div class="card role" ${extra}><div class="toolbar"><h2>${title} <span class="badge">${esc(badge)}</span></h2>
    <span class="muted">${teachers} giáo viên</span></div>${body}</div>`;
}
function renderRoles() {
  const sc = st.scenario;
  const rr = RR();
  const [cn, bm, ql] = S.roles;
  const fill = sc.subjects.filter((s) => (s.rules || {})[rr.homeroom_fill])
    .sort((a, b) => a.rules[rr.homeroom_fill] - b.rules[rr.homeroom_fill]).map(named);
  const cards = [
    roleCard(esc(cn), "có sẵn", teachersOf(cn), `
      <p class="muted">Dạy lớp chủ nhiệm của mình (cột Lớp ở bước 4) và các tiết <i>Luôn do GVCN dạy</i> (bước 1).</p>
      <h3>Nhận trọn các môn</h3>${subjectChecks((s, i, only) => ({ checked: s.rules[rr.homeroom_take],
        attrs: `data-f="rule" data-i="${i}" data-k="${rr.homeroom_take}"` }))}
      <h3>Chỉ GVCN được dạy</h3>${subjectChecks((s, i) => ({ checked: s.rules[rr.homeroom_only],
        attrs: `data-f="rule" data-i="${i}" data-k="${rr.homeroom_only}"` }))}
      <p class="muted">Nhận thêm cho đủ định mức theo thứ tự: <b>${esc(fill.join(", ") || "không")}</b> (số thứ tự ở cột
        GVCN nhận thêm của từng môn, bước 2).</p>`),
    roleCard(esc(bm), "có sẵn", teachersOf(bm), `
      <p class="muted">Dạy nhiều lớp. Bỏ đánh dấu môn Bộ Môn không được dạy (cột Bộ Môn không dạy của môn).</p>
      <h3>Được dạy</h3>${subjectChecks((s, i, only) => ({ checked: !s.rules[rr.general_forbidden] && !only,
        attrs: `data-f="rule-not" data-i="${i}" data-k="${rr.general_forbidden}"`, disabled: only && "Chỉ GVCN được dạy" }))}`),
    roleCard(esc(ql), "có sẵn", teachersOf(ql), `
      <p class="muted">Chỉ dạy môn có ghi khối ở đây (cột Quản lý dạy khối), các lớp của khối đó.</p>
      <div class="checks">${sc.subjects.map((s, i) => named(s) ? `<label class="check-item grade">
        ${input("int", (s.rules || {})[rr.manager_grade], { f: "rule", i, k: rr.manager_grade })} ${esc(named(s))}</label>` : "").join("")}</div>
      <small>Ghi khối (vd 4) cạnh môn Quản Lý dạy; để trống là không dạy.</small>`),
    ...sc.roles.map((role, i) => roleCard(
      `<input type="text" class="role-name" data-f="role" data-i="${i}" data-k="name" value="${esc(role.name)}"
        placeholder="Tên chức vụ, vd GV Nghệ thuật" spellcheck="false">`,
      `dòng ${i + 2}`, teachersOf(role.name), `
      <h3>Môn được dạy</h3>${subjectChecks((s, j, only) => ({
        checked: (role.subjects || []).some((x) => key(x) === key(s.name)),
        attrs: `data-f="role-subject" data-i="${i}" data-s="${esc(named(s))}"`, disabled: only && "Chỉ GVCN được dạy" }))}
      ${(role.subjects || []).filter((x) => !subjectNames().some((n) => key(n) === key(x))).map((x) =>
        `<p class="warn-text">Môn "${esc(x)}" không có ở bước 2.</p>`).join("")}
      ${!(role.subjects || []).length ? `<p class="warn-text">Chưa chọn môn nào.</p>` : teachersOf(role.name) ? "" :
        `<p class="muted">Chưa có giáo viên nào giữ chức vụ này (chọn ở bước 4).</p>`}
      <div class="actions end"><button type="button" class="danger ghost" data-act="del-role" data-i="${i}">Xóa chức vụ</button></div>`,
      `data-row="${i + 2}"`)),
  ];
  $("#role-cards").innerHTML = cards.join("");
  renderRoleHints();
}
// Môn Bộ Môn không dạy mà chưa có ai dạy được: gợi ý thêm chức vụ / thêm GV.
function renderRoleHints() {
  const rr = RR();
  const hints = [];
  for (const s of st.scenario.subjects) {
    const r = s.rules || {};
    const total = Object.values(s.lessons || {}).reduce((n, v) => n + (Number.isInteger(v) ? v : 0), 0);
    if (!named(s) || !total || !r[rr.general_forbidden] || r[rr.homeroom_only] || r[rr.homeroom_take]) continue;
    const roles = st.scenario.roles.filter((role) => (role.subjects || []).some((x) => key(x) === key(s.name)));
    if (!roles.length) {
      hints.push(`<li class="warn">Môn <b>${esc(named(s))}</b>: Bộ Môn không được dạy và chưa có chức vụ nào dạy.
        <button type="button" class="ghost small" data-act="add-role-for" data-s="${esc(named(s))}">+ Thêm chức vụ "${esc(named(s))}"</button></li>`);
    } else if (!roles.some((role) => teachersOf(role.name))) {
      hints.push(`<li class="warn">Môn <b>${esc(named(s))}</b>: chưa có giáo viên nào giữ chức vụ
        ${esc(roles.map(named).join(", "))} (thêm ở bước 4).</li>`);
    }
  }
  $("#role-hints").innerHTML = hints.length ? `<ul class="msgs">${hints.join("")}</ul>` : "";
}

// ---------------------------------------------------------------- tab 4: giáo viên
function renderRoleList() {
  const names = subjectNames();
  const roles = [...S.roles, ...st.scenario.roles.map(named).filter(Boolean)];
  $("#role-list").innerHTML = [...new Set(roles)].map((r) => `<option value="${esc(r)}">`).join("");
  $("#subject-list").innerHTML = [...new Set(names)].map((r) => `<option value="${esc(r)}">`).join("");
  $("#session-list").innerHTML = S.custom.sessions.map((r) => `<option value="${esc(r)}">`).join("");
}
function roleSelect(value, i) {
  const role = roleOf(value);
  const names = [...S.roles, ...st.scenario.roles.map(named).filter(Boolean)];
  let opts = `<option value="" ${role || String(value || "").trim() ? "" : "selected"}>— chọn —</option>`;
  opts += [...new Set(names)].map((n) => `<option value="${esc(n)}" ${role && key(role.name) === key(n) ? "selected" : ""}>${esc(n)}</option>`).join("");
  if (!role && String(value || "").trim()) {
    opts += `<option value="${esc(value)}" selected>${esc(value)} (chưa có ở bước 3)</option>`;
  }
  return `<select data-f="staff" data-i="${i}" data-k="role" class="${role || !String(value || "").trim() ? "" : "bad"}">${opts}</select>`;
}
let staffFilter = "";
function staffChips(t) {
  return S.staff.filter((c) => !["name", "role", "class", "lessons"].includes(c.key)).map((c) => {
    const v = t[c.key];
    if (c.kind === "yes") return v ? c.header : "";
    return String(v ?? "").trim() ? `${c.header}: ${v}` : "";
  }).filter(Boolean).map((x) => `<span class="chip">${esc(x)}</span>`).join("");
}
function renderStaff() {
  const head = `<thead><tr><th>Dòng</th><th class="left stick">Họ và Tên</th><th>Chức Vụ</th><th>Lớp</th>
    <th>Số Tiết/Tuần</th><th class="left">Khác</th><th></th></tr></thead>`;
  const body = st.scenario.staff.map((t, i) => {
    const show = !staffFilter || key(t.role) === key(staffFilter) || (staffFilter === "?" && !roleOf(t.role));
    return `<tr data-row="${i + 2}" ${show ? "" : "hidden"}><td class="num">${i + 2}</td>
    <td class="left stick">${input("text", t.name, { f: "staff", i, k: "name" }, "wide")}</td>
    <td>${roleSelect(t.role, i)}</td>
    <td>${isHomeroom(t) ? input("text", t.class, { f: "staff", i, k: "class" }, "short") : `<span class="muted">—</span>`}</td>
    <td>${input("int", t.lessons, { f: "staff", i, k: "lessons" })}</td>
    <td class="left chips">${staffChips(t)}</td>
    <td class="nowrap">
      <button type="button" class="ghost small" data-act="edit-staff" data-i="${i}">Sửa</button>
      <button type="button" class="icon" data-act="up" data-i="${i}" title="Lên">↑</button>
      <button type="button" class="icon" data-act="down" data-i="${i}" title="Xuống">↓</button>
      <button type="button" class="icon" data-act="del-staff" data-i="${i}" title="Xóa dòng">✕</button></td></tr>`;
  }).join("");
  $("#staff-table").innerHTML = head + `<tbody>${body}</tbody>`;
  const names = [...new Set([...S.roles, ...st.scenario.roles.map(named).filter(Boolean)])];
  $("#staff-filter").innerHTML = `<option value="">Mọi chức vụ</option>${names.map((n) =>
    `<option value="${esc(n)}" ${key(n) === key(staffFilter) ? "selected" : ""}>${esc(n)} (${teachersOf(n)})</option>`).join("")}
    <option value="?" ${staffFilter === "?" ? "selected" : ""}>Chưa có chức vụ hợp lệ</option>`;
  updateCounts();
}
function newStaffRow() {
  return Object.fromEntries(S.staff.map((c) => [c.key, c.kind === "yes" ? false : c.kind === "int" ? null : ""]));
}
function updateCounts() {
  if (!st) return;
  const staff = st.scenario.staff.filter((t) => String(t.name || "").trim() || String(t.role || "").trim());
  const subjects = st.scenario.subjects.filter((s) => String(s.name || "").trim());
  $("#count-gv").textContent = staff.length || "";
  $("#count-mon").textContent = subjects.length || "";
  $("#count-cv").textContent = S.roles.length + st.scenario.roles.filter(named).length;
  $("#count-luat").textContent = (st.scenario.rules || []).length || "";
  const classes = staff.filter(isHomeroom).length;
  const quota = staff.reduce((n, t) => n + (Number.isInteger(t.lessons) ? t.lessons : 0), 0);
  $("#staff-summary").textContent = `${staff.length} người, ${classes} lớp (mỗi Chủ Nhiệm một lớp), tổng định mức ` +
    `${quota} tiết/tuần. Chức Vụ chọn trong các chức vụ của bước 3; chỉ Chủ Nhiệm ghi Lớp. Bấm Sửa để ghi Thai Sản, ` +
    `Hợp Đồng, Cơ sở 2, Lớp Đang Dạy, Buổi Nghỉ.`;
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

// ---------------------------------------------------------------- tab 5: luật (bộ ghép luật)
// Mọi luật là dòng của sheet LUẬT, đọc như một câu "Với mỗi [phạm vi] · các tiết [điều kiện] · thì [phép đo]
// [so sánh] [số]" (tkb/bo_ghep.py), kể cả các luật có sẵn (tkb/luat_co_san.py): sửa, xóa, thêm dòng ở hộp thoại ghép
// câu. Câu đọc lại, lỗi và "dạng gốc" (luật có sẵn chưa sửa dạng) do máy chủ nói (/api/describe, cùng hàm với file
// Excel). Từ vựng (phạm vi, phép đo, nhãn) lấy từ schema nên thêm ở Python là trang có.
const CP = () => S.custom.composer;
const kindOf = (row) => S.custom.kinds.find((k) => k.label === row.kind || k.key === row.kind) || S.custom.kinds[0];
const measureOf = (row) => CP().measures.find((m) => m.label === row.measure || m.key === row.measure) || null;
const opLabel = (key) => (CP().ops.find((o) => o.key === key) || {}).label || key;
const listOf = (v) => String(v ?? "").split(/[,;×]/).map((x) => x.trim()).filter(Boolean);
const NATIVE_ONLY = ["nghi_gv", "co_so_2"]; // mẫu chỉ có dạng gốc: chỉ bỏ được (xóa dòng)
let said = null; // {rules: [{text, errors, native}]} của /api/describe
let sayTimer = null;
function sayLater() {
  clearTimeout(sayTimer);
  sayTimer = setTimeout(() => say().catch(fail), 350);
}
async function say() {
  said = await api("POST", "/api/describe", { scenario: st.scenario, student_rules: st.run.student_rules });
  renderRuleList();
}
function renderRules() {
  renderRuleList();
  sayLater();
}
// Mức ưu tiên bằng chữ (Thấp, Vừa, Cao, Rất cao); kịch bản cũ ghi số 1–4.
const levelWord = (v) => (typeof v === "number" || /^\d$/.test(String(v ?? "")) ? S.custom.levels[Number(v) - 1]
  : S.custom.levels.find((w) => fold(w) === fold(v))) || S.custom.levels[1];
function levelBadge(row, r) {
  if (row.hard) return `<b class="hard">Bắt buộc</b>`;
  const word = (r && r.level) || levelWord(row.level);
  return `<b class="soft" ${row.points ? `title="${esc(row.points)} điểm"` : ""}>Ưu tiên ${esc(word.toLowerCase())}</b>`;
}
function renderRuleList() {
  const rows = st.scenario.rules;
  const order = [...S.custom.groups];
  rows.forEach((r) => { if (r.group_label && !order.includes(r.group_label)) order.push(r.group_label); });
  const group = (row) => row.group_label || S.custom.custom_group;
  $("#rule-list").innerHTML = order.map((g) => {
    const items = rows.map((row, i) => [row, i]).filter(([row]) => group(row) === g);
    if (!items.length) return "";
    return `<li class="rule-group"><h3>${esc(g)} <span class="muted">(${items.length})</span></h3><ol>${items.map(([row, i]) => {
      const r = said && said.rules[i];
      const errs = r ? r.errors : [];
      const text = r && r.text ? r.text.replace(/ \((bắt buộc|ưu tiên[^)]*)\)$/, "") : `${kindOf(row).label}…`;
      const native = r && r.native ? `<span class="tag" title="Luật có sẵn ở dạng gốc: chương trình xếp như trước, số và điểm lấy từ dòng này">có sẵn</span>` : "";
      return `<li class="rule-item${errs.length ? " bad" : ""}" data-row="${i + 2}">
        <span class="num">Dòng ${i + 2}</span>
        <div class="say">${levelBadge(row, r)} ${esc(text)} ${native}${errs.map((e) => `<div class="warn-text">${esc(e)}</div>`).join("")}</div>
        <span class="nowrap"><button type="button" class="ghost small" data-act="edit-rule" data-i="${i}">Sửa</button>
          <button type="button" class="icon" data-act="del-rule" data-i="${i}" title="Xóa luật (bỏ luật này)">✕</button></span></li>`;
    }).join("")}</ol></li>`;
  }).join("");
  $("#rule-empty").hidden = rows.length > 0;
  $("#rule-structure").textContent = S.custom.structure;
  updateCounts();
}

// Loại luật: một ô chọn chia theo bốn họ (Ở đâu, Bao nhiêu, Đi cùng nhau, Ai dạy), mỗi họ gồm các mẫu luật rồi
// "Tự ghép · <phép đo>". Giá trị là Kiểu luật, hoặc "Tự ghép|<Phép đo>" (ghi vào hai cột Kiểu luật, Phép đo).
const COMPOSE_KIND = () => S.custom.kinds.find((k) => k.key === "tu_ghep");
function typeValue(row) {
  const kind = kindOf(row);
  if (kind.key !== "tu_ghep") return kind.label;
  const m = measureOf(row);
  return `${kind.label}|${m ? m.label : ""}`;
}
function typeOptions(current = "") {
  const tu = COMPOSE_KIND().label;
  const groups = CP().families.map((f) => [f, [
    ...S.custom.kinds.filter((k) => k.family === f).map((k) => [k.label, k.label]),
    ...CP().measures.filter((m) => m.family === f).map((m) => [`${tu}|${m.label}`, `${tu} · ${m.label}`])]]);
  const known = groups.some(([, opts]) => opts.some(([v]) => v === current));
  const blank = current && !known ? `<option value="${esc(current)}" selected>${esc(current.replace("|", " · "))}…</option>` : "";
  return blank + groups.map(([f, opts]) => `<optgroup label="${esc(f)}">${opts.map(([v, t]) =>
    `<option value="${esc(v)}" ${v === current ? "selected" : ""}>${esc(t)}</option>`).join("")}</optgroup>`).join("");
}
function setType(row, value) {
  const [kind, measure] = value.split("|");
  row.kind = kind;
  row.measure = measure || "";
  const m = measureOf(row);
  row.op = m && m.ops.length && !m.default_op ? opLabel(m.ops[0]) : "";
}
function newRule(value) {
  const row = Object.fromEntries(S.custom.columns.map((c) => [c.key, ""]));
  const out = { ...row, group_label: S.custom.custom_group, number: null, hard: true, level: null, points: null };
  setType(out, value);
  return out;
}

// Hộp thoại ghép câu: sửa một bản sao, bấm Xong mới ghi vào kịch bản. Thứ tự như câu luật: Loại luật · Với mỗi ·
// Các tiết nào · Thì · Mức; các ô ít dùng nằm trong "Thêm điều kiện", Điểm và Nhóm trong "Nâng cao".
let ruleEdit = null; // {i (-1: luật mới), row, native: khóa luật có sẵn lúc mở}
function openRule(i, value) {
  const row = i < 0 ? newRule(value) : JSON.parse(JSON.stringify(st.scenario.rules[i]));
  ruleEdit = { i, row, native: i >= 0 && said && said.rules[i] ? said.rules[i].native : null };
  renderComposer();
  $("#rule-dialog").showModal();
  previewRule();
}
function shown(row) {
  // Các cột hiện trong hộp thoại: cột mẫu dùng; Tự ghép thì bớt các cột phép đo không cần.
  const kind = kindOf(row);
  const uses = new Set(kind.uses);
  if (kind.key === "tu_ghep") {
    const m = measureOf(row);
    if (!m || !m.ops.length) uses.delete("op");
    if (!m || !m.number) uses.delete("number");
    if (!m || !m.count_by) uses.delete("count_by");
    if (!m || !m.other) uses.delete("other");
  }
  return uses;
}
function familyOf(row) {
  const kind = kindOf(row);
  return kind.key === "tu_ghep" ? (measureOf(row) || {}).family || "" : kind.family;
}
function checks(k, values, chosen, label = (v) => v) {
  const set = new Set(listOf(chosen).map(fold));
  return `<div class="checks">${values.map((v) => `<label class="check-item"><input type="checkbox" data-f="rdlist"
    data-k="${k}" data-v="${esc(v)}" ${set.has(fold(v)) ? "checked" : ""}> ${esc(label(v))}</label>`).join("")}</div>`;
}
// Áp dụng khi dựng bằng ô: [từ … tiết/tuần trở lên] [không quá … | số ngày học] [chẵn/lẻ]; chữ khác thì chỉ ghi tay.
function whenParts(text) {
  const out = { min: "", max: "", days: false, parity: "", raw: false };
  for (const part of listOf(text)) {
    const p = fold(part).replace(/\s+/g, "").replace("≥", ">=").replace("≤", "<=");
    let m;
    if ((m = p.match(/^>=(\d+)$/))) out.min = m[1];
    else if ((m = p.match(/^<=(\d+)$/))) out.max = m[1];
    else if (p === "<=songay") out.days = true;
    else if (p === "chan" || p === "le") out.parity = p === "chan" ? "chẵn" : "lẻ";
    else out.raw = true;
  }
  return out;
}
function whenFromBuilder() {
  const v = (k) => $(`#rule-body [data-k="${k}"]`);
  const parts = [];
  if (v("when_min").value) parts.push(`>= ${v("when_min").value}`);
  if (v("when_days").checked) parts.push("<= số ngày"); else if (v("when_max").value) parts.push(`<= ${v("when_max").value}`);
  if (v("when_parity").value) parts.push(v("when_parity").value);
  v("when_max").disabled = v("when_days").checked;
  return parts.join(", ");
}
function renderComposer() {
  const row = ruleEdit.row;
  const kind = kindOf(row);
  const uses = shown(row);
  const m = measureOf(row);
  const family = familyOf(row);
  const text = (k, attrs = "") => `<input type="text" class="wide" data-f="rd" data-k="${k}" value="${esc(row[k] ?? "")}"
    spellcheck="false" ${attrs}>`;
  const field = (k, label, html, note = "") => (uses.has(k) ? formRow(label, html, note) : "");
  const block = (k, label, html, note = "") => (uses.has(k) ? formBlock(label, html, note) : "");
  const days = frameDays().map(({ d }) => `Thứ ${d + 2}`);
  const tagsOf = (list) => listOf(row.tags).filter((t) => list.includes(t)).length > 0;
  const groups = [...new Set([...S.custom.groups, row.group_label].filter(Boolean))];
  const native = NATIVE_ONLY.includes(kind.key);
  // Ô "Vào giờ nào" là phần chính của họ Ở đâu; ô Giáo viên là phần chính của họ Ai dạy và luật về giáo viên.
  const placeMain = family === "Ở đâu";
  const roleMain = family === "Ai dạy" || ["gv_ngay", "gv_lop_ngay"].includes(kind.key);
  const place = [
    block("days", "Ngày", checks("days", days, row.days)),
    field("periods", "Tiết", text("periods"), "Vd 1 hoặc 5-7."),
    block("sessions", "Buổi", checks("sessions", SESSIONS(), row.sessions)),
    block("tags", "Giờ có nhãn", checks("tags", CP().tags.slot, row.tags),
      "Giờ học đánh dấu Có ở các cột của sheet QUY ĐỊNH (vd Hạn chế môn nặng); nhiều nhãn: giờ có một trong các nhãn."),
  ].join("");
  const role = field("role", m && m.key === "nguoi_day" ? "Do chức vụ" : "Giáo viên", text("role", 'list="role-list"'),
    "Chức vụ, vd Bộ Môn, Tiếng Anh; nhiều chức vụ cách nhau bằng dấu phẩy; \"trừ Chủ Nhiệm\": mọi giáo viên trừ chức vụ đó.");
  const w = whenParts(row.when);
  const whenBuilder = uses.has("when") && !w.raw ? formBlock("Áp dụng khi", `<div class="when">
      số tiết/tuần của môn từ <input type="number" min="1" class="tiny" data-f="rd" data-k="when_min" value="${esc(w.min)}"> trở lên;
      không quá <input type="number" min="1" class="tiny" data-f="rd" data-k="when_max" value="${esc(w.max)}" ${w.days ? "disabled" : ""}>
      <label class="check-item"><input type="checkbox" data-f="rd" data-k="when_days" ${w.days ? "checked" : ""}> số ngày học</label>;
      <select data-f="rd" data-k="when_parity"><option value=""></option>${["chẵn", "lẻ"].map((x) =>
        `<option ${w.parity === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>`,
    "Để trống: luật áp dụng cho mọi môn.") : "";
  const extra = [
    block("tags", "Môn có nhãn", checks("tags", CP().tags.subject, row.tags),
      "Môn đánh dấu Có ở các cột của sheet CHƯƠNG TRÌNH HỌC (vd Môn nặng)."),
    placeMain ? "" : place,
    block("exclude", "Trừ môn có nhãn", checks("exclude", CP().tags.subject, row.exclude)),
    block("exclude", "Trừ giờ có nhãn", checks("exclude", CP().tags.slot, row.exclude)),
    roleMain ? "" : role,
    uses.has("when") ? formRow("Áp dụng khi (ghi tay)", text("when"),
      "Điều kiện trên số tiết/tuần của môn, vd >= 6, chẵn hoặc <= số ngày.") : "",
  ].join("");
  const extraUsed = ["exclude", "when", ...(placeMain ? [] : ["days", "periods", "sessions"]), ...(roleMain ? [] : ["role"])]
    .some((k) => listOf(row[k]).length) || tagsOf(CP().tags.subject) || (!placeMain && tagsOf(CP().tags.slot));

  let html = formRow("Loại luật", `<select data-f="rd" data-k="type">${typeOptions(typeValue(row))}</select>`,
    kind.key === "tu_ghep" ? (m ? m.note : "Chọn một phép đo.") : kind.note);
  if (kind.key === "tu_ghep") {
    html += `<fieldset><legend>Với mỗi</legend>${formBlock("Phạm vi", checks("scope", CP().scopes.map((d) => d.label),
      row.scope), "Chia các tiết thành từng nhóm, vd Lớp + Ngày: luật áp dụng cho mỗi lớp mỗi ngày. Không chọn: cả trường cả tuần.")}
      </fieldset>`;
  }
  if (!native) {
    html += `<fieldset><legend>Các tiết nào</legend>
      ${field("subject", "Môn", text("subject", 'list="subject-list"'), "Một hoặc nhiều môn, cách nhau bằng dấu phẩy; để trống: mọi môn.")}
      ${uses.has("group") ? formRow("Gồm môn tăng cường", `<input type="checkbox" data-f="rd" data-k="group" ${
        fold(row.group) === "co" || row.group === true ? "checked" : ""}>`, "Tính cả các môn tăng cường cùng nhóm.") : ""}
      ${block("grades", "Khối", checks("grades", st.scenario.grades.map(String), row.grades, (g) => `Khối ${g}`))}
      ${field("classes", "Lớp", text("classes", 'list="class-list"'), "Vd 3/1, 3/2; để trống: mọi lớp.")}
      ${roleMain ? role : ""}
      ${extra.trim() ? `<details class="more" ${extraUsed ? "open" : ""}><summary>Thêm điều kiện</summary>${extra}</details>` : ""}
      </fieldset>`;
    if (placeMain && place.trim()) html += `<fieldset><legend>Vào giờ nào</legend>${place}</fieldset>`;
  }
  if (kind.key === "tu_ghep") {
    const derived = m && m.key === "so_tiet" ? 'list="derived-list"' : "";
    const thenRows = [
      field("op", "So sánh", `<select data-f="rd" data-k="op"><option value=""></option>${(m ? m.ops : []).map((o) =>
        `<option value="${esc(opLabel(o))}" ${opLabel(o) === row.op || o === row.op ? "selected" : ""}>${esc(opLabel(o))}</option>`)
        .join("")}</select>`),
      field("number", "Số", `<input type="text" class="short" data-f="rd" data-k="number" value="${esc(row.number ?? "")}" ${derived}>`,
        derived ? `Một số, hoặc ngưỡng theo dữ liệu: ${CP().derived.join(", ")}.` : ""),
      field("count_by", "Đếm theo", `<select data-f="rd" data-k="count_by"><option value=""></option>${CP().scopes.map((d) =>
        `<option value="${esc(d.label)}" ${d.label === row.count_by || d.key === row.count_by ? "selected" : ""}>${esc(d.label)}</option>`)
        .join("")}</select>`, "Đếm số lớp, ngày, cơ sở… khác nhau."),
      field("other", "Môn thứ hai", text("other", 'list="subject-list"'), "Để trống: các môn khác (cùng nhóm nếu Với mỗi có Nhóm môn)."),
      whenBuilder,
    ].join("");
    if (thenRows.trim()) html += `<fieldset><legend>Thì</legend>${thenRows}</fieldset>`;
  } else if (!native && (uses.has("number") || uses.has("other"))) {
    html += `<fieldset><legend>Thì</legend>
      ${field("number", "Số", `<input type="number" min="1" step="1" data-f="rd" data-k="number" value="${esc(row.number ?? "")}">`)}
      ${field("other", "Môn thứ hai", text("other", 'list="subject-list"'))}</fieldset>`;
  }
  const soft = !row.hard && !native;
  html += `<fieldset><legend>Mức</legend>
    ${formRow("Luật này", `<select data-f="rd" data-k="hard_mode" ${native ? "disabled" : ""}>${["Bắt buộc", "Ưu tiên"].map((x) =>
      `<option ${(x === "Bắt buộc") === Boolean(row.hard) ? "selected" : ""}>${x}</option>`).join("")}</select>`,
      native ? "Luật này chỉ có dạng bắt buộc; muốn bỏ thì xóa luật." : "Bắt buộc: TKB phải theo đúng. Ưu tiên: cố theo, không theo được thì bị trừ điểm.")}
    ${soft && !row.points ? formRow("Mức ưu tiên", `<select data-f="rd" data-k="level">${S.custom.levels.map((x) =>
      `<option ${levelWord(row.level) === x ? "selected" : ""}>${x}</option>`).join("")}</select>`,
      "Thấp, Vừa, Cao, Rất cao là 100, 400, 1500, 5000 điểm trừ mỗi lần không theo.") : ""}
    <details class="more" ${row.points ? "open" : ""}><summary>Nâng cao</summary>
      ${soft ? formRow("Điểm", `<input type="number" min="1" step="1" data-f="rd" data-k="points" value="${esc(row.points ?? "")}">`,
        "Ghi thẳng điểm trừ mỗi lần không theo, thay cho Mức; để trống thì theo Mức.") : ""}
      ${formRow("Nhóm", `<select data-f="rd" data-k="group_label">${groups.map((g) =>
        `<option value="${esc(g)}" ${g === (row.group_label || S.custom.custom_group) ? "selected" : ""}>${esc(g)}</option>`).join("")}</select>`,
        "Chỉ để xếp các luật cho dễ đọc.")}
    </details></fieldset>`;
  $("#rule-body").innerHTML = html;
  $("#class-list").innerHTML = schoolClasses().map((c) => `<option value="${esc(c)}">`).join("");
  $("#derived-list").innerHTML = CP().derived.map((d) => `<option value="${esc(d)}">`).join("");
}
let previewTimer = null;
function previewRule() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(async () => {
    if (!ruleEdit) return;
    try {
      const res = await api("POST", "/api/describe", { scenario: st.scenario, rows: [ruleEdit.row],
        student_rules: st.run.student_rules });
      const r = res.rules[0];
      $("#rule-say").textContent = r.text || "…";
      $("#rule-native").hidden = !r.native;
      $("#rule-lost").hidden = !(ruleEdit && ruleEdit.native && !r.native);
      $("#rule-errors").innerHTML = r.errors.map((e) => `<li>${esc(e.replace(/^LUẬT, dòng \d+: /, ""))}</li>`).join("");
    } catch (err) { fail(err); }
  }, 250);
}
function editRule(el) {
  const d = el.dataset;
  const row = ruleEdit.row;
  let key = d.k;
  if (d.f === "rdlist") {
    const list = listOf(row[d.k]).filter((x) => fold(x) !== fold(d.v));
    if (el.checked) list.push(d.v);
    const tags = [...CP().tags.subject, ...CP().tags.slot];
    const order = { scope: CP().scopes.map((x) => x.label), sessions: SESSIONS(),
      days: frameDays().map(({ d: n }) => `Thứ ${n + 2}`), grades: st.scenario.grades.map(String), tags, exclude: tags }[d.k] || [];
    list.sort((a, b) => order.indexOf(a) - order.indexOf(b));
    row[d.k] = list.join(", ");
  } else if (d.k === "type") {
    setType(row, el.value);
    key = "kind";
  } else if (d.k === "hard_mode") {
    row.hard = el.value === "Bắt buộc";
    key = "hard";
  } else if (d.k.startsWith("when_")) {
    row.when = whenFromBuilder();
    const raw = $('#rule-body [data-k="when"]');
    if (raw) raw.value = row.when;
  } else if (d.k === "group") {
    row.group = el.checked ? "Có" : "";
  } else if (d.k === "number") {
    const t = el.value.trim();
    row.number = /^\d+$/.test(t) ? Number(t) : t || null;
  } else {
    row[d.k] = readInput(el);
  }
  if (["kind", "measure", "hard", "points"].includes(key)) {
    const uses = shown(row);
    for (const c of S.custom.columns) {
      if (!["group_label", "kind", "hard", "level", "points"].includes(c.key) && !uses.has(c.key)) {
        row[c.key] = c.key === "number" ? null : "";
      }
    }
    if (NATIVE_ONLY.includes(kindOf(row).key)) row.hard = true;
    if (row.hard) { row.level = null; row.points = null; } else if (!row.points) row.level = levelWord(row.level);
    if (key !== "points") renderComposer();
  }
  previewRule();
}

// ---------------------------------------------------------------- tab 6: cài đặt chạy, kiểm tra, xếp
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
  const tab = { [S.sheets.staff]: "gv", [S.sheets.luat]: "luat", [S.sheets.custom]: "luat", [S.sheets.roles]: "chucvu" }[sheet] || "mon";
  if (tab === "gv" && staffFilter) { staffFilter = ""; }
  showTab(tab);
  const el = $(`#tab-${tab} [data-row="${row}"]`);
  if (!el) return;
  el.scrollIntoView({ block: "center", behavior: "smooth" });
  el.classList.remove("flash");
  void el.offsetWidth;
  el.classList.add("flash");
}
function msgItem(text, cls) {
  const sheets = [S.sheets.staff, S.sheets.program, S.sheets.roles, S.sheets.luat, S.sheets.custom].join("|");
  const m = text.match(new RegExp(`(${sheets})[:,]? *(?:[Dd]òng (\\d+)|.*?[Dd]òng (\\d+))`));
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
  const tu = COMPOSE_KIND().label;
  $("#kind-list").innerHTML = CP().families.map((f) => `<dt class="family">${esc(f)}?</dt><dd></dd>${[
    ...S.custom.kinds.filter((k) => k.family === f).map((k) => `<dt>${esc(k.label)}</dt><dd>${esc(k.note)}</dd>`),
    ...CP().measures.filter((m) => m.family === f).map((m) => `<dt>${esc(tu)} · ${esc(m.label)}</dt><dd>${esc(m.note)}</dd>`),
  ].join("")}`).join("") + `<dt class="family">${esc(tu)}</dt><dd></dd><dt>${esc(tu)}</dt><dd>${esc(COMPOSE_KIND().note)}</dd>`;
  $("#new-kind").innerHTML = typeOptions(S.custom.kinds[0].label);
}
function renderAll() {
  st.scenario.roles ||= [];
  st.scenario.rules ||= [];
  syncPeriods();
  renderGeneral();
  renderDays();
  renderPeriods();
  renderSubjects();
  renderRoles();
  renderStaff();
  renderRules();
  renderRun();
  $("#file-label").textContent = st.label || "Kịch bản mới";
  updateCounts();
}
// Mỗi bước dựng lại khi mở: bước Chức vụ sửa quy định của môn, bước Môn học hiện ai dạy, nên luôn khớp nhau.
const RENDER_TAB = { mon: () => renderSubjects(), chucvu: () => renderRoles(), gv: () => renderStaff(),
  luat: () => renderRules() };
function showTab(name) {
  if (!$(`#tab-${name}`)) name = "khung";
  if (st) RENDER_TAB[name]?.();
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

// ---------------------------------------------------------------- nhập từ Excel
// File vào V8 (mẫu đã điền, file của trường, file cập nhật) đọc ở máy chủ thành kịch bản; hộp thoại cho chọn phần nào
// lấy vào kịch bản đang soạn. Mỗi phần ứng với một sheet; chọn hết là thay toàn bộ (như Nạp vào giao diện).
const PARTS = [
  { key: "staff", label: "Giáo viên", sheet: "staff", sum: (x) => `${x.staff.length} dòng` },
  { key: "subjects", label: "Môn học và quy định của môn", sheet: "program",
    sum: (x) => `${x.subjects.filter(named).length} môn, khối ${x.grades.join(", ")}` },
  { key: "roles", label: "Chức vụ", sheet: "roles", sum: (x) => `${x.roles.filter(named).length} chức vụ GV chuyên biệt` },
  { key: "frame", label: "Khung giờ và quy định chung", sheet: "rules",
    sum: (x) => `${(x.days || []).filter((d) => d.morning_days).length} ngày học, ${(x.periods || []).length} tiết mỗi ngày` },
  { key: "rules", label: "Luật", sheet: "luat", sum: (x) => `${(x.rules || []).length} luật` },
  { key: "saved", label: "TKB đã xếp", sheet: "saved", sum: () => "giữ TKB nếu vẫn đúng luật" },
];
let importPreset = null; // nút Nhập từ Excel… của một bước: chỉ chọn sẵn phần đó
let imported = null; // {data, label}
function openImport(data, label, preset) {
  imported = { data, label };
  const src = data.scenario;
  const has = new Set((data.sheets || []).map((name) => Object.keys(S.sheets).find((k) => S.sheets[k] === name)));
  if (src.staff.length) has.add("staff"); // không có sheet NHÂN SỰ thì chương trình đọc sheet đầu tiên
  if (has.has("custom")) has.add("luat"); // file của bản trước: luật riêng ở sheet LUẬT RIÊNG
  $("#import-file").textContent = label;
  $("#import-parts").innerHTML = PARTS.filter((p) => p.key !== "saved" || src.saved).map((p) => {
    const inFile = has.has(p.sheet);
    const on = preset ? preset.includes(p.key) : true; // nút ở thanh trên: mặc định thay toàn bộ như mở file
    const staffMode = p.key === "staff" ? `<select id="import-staff-mode" aria-label="Cách nhập giáo viên">
      <option value="replace">thay danh sách đang có</option><option value="append">thêm vào cuối danh sách</option></select>`
      : p.key === "rules" ? `<select id="import-rules-mode" aria-label="Cách nhập luật">
      <option value="replace">thay các luật đang có</option><option value="append">thêm vào cuối (luật chưa có)</option></select>` : "";
    return `<div class="import-part ${inFile ? "" : "off"}"><label><input type="checkbox" data-part="${p.key}" ${on ? "checked" : ""}>
      <b>${esc(p.label)}</b></label><span class="muted">sheet ${esc(S.sheets[p.sheet])} · ${inFile ? esc(p.sum(src))
      : "file không có sheet này: lấy giá trị mặc định"}</span>${staffMode}</div>`;
  }).join("");
  renderImportNotes();
  $("#import-dialog").showModal();
}
function importChoice() {
  return { parts: $$("#import-parts [data-part]").filter((el) => el.checked).map((el) => el.dataset.part),
    all: $$("#import-parts [data-part]").every((el) => el.checked),
    append: ($("#import-staff-mode") || {}).value === "append",
    appendRules: ($("#import-rules-mode") || {}).value === "append" };
}
function renderImportNotes() {
  const src = imported.data.scenario;
  const { parts } = importChoice();
  const notes = [...imported.data.warnings];
  if (parts.includes("staff") && !parts.includes("roles")) { // GV dùng chức vụ chỉ có trong file
    const have = (name) => S.roles.some((r) => key(r) === key(name)) || st.scenario.roles.some((r) => key(r.name) === key(name));
    const subjects = new Set([...subjectNames(), ...src.subjects.map(named)].map(key)); // trùng tên môn: tự có
    const missing = [...new Set(src.staff.map((t) => String(t.role || "").trim())
      .filter((r) => r && !have(r) && !subjects.has(key(r)) && src.roles.some((x) => key(x.name) === key(r))))];
    if (missing.length) notes.push(`Giáo viên trong file có chức vụ ${missing.join(", ")} chưa có ở bước Chức vụ: nên nhập cả phần Chức vụ.`);
  }
  $("#import-notes").innerHTML = notes.length ? `<ul class="msgs">${notes.map((t) => `<li class="warn">${esc(t)}</li>`).join("")}</ul>` : "";
  $("#import-apply").disabled = !parts.length;
}
function applyImport() {
  const { data, label } = imported;
  const { parts, all, append, appendRules } = importChoice();
  if (all && !append && !appendRules) { useImported(data, label); return; }
  const sc = st.scenario;
  const src = data.scenario;
  if (parts.includes("staff")) sc.staff = append ? [...sc.staff, ...src.staff] : src.staff;
  if (parts.includes("subjects")) { sc.subjects = src.subjects; sc.grades = src.grades; }
  if (parts.includes("roles")) sc.roles = src.roles;
  if (parts.includes("frame")) { sc.general = src.general; sc.days = src.days; sc.periods = src.periods; }
  if (parts.includes("rules")) {
    const same = (a, b) => JSON.stringify({ ...a, group_label: "" }) === JSON.stringify({ ...b, group_label: "" });
    sc.rules = appendRules ? [...sc.rules, ...src.rules.filter((r) => !sc.rules.some((x) => same(x, r)))] : src.rules;
  }
  if (parts.includes("saved")) sc.saved = src.saved;
  addImplicitRoles();
  renderAll();
  changed();
  const names = PARTS.filter((p) => parts.includes(p.key)).map((p) => p.label.toLowerCase());
  notify(`Đã nhập từ ${esc(label)}: ${esc(names.join(", "))}` +
    (parts.includes("staff") && append ? ` (thêm ${src.staff.length} giáo viên vào cuối)` : "") + ".", "ok");
}
async function downloadBlob(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

// ---------------------------------------------------------------- sự kiện
let editFrom = null; // tên môn / chức vụ trước khi sửa (đổi tên thì đổi theo ở các bước khác)
function onFocus(e) {
  const d = e.target.dataset || {};
  if (d.f === "subject" || (d.f === "role" && d.k === "name")) editFrom = { f: d.f, i: d.i, value: e.target.value };
}
function onEdit(e) {
  const el = e.target;
  const d = el.dataset;
  if (!d.f && !d.run) return;
  if (d.f === "rd" || d.f === "rdlist") {
    if (e.type === "change" || el.type === "text" || el.type === "number") editRule(el);
    return;
  }
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
  const done = e.type === "change";
  const renamed = () => {
    const from = editFrom && editFrom.f === d.f && Number(editFrom.i) === i ? editFrom.value : null;
    editFrom = { f: d.f, i: d.i, value: el.value };
    return from;
  };
  if (d.f === "general") {
    sc.general[d.k] = v;
    if ((d.k === "morning_periods" || d.k === "afternoon_periods") && done) {
      syncPeriods();
      renderPeriods();
    }
  } else if (d.f === "day") {
    sc.days[i][d.k] = v;
  } else if (d.f === "period") {
    sc.periods[i][d.k] = v;
  } else if (d.f === "subject") {
    sc.subjects[i].name = v;
    if (done) {
      renameSubject(renamed(), v);
      refreshSubjectNumbers();
      renderRoleList();
      if (detail) $("#detail-title").textContent = String(v).trim() || "Môn mới";
    }
  } else if (d.f === "lessons") {
    sc.subjects[i].lessons[d.k] = v;
    if (done) refreshSubjectNumbers();
  } else if (d.f === "rule") {
    sc.subjects[i].rules[d.k] = v;
    if (done && $("#tab-chucvu").classList.contains("active")) renderRoleHints();
  } else if (d.f === "rule-not") {
    sc.subjects[i].rules[d.k] = !v;
    renderRoleHints();
  } else if (d.f === "role") {
    sc.roles[i][d.k] = v;
    if (done) {
      renameRole(renamed(), v);
      renderRoleList();
    }
  } else if (d.f === "role-subject") {
    const role = sc.roles[i];
    const rest = (role.subjects || []).filter((x) => key(x) !== key(d.s));
    role.subjects = v ? [...rest, d.s] : rest;
    // Giữ thứ tự môn như bước 2.
    const order = subjectNames().map(key);
    role.subjects.sort((a, b) => order.indexOf(key(a)) - order.indexOf(key(b)));
    renderRoleHints();
  } else if (d.f === "staff") {
    const t = sc.staff[i];
    t[d.k] = v;
    if (d.k === "role" && done) {
      if (!isHomeroom(t)) t.class = ""; // chỉ Chủ Nhiệm ghi Lớp
      renderStaff();
      if (detail) renderDetail();
    }
  } else if (d.f === "hist") {
    const t = sc.staff[i];
    const rest = histList(t).filter((c) => classKey(c) !== classKey(d.c));
    setHistory(t, v ? [...rest, d.c] : rest);
  } else if (d.f === "off-fixed" || d.f === "off-any") {
    const t = sc.staff[i];
    const o = offState(t.off);
    if (d.f === "off-fixed") {
      const k = `${d.d}|${d.s}`;
      if (v) o.fixed.add(k); else o.fixed.delete(k);
    } else {
      o.any[d.s] = Number.isInteger(v) && v > 0 ? v : 0;
    }
    t.off = offText(o);
    $("#off-note").innerHTML = offNote(t, i);
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
  const imp = e.target.closest("[data-import]");
  if (imp) {
    importPreset = [imp.dataset.import];
    $("#file-open").click();
    return;
  }
  const go = e.target.closest("[data-go]");
  if (go) {
    showTab(go.dataset.go);
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const sc = st.scenario;
  const i = Number(btn.dataset.i);
  switch (btn.dataset.act) {
    case "edit-subject":
      openDetail("subject", i);
      return;
    case "edit-staff":
      openDetail("staff", i);
      return;
    case "hist-grade": {
      const t = sc.staff[i];
      const grade = schoolClasses().filter((c) => String(classOrder(c)[0]) === btn.dataset.g);
      const chosen = new Set(histList(t).map(classKey));
      const all = grade.every((c) => chosen.has(classKey(c)));
      const keys = new Set(grade.map(classKey));
      setHistory(t, all ? histList(t).filter((c) => !keys.has(classKey(c))) : [...histList(t), ...grade]);
      $("#hist-box").innerHTML = historyBox(t, i);
      break;
    }
    case "hist-drop": {
      const t = sc.staff[i];
      setHistory(t, histList(t).filter((c) => c !== btn.dataset.c));
      $("#hist-box").innerHTML = historyBox(t, i);
      break;
    }
    case "off-drop": {
      const t = sc.staff[i];
      const o = offState(t.off);
      o.other.splice(Number(btn.dataset.k), 1);
      t.off = offText(o);
      $("#off-box").innerHTML = offBox(t, i);
      break;
    }
    case "del-subject": {
      const name = named(sc.subjects[i]);
      if (!confirm(`Xóa môn "${name || "(chưa đặt tên)"}"?`)) return;
      sc.subjects.splice(i, 1);
      for (const role of sc.roles) role.subjects = (role.subjects || []).filter((x) => key(x) !== key(name));
      renderSubjects();
      break;
    }
    case "add-role":
    case "add-role-for": {
      const s = btn.dataset.s || "";
      sc.roles.push({ name: s, subjects: s ? [s] : [] });
      renderRoles();
      renderRoleList();
      const card = $$("#role-cards .role").pop();
      card?.scrollIntoView({ block: "center", behavior: "smooth" });
      card?.querySelector(".role-name")?.focus();
      break;
    }
    case "del-role": {
      const role = sc.roles[i];
      const n = teachersOf(role.name);
      if (!confirm(`Xóa chức vụ "${named(role) || "(chưa đặt tên)"}"?` +
        (n ? ` ${n} giáo viên đang giữ chức vụ này sẽ chưa có chức vụ (chọn lại ở bước 4).` : ""))) return;
      if (n) for (const t of sc.staff) if (key(t.role) === key(role.name)) t.role = "";
      sc.roles.splice(i, 1);
      renderRoles();
      renderRoleList();
      break;
    }
    case "del-staff":
      sc.staff.splice(i, 1);
      renderStaff();
      break;
    case "edit-rule":
      openRule(i);
      return;
    case "del-rule":
      sc.rules.splice(i, 1);
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
  document.addEventListener("focusin", onFocus);
  document.addEventListener("input", onEdit);
  document.addEventListener("change", onEdit);
  document.addEventListener("click", (e) => onClick(e).catch(fail));
  $$(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("#btn-new").onclick = () => newScenario().catch(fail);
  $("#file-open").onchange = async (e) => {
    const file = e.target.files[0];
    const preset = importPreset;
    importPreset = null;
    e.target.value = "";
    if (!file) return;
    try {
      const data = await api("POST", "/api/import", await file.arrayBuffer(),
        { headers: { "X-File-Name": encodeURIComponent(file.name) } });
      openImport(data, file.name, preset);
    } catch (err) { fail(err); }
  };
  $("#import-parts").addEventListener("change", renderImportNotes);
  $("#import-dialog").addEventListener("close", () => {
    if ($("#import-dialog").returnValue === "apply" && imported) applyImport();
    imported = null;
  });
  $("#btn-template").onclick = async () => {
    try {
      downloadBlob(await api("GET", "/api/template", undefined, { blob: true }), "Mau_Input_V8.xlsx");
    } catch (err) { fail(err); }
  };
  $("#btn-export").onclick = async () => {
    try {
      const blob = await api("POST", "/api/export", { scenario: st.scenario, name: st.run.name }, { blob: true });
      downloadBlob(blob, `${st.run.name || "kich_ban"}.xlsx`);
    } catch (err) { fail(err); }
  };
  $("#btn-add-subject").onclick = () => {
    const lessons = Object.fromEntries(st.scenario.grades.map((g) => [String(g), null]));
    st.scenario.subjects.push({ name: "", lessons, rules: newSubjectRules() });
    renderSubjects();
    changed();
    $$("#subject-table tbody tr").pop()?.querySelector("input")?.focus();
  };
  $("#subject-grid").onchange = (e) => {
    subjectGrid = e.target.checked;
    try { localStorage.setItem(GRID_KEY, subjectGrid ? "1" : ""); } catch { /* bỏ qua */ }
    renderSubjects();
  };
  $("#detail-dialog").addEventListener("close", () => {
    const kind = detail && detail.kind;
    detail = null;
    if (kind === "subject") renderSubjects();
    if (kind === "staff") renderStaff();
  });
  $("#staff-filter").onchange = (e) => { staffFilter = e.target.value; renderStaff(); };
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
  $("#btn-add-rule").onclick = () => openRule(-1, $("#new-kind").value);
  $("#btn-rules-export").onclick = async () => {
    try {
      const blob = await api("POST", "/api/rules_file", { scenario: st.scenario, name: st.run.name }, { blob: true });
      downloadBlob(blob, `${st.run.name || "kich_ban"}_luat.xlsx`);
    } catch (err) { fail(err); }
  };
  $("#btn-rules-template").onclick = async () => {
    try {
      downloadBlob(await api("POST", "/api/rules_file", { template: true }, { blob: true }), "Mau_Luat.xlsx");
    } catch (err) { fail(err); }
  };
  $("#btn-rules-reset").onclick = async () => {
    if (!confirm("Thay mọi luật đang có bằng các luật có sẵn mặc định (bỏ các luật riêng và các chỗ đã sửa)?")) return;
    try {
      st.scenario.rules = (await api("GET", "/api/new")).scenario.rules;
      renderRules();
      changed();
    } catch (err) { fail(err); }
  };
  $("#rule-dialog").addEventListener("close", () => {
    const edit = ruleEdit;
    ruleEdit = null;
    if ($("#rule-dialog").returnValue !== "ok" || !edit) return;
    if (edit.i < 0) st.scenario.rules.push(edit.row); else st.scenario.rules[edit.i] = edit.row;
    renderRules();
    changed();
  });
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
    addImplicitRoles();
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
  try { subjectGrid = localStorage.getItem(GRID_KEY) === "1"; } catch { /* bỏ qua */ }
  $("#subject-grid").checked = subjectGrid;
  try {
    S = await api("GET", "/api/schema");
  } catch (err) { fail(err); return; }
  const draft = loadDraft();
  if (draft && draft.scenario && draft.scenario.version === S.version) {
    st = { ...draft, run: { ...S.run_defaults, ...(draft.run || {}) } };
    if (!st.scenario.roles) { st.scenario.roles = []; addImplicitRoles(); } // bản nháp trước khi có bước Chức vụ
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
