# Setup cho Han — các bước chuẩn bị

Framework đã nằm trong folder `letsbuild/` này. Han làm
theo thứ tự sau để thêm "nhân viên" vào hệ:

## Bước 1: Kho chung (XONG 06/11)

- Repo làm việc: https://github.com/Tuananh150603/youtube-room
  (PRIVATE; repo public `letsbuild` kia chỉ làm portfolio).
- Framework đã push lên repo. Mời 10 tài khoản làm collaborator
  (mỗi con dùng quyền riêng, không dùng chung token).
- File lớn (voice, draft CapCut, ảnh) KHÔNG đưa vào git — để
  Drive riêng, chỉ ghi đường dẫn vào report/task.

## Bước 2: Điền đường dẫn kho chung (XONG 06/11)

- Kho chung đã điền sẵn URL trong `docs/worker-onboarding.md` —
  không cần điền tay nữa.

## Bước 3: Dán onboarding cho từng Muse nhân viên

- Gửi nội dung `docs/worker-onboarding.md` cho mỗi Muse trong
  10 Muse kia (dán vào chat của nó).
- Mỗi Muse tự đặt tên worker của nó (dùng trong claim file).
- Không cần làm gì thêm ở phía Muse nhân viên: nó tự đọc board
  và nhận task.

## Bước 4: Quản lý bắt đầu tạo task thật

- Muse quản lý tạo task đầu tiên bằng
  `python3 tools/board.py new --title "..." --type ... --channel ...`
  rồi điền spec + tiêu chí nghiệm thu vào task file.
- Nhân viên tự nhận task, nộp output, quản lý QA theo
  `docs/manager-guide.md`.

## Lưu ý quan trọng

- Voice Kokoro và dựng draft CapCut: quản lý cung cấp toolkit
  (`docs/worker-toolkit-setup.md`) để nhân viên tự chạy trên máy
  riêng; nhân viên nào verify xong mới nhận 2 loại task này.
- Folder `letsbuild/` trên máy quản lý và folder trên kho chung phải
  đồng bộ: quản lý làm việc trên bản kho chung (không làm trên
  2 bản khác nhau).
- Phase 2 (server API + message queue trên mạng riêng) chỉ làm
  sau khi v1 file-based đã chạy trơn với 10 nhân viên.
