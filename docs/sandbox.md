# Sandbox cho nhân viên — vào là làm ngay

Vấn đề: `worker-toolkit-setup.md` bắt nhân viên tự cài từng thứ
(ma sát lớn). Sandbox đảo ngược lại: quản lý chuẩn bị sẵn 1 lần,
nhân viên vào, nhận task, lấy dụng cụ làm việc luôn — không tự cài.

## 2 dạng sandbox

### 1. Setup script 1 lệnh (mặc định)

- 1 script chạy trên máy nhân viên: tạo venv, cài Kokoro
  (ghim transformers 4.49.0) + tải weights, clone VectCutAPI,
  cài Whisper-small + ffmpeg, ghi config, chép docs + board.py.
- Chạy được trên mọi máy Linux, không cần Docker.
- **Phân phối:** script nằm trong kho chung (`tools/setup-worker.sh`);
  nhân viên pull về chạy 1 lệnh, không cần Han gửi tay từng người.
- Nhược điểm: chạy trực tiếp trên máy host, không có isolation.

### 2. Docker image (sandbox thật)

- Mọi thứ bake sẵn trong image: tool + weights + config + docs.
- Nhân viên chỉ cần `docker run` là có môi trường làm việc.
- Thêm được isolation: output/code lạ chạy trong container, không
  chạm tới máy host. Với team riêng thì chưa bắt buộc; mở cho người
  lạ thì bắt buộc dùng dạng này.

## Trong sandbox có gì

- **Tool:** Kokoro (giọng am_michael) + VectCutAPI server +
  Whisper-small + ffmpeg + board.py.
- **Config:** tốc độ voice (1.2 dài / 1.21 short), loudnorm
  -14 LUFS / TP -1 dB, palette Plastic Toll, template path CapCut.
- **Docs:** onboarding, protocol, playbook, style guide, luật chung.
- **Board access:** đường dẫn kho chung (Han điền theo từng đợt
  triển khai).
- **Self-test:** script tự kiểm tra sau khi vào — gen 1 câu voice
  test + build 1 draft test → báo OK/FAIL cho quản lý (đưa vào
  team-roster).

## Sandbox KHÔNG giải quyết

- Máy đủ mạnh: disk cho weights (~1–2 GB), RAM, Python (dạng 1)
  hoặc Docker (dạng 2).
- Mạng tới board: Drive/Git/Tailscale — setup riêng.
- Tài khoản riêng cho dịch vụ ngoài: của Muse nào thì Muse đó giữ.

## Quy trình

1. Quản lý build sandbox + chạy self-test thành công trước.
2. Nhân viên vào sandbox → chạy self-test → báo kết quả.
3. Self-test OK thì quản lý mới giao task voice/draft (ghi vào
   team-roster). FAIL thì báo lỗi về quản lý, không nhận task.
