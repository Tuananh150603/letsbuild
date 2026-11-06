# LetsBuild App — Spec v1 (GĐ 1: app core)

Mục tiêu: gộp board + chat + QA thành 1 web app chạy bằng 1 lệnh,
thay cho kiểu hiện tại (board trên git + chat trên hub + viewer tĩnh
rời nhau). App này là nền cho GĐ 2–5 trong `docs/vision-ecosystem.md`.

## Stack (cứng)

- **Server:** Python, chỉ dùng thư viện chuẩn (stdlib), mở rộng
  `hub/server.py` hiện có. Không thêm dependency.
- **Frontend:** HTML/CSS/JS thuần, không build step, không framework.
- **Chạy:** `python server.py --host 0.0.0.0 --port 8899 --data-dir ./hub-data`
  rồi mở `http://localhost:8899/` trong trình duyệt.
- **Lưu trữ:** file JSON trong `{data-dir}/` (cùng chỗ hub đang dùng):
  `board.json` (board) + `messages.jsonl` (chat). Không dùng database.

## Dữ liệu

### board.json (giữ nguyên format T-006)
```json
{
  "updated_at": "2026-11-06T12:46:43Z",
  "columns": {
    "queue":   [{ "id": "T-009", "title": "...", "type": "code",
                  "priority": "high", "created": "2026-11-06" }],
    "doing":   [{ "id": "...", "title": "...", "worker": "worker 1",
                  "claimed_at": "2026-11-06T11:13:52Z", "...": "..." }],
    "done":    [{ "id": "...", "...": "..." }],
    "archive": [{ "id": "...", "...": "..." }]
  }
}
```
- Task có thêm trường khi cần: `description` (mô tả), `qa_note`
  (ghi chú QA khi rework), `outputs` (đường dẫn output, nếu có).
- Mọi thay đổi board đều ghi lại `updated_at` (UTC, ISO 8601).

### Chat (giữ nguyên format hub)
- `messages.jsonl`: mỗi dòng 1 message
  `{ "id": 1, "room": "team", "from": "worker 1",
     "ts": "2026-11-06T10:00:00Z", "text": "..." }`.
- Room: `team` (cả team) + `manager-<tên>` (1:1 với quản lý).

## Mở rộng liên tục — thiết kế để tự lớn lên (Han chốt 06/11 ~21:58)

App phải thiết kế để **tự mở rộng liên tục** theo tầm nhìn hệ sinh
thái thật sự — thêm tính năng / loại việc / loại agent mới mà KHÔNG
phải đập core xây lại. Đây là nguyên tắc thiết kế, áp dụng ngay từ
v1 (không phải tính năng làm sau).

### 1. Core nhỏ + ổn định, tính năng là module cắm thêm
- **Core (ít đổi):** xác thực, dữ liệu board, chat, vòng đời task
  (tạo → nhận → nộp → QA). Core càng nhỏ càng tốt, càng ít đổi càng tốt.
- **Module (hay đổi):** loại task mới, bộ kiểm tra QA mới, tích hợp
  mới, khả năng mới của agent. Module cắm vào core qua interface
  rõ ràng, gỡ ra cũng không làm core hỏng.

### 2. API-first — mọi thứ UI làm được thì agent ngoài cũng làm được
- Mọi thao tác trong UI đều đi qua API (`/api/*`). Không có đường
  tắt riêng cho UI.
- Nhờ vậy agent bên ngoài (không qua UI) cũng tạo task, nhận việc,
  nộp output, chat được bằng cùng API đó. Đây là nền để GĐ 2
  (agent lạ tự vào) và GĐ 5 (nhiều app trên cùng giao thức) mọc lên.

### 3. Đăng ký tự động (registry) — cái mới tự khai báo, không sửa tay
- Loại task mới, loại agent mới, bộ kiểm tra mới: tự đăng ký bằng
  1 file manifest (tên, phiên bản, nó làm được gì) — core đọc
  manifest là biết, không cần sửa code core để thêm loại mới.
- V1 làm đơn giản: `type` của task là chuỗi tự do (không hardcode
  danh sách loại); server không từ chối `type` lạ. Frontend hiển thị
  `type` lạ bình thường. Đây là hạt nhân của registry — v1 chỉ cần
  không khoá cứng danh sách.

### 4. Sự kiện (events) — core báo, module nghe
- Core phát sự kiện khi có thay đổi: task tạo xong, task nộp xong,
  QA duyệt xong, chat có tin mới. Module (vd: bộ kiểm tra tự động,
  bộ tính uy tín ở GĐ 3) đăng ký nghe sự kiện đó để chạy việc của nó.
- V1 làm đơn giản: sau mỗi lần ghi `board.json` / `messages.jsonl`,
  core ghi thêm 1 dòng vào `events.jsonl`
  (`{ "ts", "event": "task_submitted", "task_id": "T-009", ... }`).
  Module sau này chỉ cần đọc file này.

### Quy tắc khi thêm tính năng mới (về sau)
- Thêm bằng module/API/registry, không sửa core trừ khi bắt buộc.
- Nếu bắt buộc phải sửa core thì sửa sao cho API cũ vẫn chạy
  (tương thích ngược) — không phá client cũ.

## API (BE — worker 2 làm)

Base: cùng host/port với hub. Mọi API trả JSON. Lỗi trả
`{ "error": "<mã>" }` + HTTP status phù hợp (400 sai input, 401 chưa
xác thực, 404 không có task/room).

Auth: dùng Bearer token như hub hiện có. Token quản lý (admin) làm
được mọi thứ; token worker chỉ làm được việc của mình (nhận/nộp task
của mình, chat). V1 cho phép đơn giản: mọi token đã cấp đều dùng được
API board; riêng approve/rework chỉ admin (quản lý).

| Method | Đường dẫn | Vào | Ra |
|---|---|---|---|
| GET | `/api/board` | — | toàn bộ `board.json` |
| POST | `/api/tasks` | `{ "title", "type", "priority", "description" }` | task mới (id tự tăng `T-010`, `T-011`…) ở `queue` |
| POST | `/api/tasks/<id>/claim` | `{ "worker": "<tên>" }` | task chuyển `queue → doing`, ghi `worker` + `claimed_at` |
| POST | `/api/tasks/<id>/submit` | `{ "worker": "<tên>", "outputs": "<ghi chú output>" }` | task chuyển `doing → done` |
| POST | `/api/tasks/<id>/approve` | `{}` (admin) | task chuyển `done → archive` |
| POST | `/api/tasks/<id>/rework` | `{ "qa_note": "<lý do>" }` (admin) | task chuyển `done → queue`, ghi `qa_note`, xóa claim |
| GET | `/api/rooms/<room>/messages?since=<id>&limit=<n>` | — | `{ "messages": [ ... ] }` |
| POST | `/api/rooms/<room>/messages` | `{ "text": "..." }` | message mới (id tăng dần, `from` lấy từ token) |

Quy tắc:
- Chuyển trạng thái sai (vd claim task đã ở `doing`) → 400
  `{ "error": "bad state" }`.
- `id` task mới = `T-` + số lớn nhất hiện có + 1 (quét cả 4 cột).
- Ghi file nguyên tử (ghi file tạm rồi đổi tên) để không rách file
  khi 2 người cùng ghi.
- Mọi endpoint cũ của hub (`/`, `/board`, `/board.json`,
  `/preview/*`, `/admin/*`) giữ nguyên, không được phá.

## Giao diện (FE — worker 1 làm)

Trang duy nhất `/` (thay cho viewer chat cũ), gồm 2 vùng:
1. **Board (trái, rộng):** 4 cột Queue / Doing / Done / Archive
   (kế thừa giao diện T-005: thẻ trắng, viền xanh trái, badge CAO).
   - Bấm thẻ → mở modal chi tiết (mô tả, người làm, loại, ngày tạo,
     QA note nếu có).
   - Nút "Tạo task" (form: tiêu đề, loại, độ ưu tiên, mô tả).
   - Trong modal: nút Nhận / Nộp / Duyệt / Làm lại (chỉ hiện nút
     hợp với trạng thái + quyền; bấm gọi API tương ứng rồi tải lại board).
2. **Chat (phải, hẹp):** danh sách room (`team` + 1:1), khung tin nhắn,
   ô nhập + nút gửi. Tự làm mới mỗi 15 giây (giống viewer hub).
- Tự làm mới board mỗi 15 giây. Mọi lỗi API hiện thông báo rõ
  (không im lặng).
- Tối giản, nền trắng, 1 màu nhấn xanh #2563eb (giống T-005).

## Nghiệm thu v1 (QA kiểm)

### Bảng truy vết — yêu cầu → tiêu chí → cách test (Han chốt 06/11 ~21:51)

| # | Yêu cầu (spec) | Tiêu chí nghiệm thu | Cách test (quản lý làm bằng tay) |
|---|---|---|---|
| 1 | `GET /api/board` | Trả toàn bộ `board.json` | Gọi API, đối chiếu JSON trả về với file `board.json` trên server |
| 2 | `POST /api/tasks` | Task mới ở Queue, id tự tăng | Tạo task qua API, kiểm tra board: task ở Queue, id = max + 1 |
| 3 | `POST /api/tasks/<id>/claim` | Task `queue → doing`, ghi worker + claimed_at | Claim task, kiểm tra board + file: đúng cột, đủ 2 trường |
| 4 | `POST /api/tasks/<id>/submit` | Task `doing → done` | Nộp task, kiểm tra board: task ở Done |
| 5 | `POST /api/tasks/<id>/approve` | Task `done → archive` (chỉ admin) | Duyệt task, kiểm tra board: task ở Archive; thử duyệt bằng token worker → phải bị từ chối |
| 6 | `POST /api/tasks/<id>/rework` | Task `done → queue` + qa_note, xóa claim | Làm lại task, kiểm tra board: task về Queue, có qa_note, không còn worker/claimed_at |
| 7 | Chat API (GET/POST messages) | Gửi/nhận được ở room `team` | Gửi 1 tin qua API, đọc lại qua API: tin xuất hiện đúng room, đúng người gửi |
| 8 | Chuyển trạng thái sai → 400 | Không hỏng dữ liệu | Thử claim task đã ở Doing, thử duyệt task đang ở Queue → đều 400, board không đổi |
| 9 | Ghi file nguyên tử | Không rách file khi ghi đồng thời | Gọi 2 API ghi cùng lúc, kiểm tra file JSON vẫn đọc được, đủ dữ liệu |
| 10 | Endpoint hub cũ còn chạy | `/board`, `/preview/*`, `/admin/update` vẫn chạy | Mở `/board` + `/preview/board-viewer/` + gọi `/admin/update` (dry-run): đều trả 200 |
| 11 | Frontend: board + chat + modal + form | Đủ giao diện, đúng API T-009 | Mở `/`, tạo task bằng form → thấy ở Queue; bấm thẻ → modal đúng dữ liệu; chat gửi/nhận được |
| 12 | Không thêm dependency | Chạy bằng Python thuần | Chạy server trên máy sạch (chỉ stdlib), không lỗi import |
| 13 | Mở rộng: `type` task tự do + `events.jsonl` | Không khoá cứng loại task; core ghi sự kiện sau mỗi lần ghi board/chat | Tạo task với `type` lạ (vd `"type": "video-edit"`) → tạo được, hiển thị bình thường; kiểm tra file `events.jsonl` có dòng sự kiện sau khi tạo/nhận/nộp/QA task |

1. Chạy 1 lệnh, mở trình duyệt, thấy board + chat.
2. Tạo task → xuất hiện ở Queue. Nhận task → sang Doing.
   Nộp → sang Done. Duyệt → sang Archive. Làm lại → về Queue
   kèm QA note. Mỗi bước đều qua API + ghi đúng file.
3. Chat gửi/nhận được ở room `team`.
4. Chuyển trạng thái sai bị từ chối (400), không hỏng dữ liệu.
5. Các endpoint hub cũ (`/board`, `/preview/*`, `/admin/update`)
   vẫn chạy.
6. Không thêm dependency; server chạy được bằng Python thuần.
