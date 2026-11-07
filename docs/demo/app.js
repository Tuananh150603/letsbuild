"use strict";

/* LetsBuild app core v1 — frontend (T-010, single-page panels in T-020):
 * one page, five inline panels (Board, Chat, Luật chơi, Hồ sơ agent,
 * Đăng task). A tab shows its panel and hides the others — no page
 * navigation, no reload, no URL change. Task detail opens as a side
 * panel BESIDE the board (board stays visible); closing it returns
 * to the board keeping the scroll position.
 *
 * API contract: docs/app-core-spec.md (exact endpoint names/fields).
 *   GET  /api/board
 *   POST /api/tasks                       {title, type, priority, description}
 *   POST /api/tasks/<id>/claim           {worker}
 *   POST /api/tasks/<id>/submit          {worker, outputs}
 *   POST /api/tasks/<id>/approve         {}            (admin only)
 *   POST /api/tasks/<id>/rework          {qa_note}     (admin only)
 *   GET  /api/rooms/<room>/messages?since=<id>&limit=<n>
 *   POST /api/rooms/<room>/messages      {text}
 *   GET  /api/rules                      -> {rules, agreed} (public)
 *   POST /api/rules/agree                {} -> {ok: true, agreed: true}
 *     (T-017: a token must agree to the public rules before it may
 *     claim a task; claim without agreement -> 403 rules_not_agreed.)
 *   GET  /api/agents/<name>               -> agent profile (public)
 *   POST /api/admin/ban                  {name, reason} (admin only)
 *     (T-018: portfolio + ban. Ban revokes the token, marks the
 *     account banned, bans the owner, writes agent_banned.)
 * Errors are JSON {error: "<code>"} + HTTP status (400/401/403/404).
 *
 * The T-009 backend may not be deployed yet. On load this page tries
 * the real API first; when it is unreachable or the endpoints do not
 * exist yet (network error / 404) it falls back to an in-browser mock
 * with the same semantics, seeded from a real board snapshot, and says
 * so clearly in the header badge. A 401 (backend exists, no token)
 * does NOT auto-fall-back: it shows an error asking for a token, with
 * an explicit "Dùng dữ liệu mẫu" button. API errors are always shown
 * in the red banner — never silent.
 */

var COLUMNS = [
  { key: "queue", label: "Queue" },
  { key: "doing", label: "Doing" },
  { key: "done", label: "Done" },
  { key: "archive", label: "Archive" }
];
var PRIORITY_LABELS = { high: "Cao", medium: "Trung bình", low: "Thấp" };
/* NOTE: task `type` is a FREE string (spec supplement "Mở rộng liên tục"):
   no hardcoded type list anywhere. The create form takes free text
   (with datalist suggestions only); the modal displays the type as-is. */
var ROOMS_FALLBACK = ["team", "manager-worker1"];
var REFRESH_MS = 15000;

var LS_TOKEN = "lb_token_v1";
var LS_NAME = "lb_name_v1";
var LS_ROLE = "lb_role_v1";
var LS_MOCK = "lb_mock_v1";

/* Real board snapshot (outputs/T-006/board.json, updated_at
   2026-11-06T11:22:43Z) used as mock seed. Note: the live board has
   since moved T-005/T-006 to archive; this snapshot is kept because
   it has tasks in "done" so approve/rework can be tested in mock. */
var MOCK_BOARD_SEED = {
  "updated_at": "2026-11-06T11:22:43Z",
  "columns": {
    "queue": [],
    "doing": [],
    "done": [
      { "id": "T-005", "title": "Thiết kế + code giao diện web xem board LetsBuild (worker 1)", "type": "code", "priority": "high", "created": "2026-11-06", "worker": "Muse 1", "claimed_at": "2026-11-06T11:13:52Z" },
      { "id": "T-006", "title": "Script xuất dữ liệu board LetsBuild ra JSON (worker 2)", "type": "code", "priority": "high", "created": "2026-11-06", "worker": "worker 2", "claimed_at": "2026-11-06T11:18:48Z" }
    ],
    "archive": [
      { "id": "T-001", "title": "Verify worker setup — chạy setup 1 lệnh + báo self-test", "type": "other", "priority": "high", "created": "2026-11-06", "worker": "Muse 1" },
      { "id": "T-002", "title": "Verify worker setup — chạy setup 1 lệnh + báo self-test (worker 2)", "type": "other", "priority": "high", "created": "2026-11-06", "worker": "worker 2" },
      { "id": "T-003", "title": "Nghiên cứu repo hướng dẫn agent vẽ Figma + báo cáo cách team áp dụng (worker 1)", "type": "research", "priority": "high", "created": "2026-11-06", "worker": "Muse 1" },
      { "id": "T-004", "title": "Nghiên cứu repo hướng dẫn agent vẽ Figma + báo cáo cách team áp dụng (worker 2)", "type": "research", "priority": "high", "created": "2026-11-06", "worker": "worker 2" }
    ]
  }
};

/* Sample chat messages for the mock. These are SAMPLE data written for
   testing the UI, not real hub messages. */
var MOCK_MESSAGES_SEED = {
  "team": [
    { "id": 1, "room": "team", "from": "manager", "ts": "2026-11-06T10:00:00Z", "text": "Chào cả team, hôm nay build app core GĐ 1 nhé." },
    { "id": 2, "room": "team", "from": "worker 1", "ts": "2026-11-06T10:05:00Z", "text": "Đã rõ, t làm frontend T-010." },
    { "id": 3, "room": "team", "from": "worker 2", "ts": "2026-11-06T10:07:00Z", "text": "T làm backend T-009, cùng spec nhé." }
  ],
  "manager-worker1": [
    { "id": 4, "room": "manager-worker1", "from": "manager", "ts": "2026-11-06T10:10:00Z", "text": "Nhắn riêng với quản lý ở đây nhé." }
  ]
};

/* ---------- Small helpers ---------- */

function deepCopy(obj) { return JSON.parse(JSON.stringify(obj)); }

function utcNow() { return new Date().toISOString().replace(/\.\d{3}Z$/, "Z"); }

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
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

/* Next task id per spec: "T-" + (largest number in all 4 columns + 1). */
function nextTaskId(board) {
  var max = 0;
  COLUMNS.forEach(function (col) {
    (board.columns[col.key] || []).forEach(function (t) {
      var m = /^T-(\d+)$/.exec(String(t.id || ""));
      if (m) max = Math.max(max, parseInt(m[1], 10));
    });
  });
  return "T-" + String(max + 1).padStart(3, "0");
}

function findTask(board, id) {
  for (var i = 0; i < COLUMNS.length; i++) {
    var list = board.columns[COLUMNS[i].key] || [];
    for (var j = 0; j < list.length; j++) {
      if (list[j].id === id) return { task: list[j], column: COLUMNS[i].key, index: j };
    }
  }
  return null;
}

function apiError(status, code) {
  var e = new Error(code);
  e.status = status;
  e.code = code;
  return e;
}

/* Storage shim: localStorage in the browser, in-memory under Node (tests). */
var storage = (function () {
  try {
    if (typeof localStorage !== "undefined") return localStorage;
  } catch (e) { /* fall through */ }
  var mem = {};
  return {
    getItem: function (k) { return Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null; },
    setItem: function (k, v) { mem[k] = String(v); },
    removeItem: function (k) { delete mem[k]; }
  };
})();

/* ---------- Mock API: same contract, in-memory + localStorage ---------- */

var MockApi = {
  _state: null,

  _load: function () {
    if (this._state) return this._state;
    try {
      var raw = storage.getItem(LS_MOCK);
      if (raw) { this._state = JSON.parse(raw); return this._state; }
    } catch (e) { /* corrupted mock state: reseed below */ }
    this._state = {
      board: deepCopy(MOCK_BOARD_SEED),
      messages: deepCopy(MOCK_MESSAGES_SEED),
      nextMsgId: 5,
      user: "worker 1",
      /* T-018 mock agent (seeded so the profile UI can be demoed
         without a backend): one agent with a 2-item portfolio. */
      agents: {
        "demo-agent": {
          name: "demo-agent",
          kind: "agent",
          abilities: ["video-edit", "voice"],
          portfolio: [
            { skill: "video-edit", title: "Video giới thiệu kênh",
              url: "https://example.com/video-1",
              description: "Cắt + dựng video 5 phút, có phụ đề." },
            { skill: "voice", title: "Lồng tiếng bản tin",
              url: "https://example.com/voice-1",
              description: "Giọng đọc bản tin tài chính." }
          ],
          owner: { name: "Demo Owner", contact: "demo@example.com" },
          reputation: 12,
          new_agent: false,
          created: "2026-11-06T10:00:00Z",
          tasks_done: 4,
          banned: false
        }
      },
      /* T-017 mock rules: same text as outputs/T-017/rules.md. */
      rules: "# Luật chơi LetsBuild\n\nLuật chơi công khai của team LetsBuild. Mọi agent (người hay máy)\nđều đọc được luật này trong app, không phải đi hỏi ai. **Agent mới\nphải đọc kỹ và bấm \"Tôi đã đọc và đồng ý\" thì mới được nhận task.**\nĐồng ý luật nghĩa là chấp nhận toàn bộ các điều dưới đây.\n\n## 1. Cách nhận việc / nộp output / QA\n\n- Việc nằm trên board, đi qua 4 cột: Queue → Doing → Done →\n  Archive. Nhận việc = claim task đang ở Queue; làm xong thì nộp\n  (submit) kèm đường dẫn output, task sang Done.\n- Quản lý QA bằng tay: kiểm chứng từng tiêu chí nghiệm thu của task.\n  Đạt hết thì duyệt (approve) → Archive. Chưa đạt thì làm lại\n  (rework) kèm ghi chú QA, task về lại Queue.\n- Báo cáo hoàn thành chỉ báo trên hub (phòng team hoặc 1:1 với quản\n  lý), không báo qua kênh khác. Nộp file/output qua git theo đúng\n  quy trình của team.\n\n## 2. Tiêu chí nghiệm thu + cổng chất lượng\n\n- Mỗi task có bảng truy vết: yêu cầu → tiêu chí nghiệm thu → cách\n  test. Task chỉ được archive khi QA kiểm chứng bằng tay rằng TOÀN\n  BỘ tiêu chí đều pass — không có chuyện \"duyệt trước, sửa sau\".\n- Worker KHÔNG tự chấm điểm việc của mình: QA do quản lý hoặc một\n  worker khác làm.\n- Test ngay sau mỗi task, không dồn test tới cuối.\n- Lỗi do QA tìm ra phải có 1 dòng phân tích nguyên nhân gốc (do spec\n  mơ hồ? thiếu test? quy trình? hiểu sai spec?) trong ghi chú QA.\n  Lỗi lặp lại 2 lần với cùng 1 nguyên nhân thì phải sửa quy trình /\n  spec để nó không xảy ra lần thứ 3.\n\n## 3. Cách tính uy tín\n\n- Làm tốt (đúng tiêu chí, test đầy đủ, báo cáo rõ ràng) thì uy tín\n  tăng. Làm ẩu (nộp khi chưa test, bỏ qua tiêu chí, báo cáo sai sự\n  thật) thì uy tín giảm.\n- Uy tín quyết định việc được nhận: task lớn, task quan trọng chỉ\n  giao cho agent có uy tín cao. Uy tín thấp thì chỉ nhận task nhỏ\n  cho tới khi làm tốt trở lại.\n\n## 4. Agent mới\n\n- Agent mới chỉ nhận task nhỏ cho tới khi làm tốt đủ 3 task. Sau 3\n  task tốt, quản lý mới giao task lớn hơn.\n- Agent mới phải đọc luật này và bấm đồng ý trước khi nhận task đầu\n  tiên. Chưa đồng ý thì hệ thống chặn nhận task.\n\n## 5. Cấm\n\n- Mạo danh người khác (nhận/nộp task dưới tên người khác).\n- Đọc hoặc gửi tin trong phòng chat 1:1 của người khác. Phòng\n  `manager-<tên>` chỉ người đó và quản lý được vào.\n- Gian lận uy tín (tự chấm điểm mình, bịa kết quả test, báo cáo sai).\n- Sửa server live khi chưa được duyệt, hoặc đẩy code lên hub live khi\n  chưa qua QA.\n\n## 6. Trả công\n\n- Trả công chỉ áp dụng sau này, khi GĐ 4 chạy: chỉ trả khi việc đã\n  qua kiểm chứng bằng tay của quản lý. Việc chưa qua QA thì không\n  tính công.\n- Trước GĐ 4, mọi việc trong team chưa có trả công.",
      agreed: false
    };
    this._save();
    return this._state;
  },

  _save: function () {
    try { storage.setItem(LS_MOCK, JSON.stringify(this._state)); } catch (e) { /* storage full/blocked: keep in memory */ }
  },

  reset: function () {
    this._state = null;
    try { storage.removeItem(LS_MOCK); } catch (e) { /* ignore */ }
    return this._load();
  },

  _touch: function (board) { board.updated_at = utcNow(); },

  getBoard: function () {
    return Promise.resolve(deepCopy(this._load().board));
  },

  createTask: function (body) {
    var st = this._load();
    if (!body || !String(body.title || "").trim()) {
      return Promise.reject(apiError(400, "bad input: title is required"));
    }
    var task = {
      id: nextTaskId(st.board),
      title: String(body.title).trim(),
      type: body.type || "other",
      priority: body.priority || "medium",
      created: utcNow().slice(0, 10)
    };
    if (body.description) task.description = String(body.description);
    st.board.columns.queue.push(task);
    this._touch(st.board);
    this._save();
    return Promise.resolve(deepCopy(task));
  },

  /* T-017: same contract as the real API — the mock has its own
     agreed flag, so the Rules modal + claim block work in mock mode. */
  getRules: function () {
    var st = this._load();
    return Promise.resolve({ rules: st.rules, agreed: !!st.agreed });
  },

  agreeRules: function () {
    var st = this._load();
    st.agreed = true;
    this._save();
    return Promise.resolve({ ok: true, agreed: true });
  },

  /* T-018 mock agents: profile read is public; ban is mock-local
     (the real server enforces admin-only + token revocation). */
  getAgent: function (name) {
    var st = this._load();
    var agent = st.agents[name];
    if (!agent) return Promise.reject(apiError(404, "not found"));
    return Promise.resolve(deepCopy(agent));
  },

  banAgent: function (name, reason) {
    var st = this._load();
    var agent = st.agents[name];
    if (!agent) return Promise.reject(apiError(404, "not found"));
    if (!reason || !String(reason).trim()) {
      return Promise.reject(apiError(400, "bad reason"));
    }
    agent.banned = true;
    agent.ban_reason = String(reason).trim();
    this._save();
    return Promise.resolve({ ok: true, name: name, banned: true });
  },

  claimTask: function (id, body) {
    var st = this._load();
    var found = findTask(st.board, id);
    if (!found) return Promise.reject(apiError(404, "not found"));
    /* T-017: no agreement, no claim — mirrors POST /api/tasks/<id>/claim. */
    if (!st.agreed) return Promise.reject(apiError(403, "rules_not_agreed"));
    if (found.column !== "queue") return Promise.reject(apiError(400, "bad state"));
    var task = found.task;
    st.board.columns.queue.splice(found.index, 1);
    task.worker = (body && body.worker) || "worker 1";
    task.claimed_at = utcNow();
    st.board.columns.doing.push(task);
    this._touch(st.board);
    this._save();
    return Promise.resolve(deepCopy(task));
  },

  submitTask: function (id, body) {
    var st = this._load();
    var found = findTask(st.board, id);
    if (!found) return Promise.reject(apiError(404, "not found"));
    if (found.column !== "doing") return Promise.reject(apiError(400, "bad state"));
    var task = found.task;
    st.board.columns.doing.splice(found.index, 1);
    task.worker = (body && body.worker) || task.worker || "worker 1";
    if (body && body.outputs) task.outputs = String(body.outputs);
    st.board.columns.done.push(task);
    this._touch(st.board);
    this._save();
    return Promise.resolve(deepCopy(task));
  },

  approveTask: function (id, role) {
    var st = this._load();
    if (role !== "manager") return Promise.reject(apiError(401, "unauthorized"));
    var found = findTask(st.board, id);
    if (!found) return Promise.reject(apiError(404, "not found"));
    if (found.column !== "done") return Promise.reject(apiError(400, "bad state"));
    var task = found.task;
    st.board.columns.done.splice(found.index, 1);
    st.board.columns.archive.push(task);
    this._touch(st.board);
    this._save();
    return Promise.resolve(deepCopy(task));
  },

  reworkTask: function (id, body, role) {
    var st = this._load();
    if (role !== "manager") return Promise.reject(apiError(401, "unauthorized"));
    if (!body || !String(body.qa_note || "").trim()) {
      return Promise.reject(apiError(400, "bad input: qa_note is required"));
    }
    var found = findTask(st.board, id);
    if (!found) return Promise.reject(apiError(404, "not found"));
    if (found.column !== "done") return Promise.reject(apiError(400, "bad state"));
    var task = found.task;
    st.board.columns.done.splice(found.index, 1);
    task.qa_note = String(body.qa_note).trim();
    delete task.worker;
    delete task.claimed_at;
    st.board.columns.queue.push(task);
    this._touch(st.board);
    this._save();
    return Promise.resolve(deepCopy(task));
  },

  getRooms: function () {
    var st = this._load();
    return Promise.resolve({ rooms: Object.keys(st.messages) });
  },

  getMessages: function (room, since, limit) {
    var st = this._load();
    var list = st.messages[room];
    if (!list) return Promise.reject(apiError(404, "not found"));
    var out = list.filter(function (m) { return m.id > (since || 0); });
    if (limit) out = out.slice(0, limit);
    return Promise.resolve({ room: room, messages: deepCopy(out) });
  },

  sendMessage: function (room, body, from) {
    var st = this._load();
    if (!st.messages[room]) return Promise.reject(apiError(404, "not found"));
    if (!body || !String(body.text || "").trim()) {
      return Promise.reject(apiError(400, "bad input: text is required"));
    }
    var msg = {
      id: st.nextMsgId++,
      room: room,
      from: from || "worker 1",
      ts: utcNow(),
      text: String(body.text).trim()
    };
    st.messages[room].push(msg);
    this._save();
    return Promise.resolve(deepCopy(msg));
  }
};

/* ---------- Real API (fetch, exact spec endpoints) ---------- */

var RealApi = {
  _headers: function (token) {
    var h = { "Content-Type": "application/json" };
    if (token) h["Authorization"] = "Bearer " + token;
    return h;
  },

  _req: function (method, path, body, token) {
    return fetch(path, {
      method: method,
      headers: this._headers(token),
      body: body === undefined ? undefined : JSON.stringify(body)
    }).then(function (resp) {
      return resp.json().then(function (data) {
        if (!resp.ok) {
          var code = (data && data.error) || ("HTTP " + resp.status);
          throw apiError(resp.status, code);
        }
        return data;
      }).catch(function (err) {
        if (err && err.status) throw err;
        throw apiError(resp.status, "bad response");
      });
    }).catch(function (err) {
      if (err && err.status) throw err;
      var net = new Error("network error");
      net.status = 0;
      net.code = "network error";
      throw net;
    });
  },

  getBoard: function (token) { return this._req("GET", "/api/board", undefined, token); },
  createTask: function (body, token) { return this._req("POST", "/api/tasks", body, token); },
  claimTask: function (id, body, token) { return this._req("POST", "/api/tasks/" + encodeURIComponent(id) + "/claim", body, token); },
  submitTask: function (id, body, token) { return this._req("POST", "/api/tasks/" + encodeURIComponent(id) + "/submit", body, token); },
  approveTask: function (id, token) { return this._req("POST", "/api/tasks/" + encodeURIComponent(id) + "/approve", {}, token); },
  reworkTask: function (id, body, token) { return this._req("POST", "/api/tasks/" + encodeURIComponent(id) + "/rework", body, token); },
  getRooms: function (token) { return this._req("GET", "/rooms", undefined, token); },
  getMessages: function (room, since, limit, token) {
    return this._req("GET", "/api/rooms/" + encodeURIComponent(room) + "/messages?since=" + (since || 0) + "&limit=" + (limit || 100), undefined, token);
  },
  getRules: function (token) { return this._req("GET", "/api/rules", undefined, token); },
  agreeRules: function (token) { return this._req("POST", "/api/rules/agree", {}, token); },
  getAgent: function (name) { return this._req("GET", "/api/agents/" + encodeURIComponent(name), undefined, undefined); },
  banAgent: function (name, reason, token) { return this._req("POST", "/api/admin/ban", { name: name, reason: reason }, token); },
  sendMessage: function (room, body, token) { return this._req("POST", "/api/rooms/" + encodeURIComponent(room) + "/messages", body, token); }
};

/* ---------- App state ---------- */

var state = {
  mode: null,              /* "real" | "mock" | "needs-token" */
  token: "",
  name: "worker 1",
  role: "worker",
  board: null,
  rooms: ROOMS_FALLBACK.slice(),
  room: "team",
  lastMsgId: 0,
  detailTask: null,
  detailColumn: null,
  rulesAgreed: false,
  rulesText: "",
  /* T-020: which panel is showing; board scroll saved across panels. */
  panel: "board",
  boardScrollY: 0
};

function $(id) { return document.getElementById(id); }

function showError(msg) {
  var banner = $("error-banner");
  $("error-text").textContent = msg;
  banner.hidden = false;
}

function hideError() { $("error-banner").hidden = true; }

function showNotice(msg) {
  var banner = $("notice-banner");
  $("notice-text").textContent = msg;
  banner.hidden = false;
  setTimeout(function () { banner.hidden = true; }, 5000);
}

function setModeBadge() {
  var badge = $("mode-badge");
  var resetBtn = $("reset-mock-btn");
  var mockBtn = $("use-mock-btn");
  if (state.mode === "real") {
    badge.textContent = "API thật";
    badge.className = "badge badge-green";
    resetBtn.hidden = true;
    mockBtn.hidden = true;
  } else if (state.mode === "mock") {
    badge.textContent = "Dữ liệu mẫu (mock) — API thật chưa sẵn sàng";
    badge.className = "badge badge-amber";
    resetBtn.hidden = false;
    mockBtn.hidden = true;
  } else {
    badge.textContent = "Cần token để dùng API thật";
    badge.className = "badge badge-gray";
    resetBtn.hidden = true;
    mockBtn.hidden = false;
  }
}

/* One call site for board mutations: real or mock, same shapes. */
function api() { return state.mode === "real" ? RealApi : MockApi; }

function apiGetBoard() {
  if (state.mode === "real") return RealApi.getBoard(state.token);
  return MockApi.getBoard();
}

function apiGetRooms() {
  if (state.mode === "real") {
    return RealApi.getRooms(state.token).then(function (r) { return r.rooms || ROOMS_FALLBACK; })
      .catch(function () { return ROOMS_FALLBACK; });
  }
  return MockApi.getRooms().then(function (r) { return r.rooms; });
}

function apiGetMessages(room, since, limit) {
  if (state.mode === "real") return RealApi.getMessages(room, since, limit, state.token);
  return MockApi.getMessages(room, since, limit);
}

function apiSendMessage(room, text) {
  if (state.mode === "real") return RealApi.sendMessage(room, { text: text }, state.token);
  return MockApi.sendMessage(room, { text: text }, state.name);
}

function apiGetRules() {
  if (state.mode === "real") return RealApi.getRules(state.token);
  return MockApi.getRules();
}

function apiAgreeRules() {
  if (state.mode === "real") return RealApi.agreeRules(state.token);
  return MockApi.agreeRules();
}

function apiGetAgent(name) {
  if (state.mode === "real") return RealApi.getAgent(name);
  return MockApi.getAgent(name);
}

function apiBanAgent(name, reason) {
  if (state.mode === "real") return RealApi.banAgent(name, reason, state.token);
  return MockApi.banAgent(name, reason);
}

function apiCreateTask(body) {
  if (state.mode === "real") return RealApi.createTask(body, state.token);
  return MockApi.createTask(body);
}

function apiClaimTask(id) {
  if (state.mode === "real") return RealApi.claimTask(id, { worker: state.name }, state.token);
  return MockApi.claimTask(id, { worker: state.name });
}

function apiSubmitTask(id, outputs) {
  var body = { worker: state.name };
  if (outputs) body.outputs = outputs;
  if (state.mode === "real") return RealApi.submitTask(id, body, state.token);
  return MockApi.submitTask(id, body);
}

function apiApproveTask(id) {
  if (state.mode === "real") return RealApi.approveTask(id, state.token);
  return MockApi.approveTask(id, state.role);
}

function apiReworkTask(id, qaNote) {
  if (state.mode === "real") return RealApi.reworkTask(id, { qa_note: qaNote }, state.token);
  return MockApi.reworkTask(id, { qa_note: qaNote }, state.role);
}

/* ---------- Board rendering (T-005 look) ---------- */

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

function renderBoard(data) {
  var columns = (data && data.columns) || {};
  var total = 0;
  COLUMNS.forEach(function (col) {
    var tasks = Array.isArray(columns[col.key]) ? columns[col.key] : [];
    total += tasks.length;
    $("count-" + col.key).textContent = String(tasks.length);
    var box = $("cards-" + col.key);
    if (tasks.length === 0) {
      box.innerHTML = '<p class="column-empty">Chưa có task</p>';
    } else {
      box.innerHTML = tasks.map(function (t) { return cardHtml(t, col.label); }).join("");
    }
  });
  $("updated-at").textContent = formatDate(data && data.updated_at);
  $("empty-state").hidden = total > 0;
}

function loadBoard() {
  return apiGetBoard().then(function (data) {
    state.board = data;
    renderBoard(data);
  }).catch(function (err) {
    showError("Không tải được board: " + (err.code || err.message) +
      (err.status ? " (HTTP " + err.status + ")" : "") +
      ". Kiểm tra token/backend rồi bấm Tải lại.");
  });
}

/* ---------- Detail modal ---------- */

function openDetail(task, columnLabel, columnKey) {
  state.detailTask = task;
  state.detailColumn = columnKey;
  $("modal-id").textContent = task.id || "";
  var pr = $("modal-priority");
  var p = (task.priority || "low").toLowerCase();
  pr.className = "priority priority-" + p;
  pr.textContent = PRIORITY_LABELS[p] || task.priority || "—";
  $("modal-title").textContent = task.title || "(không có tiêu đề)";
  var desc = $("modal-desc");
  if (task.description) { desc.hidden = false; desc.textContent = task.description; }
  else { desc.hidden = true; desc.textContent = ""; }
  $("modal-status").textContent = columnLabel;
  $("modal-worker").textContent = task.worker || "—";
  /* `type` is free-form: display exactly as stored, never mapped/filtered. */
  $("modal-type").textContent = task.type || "—";
  $("modal-created").textContent = formatDay(task.created);
  var claimedRow = $("modal-claimed-row");
  if (task.claimed_at) { claimedRow.hidden = false; $("modal-claimed").textContent = formatDate(task.claimed_at); }
  else { claimedRow.hidden = true; }
  var outRow = $("modal-outputs-row");
  if (task.outputs) { outRow.hidden = false; $("modal-outputs").textContent = task.outputs; }
  else { outRow.hidden = true; }
  var qaRow = $("modal-qa-row");
  if (task.qa_note) { qaRow.hidden = false; $("modal-qa").textContent = task.qa_note; }
  else { qaRow.hidden = true; }
  renderActions(task, columnKey);
  /* T-020: detail opens as a side panel BESIDE the board (board
     stays visible behind it). The page scroll is untouched, so
     closing the panel returns to the exact same spot. */
  $("detail-panel").hidden = false;
}

function closeDetail() {
  $("detail-panel").hidden = true;
  state.detailTask = null;
  state.detailColumn = null;
}

function actionButton(label, cls, onClick) {
  var b = document.createElement("button");
  b.type = "button";
  b.className = "btn " + cls;
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

function renderActions(task, columnKey) {
  var box = $("modal-actions");
  var note = $("modal-note");
  box.innerHTML = "";
  note.hidden = true;
  note.textContent = "";

  if (columnKey === "queue") {
    box.appendChild(actionButton("Nhận", "btn-primary", function () {
      doTaskAction("claim", task, null);
    }));
  } else if (columnKey === "doing") {
    var inp = document.createElement("input");
    inp.type = "text";
    inp.className = "action-input";
    inp.placeholder = "Ghi chú output (không bắt buộc)";
    inp.setAttribute("aria-label", "Ghi chú output");
    box.appendChild(inp);
    box.appendChild(actionButton("Nộp", "btn-primary", function () {
      doTaskAction("submit", task, inp.value.trim());
    }));
  } else if (columnKey === "done") {
    if (state.role === "manager") {
      var qa = document.createElement("input");
      qa.type = "text";
      qa.className = "action-input";
      qa.placeholder = "Lý do làm lại (QA note) — bắt buộc khi Làm lại";
      qa.setAttribute("aria-label", "Lý do làm lại");
      box.appendChild(qa);
      box.appendChild(actionButton("Duyệt", "btn-primary", function () {
        doTaskAction("approve", task, null);
      }));
      box.appendChild(actionButton("Làm lại", "btn-danger", function () {
        if (!qa.value.trim()) { showError("Làm lại cần ghi lý do (QA note)."); return; }
        doTaskAction("rework", task, qa.value.trim());
      }));
    } else {
      note.textContent = "Chỉ quản lý (admin) mới duyệt hoặc làm lại được. Đổi vai trò ở trên cùng nếu bạn là quản lý.";
      note.hidden = false;
    }
  }
  /* archive: no action buttons. */
}

function doTaskAction(kind, task, value) {
  var box = $("modal-actions");
  var buttons = box.querySelectorAll("button");
  buttons.forEach(function (b) { b.disabled = true; });
  var verb = { claim: "Nhận", submit: "Nộp", approve: "Duyệt", rework: "Làm lại" }[kind];
  var p;
  if (kind === "claim") p = apiClaimTask(task.id);
  else if (kind === "submit") p = apiSubmitTask(task.id, value || undefined);
  else if (kind === "approve") p = apiApproveTask(task.id);
  else p = apiReworkTask(task.id, value);
  p.then(function () {
    closeDetail();
    showNotice("Đã " + verb.toLowerCase() + " task " + task.id + ".");
    return loadBoard();
  }).catch(function (err) {
    buttons.forEach(function (b) { b.disabled = false; });
    showError("Không " + verb.toLowerCase() + " được task " + task.id + ": " +
      (err.code || err.message) + (err.status ? " (HTTP " + err.status + ")" : "") +
      ". Board không đổi — kiểm tra lại trạng thái task / quyền rồi thử lại.");
    /* T-017: claim blocked until the agent agrees to the rules —
       open the Rules modal so they can agree right away. */
    if (kind === "claim" && err.status === 403 && err.code === "rules_not_agreed") {
      loadRules().then(openRules);
    }
  });
}

/* ---------- Agents (T-018) ---------- */

function agentSummaryHtml(profile) {
  var owner = profile.owner && profile.owner.name
    ? escapeHtml(profile.owner.name)
    : "—";
  var abilities = (profile.abilities || []).map(escapeHtml).join(", ") || "—";
  var banned = profile.banned
    ? ' <span class="badge badge-red">ĐÃ BỊ BAN</span>' : "";
  return "<strong>" + escapeHtml(profile.name || "?") + "</strong>" + banned +
    "<br>Loại: " + escapeHtml(profile.kind || "agent") +
    " · Uy tín: " + escapeHtml(profile.reputation) +
    " · Task đã làm: " + escapeHtml(profile.tasks_done) +
    "<br>Kỹ năng: " + abilities +
    "<br>Chủ sở hữu: " + owner +
    (profile.new_agent ? "<br>Agent mới (chưa đủ 3 task tốt)." : "");
}

function renderAgentProfile(profile) {
  var box = $("agent-profile");
  box.hidden = false;
  $("agent-summary").innerHTML = agentSummaryHtml(profile);
  var list = $("agent-portfolio");
  var items = profile.portfolio || [];
  if (!items.length) {
    list.innerHTML = '<li class="portfolio-empty">Chưa có portfolio.</li>';
  } else {
    list.innerHTML = items.map(function (it) {
      var link = it.url
        ? ' — <a href="' + escapeHtml(it.url) + '" target="_blank" rel="noopener">' + escapeHtml(it.url) + "</a>"
        : "";
      var desc = it.description ? "<br>" + escapeHtml(it.description) : "";
      return '<li><strong>' + escapeHtml(it.skill || "?") + "</strong>: " +
        escapeHtml(it.title || "(không có tiêu đề)") + link + desc + "</li>";
    }).join("");
  }
  var banned = $("agent-banned");
  if (profile.banned) {
    banned.hidden = false;
    banned.textContent = "Agent này đã bị ban" +
      (profile.ban_reason ? " — lý do: " + profile.ban_reason : "") +
      (profile.banned_at ? " (" + formatDate(profile.banned_at) + ")" : "");
  } else {
    banned.hidden = true;
    banned.textContent = "";
  }
}

function openAgent() { showPanel("agent"); }
function closeAgent() { showPanel("board"); }

/* ---------- Panels (T-020) ---------- */

/* Show one panel, hide the rest. No navigation, no reload, no URL
   change — the tab click only toggles `hidden`. The board's scroll
   position is saved when leaving it and restored when coming back,
   so switching tabs never loses your place on the board. */
function showPanel(name) {
  if (state.panel === "board" && name !== "board") {
    state.boardScrollY = (typeof window !== "undefined" && window.scrollY) || 0;
  }
  state.panel = name;
  var panels = document.querySelectorAll(".panel");
  for (var i = 0; i < panels.length; i++) {
    var el = panels[i];
    el.hidden = el.getAttribute("data-panel") !== name;
  }
  var tabs = document.querySelectorAll(".tab-btn");
  for (var j = 0; j < tabs.length; j++) {
    var tab = tabs[j];
    var active = tab.getAttribute("data-panel") === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  }
  if (name === "board" && typeof window !== "undefined" && window.scrollTo) {
    window.scrollTo(0, state.boardScrollY || 0);
  }
}

/* ---------- Rules (T-017) ---------- */

function renderRules() {
  var text = $("rules-text");
  text.textContent = state.rulesText || "Chưa tải được luật chơi.";
  var status = $("rules-status");
  var agreeBtn = $("rules-agree-btn");
  if (state.rulesAgreed) {
    status.hidden = false;
    status.textContent = "Bạn đã đồng ý luật chơi — có thể nhận task.";
    agreeBtn.disabled = true;
    agreeBtn.textContent = "Đã đồng ý ✓";
  } else {
    status.hidden = false;
    status.textContent = "Bạn chưa đồng ý luật chơi — nhận task sẽ bị chặn (403) cho tới khi bấm đồng ý.";
    agreeBtn.disabled = false;
    agreeBtn.textContent = "Tôi đã đọc và đồng ý";
  }
}

function openRules() {
  renderRules();
  showPanel("rules");
}

function closeRules() { showPanel("board"); }

function loadRules() {
  if (!state.mode || state.mode === "needs-token") return Promise.resolve();
  return apiGetRules().then(function (res) {
    state.rulesText = (res && res.rules) || "";
    state.rulesAgreed = !!(res && res.agreed);
    if (!state.rulesAgreed) {
      showNotice("Bạn chưa đồng ý luật chơi — bấm “Luật chơi” ở trên cùng để đọc và đồng ý trước khi nhận task.");
    }
  }).catch(function (err) {
    state.rulesText = "";
    showError("Không tải được luật chơi: " + (err.code || err.message) +
      (err.status ? " (HTTP " + err.status + ")" : ""));
  });
}

/* ---------- Create-task modal ---------- */

function openCreate() { showPanel("create"); $("create-title-input").focus(); }
function closeCreate() { showPanel("board"); }

/* ---------- Chat ---------- */

function renderRooms() {
  var list = $("room-list");
  list.innerHTML = "";
  state.rooms.forEach(function (room) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "room-btn" + (room === state.room ? " active" : "");
    b.textContent = "#" + room;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", room === state.room ? "true" : "false");
    b.addEventListener("click", function () { switchRoom(room); });
    list.appendChild(b);
  });
  var input = $("chat-input");
  input.placeholder = "Nhắn vào #" + state.room + "…";
}

function msgHtml(msg) {
  return '<div class="chat-msg"><div class="msg-meta"><span class="msg-from">' +
    escapeHtml(msg.from || "?") + '</span> · ' + escapeHtml(formatDate(msg.ts)) +
    '</div><div>' + escapeHtml(msg.text || "") + "</div></div>";
}

function loadChat(initial) {
  if (!state.mode || state.mode === "needs-token") return Promise.resolve();
  var box = $("chat-messages");
  var nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  return apiGetMessages(state.room, initial ? 0 : state.lastMsgId, 100).then(function (res) {
    var msgs = (res && res.messages) || [];
    if (initial) {
      state.lastMsgId = 0;
      box.innerHTML = msgs.length ? "" : '<p class="chat-empty">Chưa có tin nhắn nào trong room này.</p>';
      msgs.forEach(function (m) {
        box.insertAdjacentHTML("beforeend", msgHtml(m));
        if (m.id > state.lastMsgId) state.lastMsgId = m.id;
      });
      box.scrollTop = box.scrollHeight;
    } else if (msgs.length) {
      var empty = box.querySelector(".chat-empty");
      if (empty) empty.remove();
      msgs.forEach(function (m) {
        box.insertAdjacentHTML("beforeend", msgHtml(m));
        if (m.id > state.lastMsgId) state.lastMsgId = m.id;
      });
      if (nearBottom) box.scrollTop = box.scrollHeight;
    }
  }).catch(function (err) {
    showError("Không tải được chat #" + state.room + ": " + (err.code || err.message) +
      (err.status ? " (HTTP " + err.status + ")" : ""));
  });
}

function switchRoom(room) {
  if (room === state.room) return;
  state.room = room;
  state.lastMsgId = 0;
  renderRooms();
  loadChat(true);
}

function sendChat(text) {
  return apiSendMessage(state.room, text).then(function () {
    return loadChat(false);
  }).catch(function (err) {
    showError("Không gửi được tin nhắn: " + (err.code || err.message) +
      (err.status ? " (HTTP " + err.status + ")" : ""));
  });
}

/* ---------- Mode detection ---------- */

function detectMode() {
  /* Try the real API first. 404 / network error => backend not there
     yet => mock. 401 => backend exists but no (valid) token: do not
     silently mock; ask for a token and offer mock explicitly. */
  return RealApi.getBoard(state.token).then(function (data) {
    state.mode = "real";
    setModeBadge();
    state.board = data;
    renderBoard(data);
    return apiGetRooms().then(function (rooms) {
      state.rooms = rooms.length ? rooms : ROOMS_FALLBACK.slice();
      if (state.rooms.indexOf(state.room) === -1) state.room = state.rooms[0];
      renderRooms();
      return loadChat(true);
    }).then(function () { return loadRules(); });
  }).catch(function (err) {
    if (err.status === 401) {
      state.mode = "needs-token";
      setModeBadge();
      showError("API yêu cầu đăng nhập (401): backend đã có nhưng token chưa đúng hoặc chưa nhập. Nhập token ở trên rồi bấm “Lưu token”, hoặc bấm “Dùng dữ liệu mẫu” để test giao diện bằng mock.");
      renderRooms();
      return;
    }
    state.mode = "mock";
    setModeBadge();
    showNotice("Backend API chưa sẵn sàng (" + (err.code || err.message) + ") — đang dùng dữ liệu mẫu (mock) để test giao diện.");
    MockApi._load();
    state.board = MockApi._load().board;
    renderBoard(state.board);
    return apiGetRooms().then(function (rooms) {
      state.rooms = rooms;
      renderRooms();
      return loadChat(true);
    }).then(function () { return loadRules(); });
  });
}

/* ---------- Init ---------- */

function detailPanelOpen() {
  return !$("detail-panel").hidden;
}

function init() {
  state.token = storage.getItem(LS_TOKEN) || "";
  state.name = storage.getItem(LS_NAME) || "worker 1";
  state.role = storage.getItem(LS_ROLE) || "worker";
  $("user-name").value = state.name;
  $("user-role").value = state.role;
  $("api-token").value = state.token;

  $("user-name").addEventListener("change", function () {
    state.name = $("user-name").value.trim() || "worker 1";
    storage.setItem(LS_NAME, state.name);
  });
  $("user-role").addEventListener("change", function () {
    state.role = $("user-role").value;
    storage.setItem(LS_ROLE, state.role);
    if (state.detailTask) renderActions(state.detailTask, state.detailColumn);
  });
  $("save-token-btn").addEventListener("click", function () {
    state.token = $("api-token").value.trim();
    if (state.token) storage.setItem(LS_TOKEN, state.token);
    else storage.removeItem(LS_TOKEN);
    hideError();
    showNotice("Đã lưu token. Đang thử nối lại API thật…");
    detectMode();
  });
  $("use-mock-btn").addEventListener("click", function () {
    state.mode = "mock";
    setModeBadge();
    hideError();
    MockApi._load();
    state.board = MockApi._load().board;
    renderBoard(state.board);
    apiGetRooms().then(function (rooms) {
      state.rooms = rooms;
      renderRooms();
      return loadChat(true);
    });
  });
  $("reset-mock-btn").addEventListener("click", function () {
    MockApi.reset();
    state.board = MockApi._load().board;
    renderBoard(state.board);
    state.lastMsgId = 0;
    loadChat(true);
    showNotice("Đã đặt lại dữ liệu mẫu về trạng thái ban đầu.");
  });

  /* T-020: the five tabs switch inline panels (no navigation). */
  var tabs = document.querySelectorAll(".tab-btn");
  for (var ti = 0; ti < tabs.length; ti++) {
    tabs[ti].addEventListener("click", function (event) {
      var name = event.currentTarget.getAttribute("data-panel");
      if (name === "rules") { loadRules().then(openRules); return; }
      if (name === "agent") { openAgent(); return; }
      if (name === "create") { openCreate(); return; }
      showPanel(name);
    });
  }
  $("agent-lookup-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var name = $("agent-name-input").value.trim();
    if (!name) { showError("Nhập tên agent để xem hồ sơ."); return; }
    $("agent-profile").hidden = true;
    apiGetAgent(name).then(function (profile) {
      renderAgentProfile(profile);
    }).catch(function (err) {
      showError("Không xem được hồ sơ " + name + ": " +
        (err.code || err.message) + (err.status ? " (HTTP " + err.status + ")" : ""));
    });
  });
  $("agent-ban-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var name = $("agent-ban-name").value.trim();
    var reason = $("agent-ban-reason").value.trim();
    if (!name || !reason) { showError("Ban cần tên agent và lý do."); return; }
    var btn = $("agent-ban-btn");
    btn.disabled = true;
    apiBanAgent(name, reason).then(function () {
      showNotice("Đã ban agent " + name + " (token đã thu hồi, owner đã vào danh sách cấm).");
      $("agent-ban-form").reset();
      return apiGetAgent(name);
    }).then(function (profile) {
      renderAgentProfile(profile);
    }).catch(function (err) {
      showError("Không ban được " + name + ": " +
        (err.code || err.message) + (err.status ? " (HTTP " + err.status + ")" : "") +
        ". Chỉ quản lý (token admin) mới ban được.");
    }).then(function () { btn.disabled = false; });
  });
  /* (Rules panel: agree button is wired just below.) */
  $("rules-later-btn").addEventListener("click", closeRules);
  $("rules-agree-btn").addEventListener("click", function () {
    var btn = $("rules-agree-btn");
    btn.disabled = true;
    apiAgreeRules().then(function () {
      state.rulesAgreed = true;
      renderRules();
      showNotice("Đã ghi nhận: bạn đồng ý luật chơi. Giờ có thể nhận task.");
    }).catch(function (err) {
      btn.disabled = false;
      showError("Không ghi nhận được đồng ý: " + (err.code || err.message) +
        (err.status ? " (HTTP " + err.status + ")" : ""));
    });
  });
  $("error-close").addEventListener("click", hideError);
  $("refresh-btn").addEventListener("click", function () { hideError(); loadBoard(); loadChat(false); });
  $("create-cancel").addEventListener("click", closeCreate);
  $("create-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var title = $("create-title-input").value.trim();
    if (!title) { showError("Tạo task cần có tiêu đề."); return; }
    var body = {
      title: title,
      type: $("create-type").value.trim() || "other",
      priority: $("create-priority").value,
      description: $("create-desc").value.trim()
    };
    var btn = $("create-submit");
    btn.disabled = true;
    apiCreateTask(body).then(function (task) {
      closeCreate();
      $("create-form").reset();
      showNotice("Đã tạo task " + task.id + " ở Queue.");
      return loadBoard();
    }).catch(function (err) {
      showError("Không tạo được task: " + (err.code || err.message) +
        (err.status ? " (HTTP " + err.status + ")" : ""));
    }).then(function () { btn.disabled = false; });
  });

  $("board").addEventListener("click", function (event) {
    var card = event.target.closest(".card");
    if (!card || !state.board) return;
    var colKey = null, colLabel = card.getAttribute("data-column");
    COLUMNS.forEach(function (c) { if (c.label === colLabel) colKey = c.key; });
    var tasks = (state.board.columns || {})[colKey] || [];
    var task = null;
    for (var i = 0; i < tasks.length; i++) {
      if (tasks[i].id === card.getAttribute("data-id")) { task = tasks[i]; break; }
    }
    if (task) openDetail(task, colLabel, colKey);
  });
  $("modal-close").addEventListener("click", closeDetail);
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    if (detailPanelOpen()) { closeDetail(); return; }
    if (state.panel !== "board") showPanel("board");
  });

  $("chat-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var text = $("chat-input").value.trim();
    if (!text) return;
    $("chat-input").value = "";
    sendChat(text);
  });

  detectMode();
  /* T-020: inline panels are not disturbed by a board re-render
     (the detail side panel is separate DOM, the forms keep their
     input), so the 15 s refresh runs on every panel. */
  setInterval(function () {
    if (state.mode === "real" || state.mode === "mock") loadBoard();
    loadChat(false);
  }, REFRESH_MS);
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}

/* Exposed for Node-based tests (node --check + mock/real API contract tests). */
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    MockApi: MockApi,
    RealApi: RealApi,
    nextTaskId: nextTaskId,
    findTask: findTask,
    MOCK_BOARD_SEED: MOCK_BOARD_SEED,
    MOCK_MESSAGES_SEED: MOCK_MESSAGES_SEED,
    /* _test lets a Node harness drive exactly the code paths the UI
       calls (api* wrappers read state.mode/token/name/role). */
    _test: {
      setState: function (patch) { Object.keys(patch).forEach(function (k) { state[k] = patch[k]; }); },
      getState: function () { return state; },
      apiGetBoard: apiGetBoard,
      apiCreateTask: apiCreateTask,
      apiClaimTask: apiClaimTask,
      apiSubmitTask: apiSubmitTask,
      apiApproveTask: apiApproveTask,
      apiReworkTask: apiReworkTask,
      apiGetRooms: apiGetRooms,
      apiGetMessages: apiGetMessages,
      apiSendMessage: apiSendMessage,
      apiGetRules: apiGetRules,
      apiAgreeRules: apiAgreeRules,
      apiGetAgent: apiGetAgent,
      apiBanAgent: apiBanAgent,
      renderAgentProfile: renderAgentProfile,
      openAgent: openAgent,
      closeAgent: closeAgent,
      showPanel: showPanel,
      openDetail: openDetail,
      closeDetail: closeDetail,
      detailPanelOpen: detailPanelOpen,
      loadRules: loadRules,
      openRules: openRules,
      closeRules: closeRules
    }
  };
}
