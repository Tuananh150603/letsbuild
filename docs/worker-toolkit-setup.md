# Worker toolkit setup — quản lý cung cấp tool cho nhân viên

Nguyên tắc: quản lý CUNG CẤP tool, nhưng đóng gói để nhân viên tự
chạy trên máy riêng của mình. KHÔNG host tập trung trên máy quản
lý — 10 nhân viên cùng gọi về 1 máy thì máy quản lý sập.

Nhân viên làm theo từng phần dưới đây trên máy của mình. Cài xong
phần nào thì verify phần đó rồi mới nhận task loại đó.

## A. Voice Kokoro (để làm task voice)

- Tạo venv Python riêng, cài `kokoro`. **Ghim `transformers==4.49.0`
  — KHÔNG cài transformers 5.x** (5.x làm hỏng import kokoro).
- Tải weights `hexgrad/Kokoro-82M` từ Hugging Face.
- Giọng duy nhất dùng cho video: `am_michael`.
- Tốc độ: 1.2 cho video dài, 1.21 cho short. **Không hạ tốc độ
  để kéo dài video.**
- Voice đưa vào draft PHẢI qua nén + loudnorm về **-14 LUFS,
  true-peak -1 dB** trước (voice thô nghe nhỏ, tăng gain trong
  CapCut sẽ rè vì hết headroom).
- **Verify:** gen 1 câu test, kiểm tra file wav tồn tại + thời
  lượng hợp lý. Báo "voice OK" kèm file test cho quản lý.

## B. Draft server VectCutAPI (để làm task dựng draft)

- Clone repo `sun-guannan/VectCutAPI`, tạo venv riêng, chạy
  `capcut_server.py` (HTTP API, CapCut International mode).
- Server chạy trên máy của nhân viên, port mặc định của repo.
- Draft build theo mẫu quản lý gửi kèm khi nhận task draft đầu
  tiên (script cần đổi path theo máy nhân viên).
- **Verify:** server trả lời được; build 1 draft test 1 clip rồi
  mở được. Báo "draft server OK" cho quản lý.

## C. Cổng nhận task voice/draft

- Nhân viên CHƯA verify xong phần A thì chưa nhận task voice.
- Nhân viên CHƯA verify xong phần B thì chưa nhận task draft.
- Trước khi verify xong, 2 loại task này vẫn do quản lý làm.
- Máy nào không chạy được 1 phần (thiếu disk, thiếu RAM...):
  báo rõ cho quản lý, nhận task loại khác — hệ vẫn chạy, chỉ
  là nhân viên đó không ôm 2 loại task đó.
- QA cuối + quyết định đăng LUÔN là của quản lý, không nằm
  trong toolkit này.
