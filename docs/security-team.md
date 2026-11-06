# Đội An ninh — LetsBuild (Red Team)

**Chốt 07/11 ~00:18:** Han tạo 6 Muse mới vào đội an ninh.
Đội xây (blue team) = worker 1 + 2 hiện tại. Đội an ninh (red team)
= 6 người mới, chỉ làm an ninh — tấn công app, tìm lỗ hổng, báo cáo.
Không xây, không sửa, chỉ phá.

## Cách làm việc

Đội xây nộp bản mới → đội an ninh tấn công → báo lỗ → đội xây sửa
→ đội an ninh kiểm tra lại. Vòng lặp liên tục, mỗi bản mới đều bị
tấn công thử.

**Luật cứng:** chỉ tấn công trên máy test riêng, TUYỆT ĐỐI KHÔNG
tấn công hub live của Han. Không sửa code — chỉ tìm lỗ và báo cáo.

## 6 vai trò

### 1. Pentester ứng dụng (2 người)
- Tấn công app + API (xác thực, phân quyền, injection, path
  traversal, trạng thái sai, DoS, rò rỉ dữ liệu) — như T-014.
- Mỗi bản server.py / frontend mới đều phải qua tay pentester.

### 2. Pentester hạ tầng (1 người)
- Tấn công hạ tầng: Docker sandbox (thoát container?), server,
  mạng, cấu hình.
- Kiểm tra quy tắc an toàn container (không privileged, không mount
  Docker socket, giới hạn tài nguyên).

### 3. Phân tích lỗ hổng (1 người)
- Nhận báo cáo từ pentester, xếp hạng mức độ (Critical/High/
  Medium/Low), viết hướng dẫn sửa cho đội xây.
- Giữ sổ lỗ hổng (lỗ nào đã sửa, lỗ nào còn mở, lỗ nào tái phát).

### 4. Kiểm toán smart contract (1 người)
- Kiểm tra smart contract (GĐ 3–4: luật, uy tín, escrow, trả công)
  trước khi đưa lên chain. Tìm lỗ logic, lỗ kinh tế (tấn công
  kinh tế vào cơ chế trả công).
- Chưa có smart contract thì hỗ trợ pentester ứng dụng.

### 5. Giám sát + phản ứng (1 người)
- Giám sát log hub/server tìm dấu hiệu tấn công thật (ai đó đang
  dò quét, thử token lạ, request bất thường).
- Viết quy trình phản ứng khi phát hiện tấn công (khóa token,
  báo quản lý, ghi lại bằng chứng).

## Onboard

Mỗi người mới làm 2 task onboard (như T-001/T-002):
1. **Setup-verify:** chạy setup-worker.sh, gen voice mẫu, import
   draft — chứng minh môi trường làm việc được.
2. **Security-verify:** tấn công mẫu vào test server (bộ 7 nhóm
   của T-014, thu nhỏ) — chứng minh biết tấn công + báo cáo.

Xong 2 task onboard → nhận task an ninh thật.

## Ghi chú

- Đội an ninh càng đông thì càng cần phân công rõ — quản lý giao
  task theo vai trò, không giao trùng.
- Khi hệ sinh thái mở cho agent lạ (GĐ 2), đội an ninh là tuyến
  phòng thủ đầu tiên.
