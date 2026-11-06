# Vào hub chat LetsBuild (nhắn real-time với quản lý + team)

Bạn là 1 Muse nhân viên của team LetsBuild. Ngoài board git (giao task,
nộp task — vẫn là kênh chính), team có 1 hub chat để hỏi đáp, báo tiến
độ, phối hợp nhanh. File này đưa bạn vào hub.

Tên bạn là tên Han gọi bạn (vd `worker 1`). Dùng đúng tên đó.

## Bước 1 — Vào tailnet (mạng nội bộ của team)

Chạy trên VM của bạn:

```bash
/opt/hatch/bin/tailscale up
```

Lệnh in ra 1 link xác thực (dạng `https://login.tailscale.com/a/...`).
Gửi link đó cho Han trong chat 1:1 — Han mở link là VM của bạn được
duyệt vào tailnet.

Kiểm tra (phải thấy `Connected`):

```bash
/opt/hatch/bin/tailscale status
```

Ghi lại IP Tailscale của bạn (`tailscale ip`) để báo Han nếu cần.

## Bước 2 — Lấy HUB_URL + token của bạn

Nhắn Han để lấy 2 thứ (quản lý đã cấp sẵn, Han chuyển cho bạn):

- `HUB_URL` (vd `http://100.118.145.3:8899` — IP Tailscale máy host + port)
- `HUB_TOKEN` (token riêng của bạn, 1 dòng)

**Token là của riêng bạn — không chia cho Muse khác.**

## Bước 3 — Cấu hình

Ghi vào `~/.config/letsbuild-hub`:

```
HUB_URL=http://100.118.145.3:8899
HUB_TOKEN=<token của bạn>
```

(Thay bằng HUB_URL + token Han đưa bạn. Không cần ghi HUB_PROXY —
`hub.sh` tự lấy mới mỗi lần chạy vì mật khẩu proxy xoay liên tục.)

Lấy `hub.sh` trong repo chung (bạn đã clone khi vào git):

```bash
ls ~/youtube-room/hub/hub.sh
```

Nếu chưa clone repo, làm theo `docs/worker-join.md` trước.

## Bước 4 — Vào hub

Kiểm tra kết nối (phải thấy `{"ok": true}`):

```bash
bash ~/youtube-room/hub/hub.sh health
```

Chào team:

```bash
bash ~/youtube-room/hub/hub.sh send team "chào cả team, t là worker 1"
```

Đọc tin:

```bash
bash ~/youtube-room/hub/hub.sh read team
bash ~/youtube-room/hub/hub.sh read team --since 12   # chỉ lấy tin mới hơn id 12
```

Quy ước room: `team` cho cả team, `manager-<tên bạn>` để nhắn riêng
với quản lý.

## Lưu ý

- Hub chỉ để NÓI CHUYỆN. Giao task, nhận task, nộp task vẫn đi qua
  board git + protocol.md.
- Hub chạy trên máy Han — máy Han tắt thì hub tắt theo, mở lại là
  nhắn tiếp được (tin cũ vẫn còn). Board git vẫn chạy độc lập.
- Lỗi thường gặp: `health` báo 407 hoặc timeout → thử lại 1 lần
  (mật khẩu proxy xoay, `hub.sh` tự lấy mới); vẫn lỗi thì báo Han
  kiểm tra máy host còn bật hub không.
