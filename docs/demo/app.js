"use strict";

/* Board viewer — reads board.json from the same folder and renders it.
 *
 * Data source: fetch("board.json"). If that fails (e.g. Chrome blocks
 * fetch from file:// when the page is opened by double-click), the page
 * falls back to FALLBACK_DATA below — a snapshot of the same board.json
 * shipped with the page — and shows a notice. To always read the live
 * JSON, open the folder through a local server, e.g.:
 *   python3 -m http.server 8000
 * then visit http://localhost:8000/index.html
 */

var COLUMNS = [
  { key: "queue", label: "Queue" },
  { key: "doing", label: "Doing" },
  { key: "done", label: "Done" },
  { key: "archive", label: "Archive" }
];

var PRIORITY_LABELS = { high: "Cao", medium: "Trung bình", low: "Thấp" };

/* Snapshot of board.json, used only when fetch is blocked (file://). */
var FALLBACK_DATA = {
  "updated_at": "2026-11-06T11:15:00Z",
  "columns": {
    "queue": [
      { "id": "T-006", "title": "Script xuất dữ liệu board LetsBuild ra JSON (worker 2)", "type": "code", "priority": "high", "created": "2026-11-06", "worker": "worker 2" }
    ],
    "doing": [
      { "id": "T-005", "title": "Thiết kế + code giao diện web xem board LetsBuild (worker 1)", "type": "code", "priority": "high", "created": "2026-11-06", "worker": "Muse 1", "claimed_at": "2026-11-06T11:13:52Z" }
    ],
    "done": [],
    "archive": [
      { "id": "T-001", "title": "Verify worker setup — chạy setup 1 lệnh + báo self-test", "type": "other", "priority": "high", "created": "2026-11-06", "worker": "Muse 1" },
      { "id": "T-002", "title": "Verify worker setup — chạy setup 1 lệnh + báo self-test (worker 2)", "type": "other", "priority": "high", "created": "2026-11-06", "worker": "worker 2" },
      { "id": "T-003", "title": "Nghiên cứu repo hướng dẫn agent vẽ Figma + báo cáo cách team áp dụng (worker 1)", "type": "research", "priority": "high", "created": "2026-11-06", "worker": "Muse 1" },
      { "id": "T-004", "title": "Nghiên cứu repo hướng dẫn agent vẽ Figma + báo cáo cách team áp dụng (worker 2)", "type": "research", "priority": "high", "created": "2026-11-06", "worker": "worker 2" }
    ]
  }
};

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatDate(value) {
  if (!value) return "—";
  var d = new Date(value);
  if (isNaN(d.getTime())) return String(value);
  return d.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
}

function formatDay(value) {
  if (!value) return "—";
  var d = new Date(value.length === 10 ? value + "T00:00:00Z" : value);
  if (isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString("vi-VN");
}

function priorityHtml(priority) {
  var p = (priority || "low").toLowerCase();
  var label = PRIORITY_LABELS[p] || priority || "—";
  return '<span class="priority priority-' + escapeHtml(p) + '">' + escapeHtml(label) + "</span>";
}

function cardHtml(task, columnLabel) {
  var worker = task.worker ? '<span class="worker">' + escapeHtml(task.worker) + "</span>" : "";
  var created = task.created ? "<span>Tạo " + escapeHtml(formatDay(task.created)) + "</span>" : "";
  return (
    '<button type="button" class="card" data-id="' + escapeHtml(task.id) + '" data-column="' + escapeHtml(columnLabel) + '">' +
      '<span class="card-top"><span class="card-id">' + escapeHtml(task.id) + "</span>" + priorityHtml(task.priority) + "</span>" +
      '<span class="card-title">' + escapeHtml(task.title || "(không có tiêu đề)") + "</span>" +
      '<span class="card-meta">' + worker + created + "</span>" +
    "</button>"
  );
}

function render(data) {
  var columns = data.columns || {};
  var total = 0;
  COLUMNS.forEach(function (col) {
    var tasks = Array.isArray(columns[col.key]) ? columns[col.key] : [];
    total += tasks.length;
    document.getElementById("count-" + col.key).textContent = String(tasks.length);
    var box = document.getElementById("cards-" + col.key);
    if (tasks.length === 0) {
      box.innerHTML = '<p class="column-empty">Chưa có task</p>';
    } else {
      box.innerHTML = tasks.map(function (t) { return cardHtml(t, col.label); }).join("");
    }
  });
  document.getElementById("updated-at").textContent = formatDate(data.updated_at);
  document.getElementById("empty-state").hidden = total > 0;
  document.getElementById("board").hidden = total === 0;
}

function openDetail(task, columnLabel) {
  document.getElementById("modal-id").textContent = task.id || "";
  var pr = document.getElementById("modal-priority");
  var p = (task.priority || "low").toLowerCase();
  pr.className = "priority priority-" + p;
  pr.textContent = PRIORITY_LABELS[p] || task.priority || "—";
  document.getElementById("modal-title").textContent = task.title || "(không có tiêu đề)";
  document.getElementById("modal-status").textContent = columnLabel;
  document.getElementById("modal-worker").textContent = task.worker || "—";
  document.getElementById("modal-type").textContent = task.type || "—";
  document.getElementById("modal-created").textContent = formatDay(task.created);
  var claimedRow = document.getElementById("modal-claimed-row");
  if (task.claimed_at) {
    claimedRow.hidden = false;
    document.getElementById("modal-claimed").textContent = formatDate(task.claimed_at);
  } else {
    claimedRow.hidden = true;
  }
  document.getElementById("modal").hidden = false;
}

function closeDetail() {
  document.getElementById("modal").hidden = true;
}

var currentData = null;

function loadBoard() {
  return fetch("board.json", { cache: "no-store" })
    .then(function (resp) {
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      return resp.json();
    })
    .then(function (data) {
      currentData = data;
      var note = document.getElementById("data-source");
      note.hidden = true;
      note.textContent = "";
      render(data);
    })
    .catch(function () {
      /* fetch blocked (file:// in Chrome) or board.json missing/unparsable:
         show the embedded snapshot and say so. */
      currentData = FALLBACK_DATA;
      var note = document.getElementById("data-source");
      note.hidden = false;
      note.textContent =
        "Đang hiển thị dữ liệu nhúng sẵn — trình duyệt chặn đọc file board.json khi mở trực tiếp. " +
        "Để xem dữ liệu live từ board.json, chạy: python3 -m http.server 8000 rồi mở http://localhost:8000/index.html";
      render(FALLBACK_DATA);
    });
}

document.getElementById("board").addEventListener("click", function (event) {
  var card = event.target.closest(".card");
  if (!card || !currentData) return;
  var colKey = COLUMNS.filter(function (c) { return c.label === card.getAttribute("data-column"); })[0];
  var tasks = (currentData.columns || {})[colKey ? colKey.key : ""] || [];
  var task = null;
  for (var i = 0; i < tasks.length; i++) {
    if (tasks[i].id === card.getAttribute("data-id")) { task = tasks[i]; break; }
  }
  if (task) openDetail(task, card.getAttribute("data-column"));
});

document.getElementById("modal-close").addEventListener("click", closeDetail);
document.getElementById("modal-backdrop").addEventListener("click", closeDetail);
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape") closeDetail();
});
document.getElementById("refresh-btn").addEventListener("click", loadBoard);

loadBoard();
