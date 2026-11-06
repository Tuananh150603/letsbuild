# Manager guide — quy trình vận hành của quản lý

Dành cho Muse quản lý. Nhân viên không sửa file này.

## Vòng lặp hàng ngày

1. **Tạo task:** `python3 tools/board.py new --title "..." --type <loại>
   --channel <kênh>`, rồi mở task file trong `board/queue/` điền
   spec + tiêu chí nghiệm thu đầy đủ trước khi giao. Task không có
   tiêu chí nghiệm thu rõ thì chưa được giao.
2. **Kiểm tra board:** `python3 tools/board.py list` — xem queue/doing/
   done, claim nào quá 24h (STALE) thì trả về queue.
3. **QA submission:** đọc output trong `outputs/<ID>/` + `report.md`,
   đối chiếu từng tiêu chí nghiệm thu. Duyệt:
   `python3 tools/board.py approve <ID>`. Cần sửa:
   `python3 tools/board.py rework <ID> --note "..."` (ghi rõ sửa
   cái gì, task tự về queue).
4. **Ráp + chốt cuối:** chỉ quản lý mới ráp các output thành sản
   phẩm cuối và quyết định giao/đăng.

## Quy trình chuẩn — áp dụng ngay (Han chốt 06/11 ~21:51)

Rút gọn từ quy trình dự án cấp quốc gia (CMMI + mô hình V), chỉ lấy
4 thứ rẻ mà hiệu quả nhất. Áp dụng cho MỌI task từ nay, không ngoại lệ.

### 1. Truy vết yêu cầu → test (traceability)
- Mỗi task phải có bảng truy vết: yêu cầu nào (trong spec) →
  tiêu chí nghiệm thu nào → test bằng cách nào. Viết trong task file
  hoặc spec, trước khi giao task.
- Không có truy vết thì chưa giao task (giống như task không có
  tiêu chí nghiệm thu thì chưa được giao).

### 2. Cổng chất lượng (quality gate)
- Mỗi task chỉ được archive khi QA kiểm chứng BẰNG TAY đạt TẤT CẢ
  tiêu chí nghiệm thu. Không đạt 1 tiêu chí → rework, không "duyệt
  tạm rồi sửa sau".
- Người làm KHÔNG được tự chấm mình: QA luôn do quản lý (hoặc 1
  worker khác làm peer QA) thực hiện, không phải người làm task đó.

### 3. Test sau mỗi task (đã là luật)
- Xong task nào test ngay task đó (quản lý QA kiểm chứng bằng tay
  trước khi archive, không tin báo cáo một mình).
- Không gộp nhiều task rồi test một lần ở cuối.

### 4. Phân tích nguyên nhân gốc (root cause)
- Mỗi lỗi tìm ra trong QA phải ghi thêm 1 dòng: **vì sao lỗi này
  xảy ra** (do yêu cầu mơ hồ? do thiếu test? do quy trình? do hiểu
  sai spec?) — ghi vào Ghi chú QA của task + sổ lỗi chung.
- Lỗi lặp lại 2 lần cùng nguyên nhân → sửa quy trình/spec để lỗi
  đó không xảy ra lần 3 (không chỉ sửa output).

## Checklist QA theo loại task

- **Nghiên cứu:** mọi khẳng định có nguồn; nguồn ghi tên + ngày;
  phân biệt rõ fact / suy đoán / chưa xác minh; không bịa số.
- **Fact-check:** đối chiếu từng claim với nguồn gốc (SEC/DOJ/
  paper/nguồn chính thức khi có); claim nào không kiểm được thì
  ghi "chưa xác minh", không viết thành fact.
- **Script:** tiếng Anh; 1 câu = 1 beat (video dài) hoặc theo spec
  task; không mở bằng câu hỏi tu từ; kết bằng hình ảnh; số liệu
  có đơn vị + bối cảnh; đại từ rõ ràng (QA ngược: chỉ nghe voice
  vẫn hiểu).
- **Prompt ảnh:** tiếng Anh; đúng style flat mid-century modern;
  không trang trí thừa; không số/date bịa trong caption; 1 element
  = 1 khối đặc nguyên vẹn.
- **Ảnh:** xem full-size; caption đối chiếu từng câu voice; không
  khung trắng lệch style; không số/date/tên bịa trong ảnh.

## Xử lý claim trùng và claim chết

- 2 claim cùng task: lấy timestamp sớm nhất, báo cho bên còn lại
  bỏ task đó (ghi vào report của họ là đủ, không cần xin lỗi dài).
- Claim quá 24h không có output/report mới: quản lý xóa claim,
  trả task về queue, ghi chú "released: stale claim".

## Task chỉ quản lý làm (không giao)

QA cuối, quyết định đăng/xuất. Lý do: QA cuối là chốt chất lượng
tổng, không được chia nhỏ.

Voice Kokoro + dựng draft CapCut: quản lý CUNG CẤP tool cho nhân
viên qua `docs/worker-toolkit-setup.md` (nhân viên tự chạy trên máy
riêng, không host tập trung). Nhân viên nào chưa cài + verify xong
thì chưa nhận 2 loại task này.

## Nguyên tắc chia task

- Chia theo khâu pipeline (nghiên cứu → fact-check → script →
  prompt/ảnh → draft → QA), không chia ngang 1 câu chuyện hay
  1 cảnh cho nhiều người.
- Mỗi task: 1 đầu ra duy nhất, đo được bằng tiêu chí nghiệm thu.
- Task càng nhỏ càng tốt, nhưng không nhỏ tới mức mất bối cảnh
  (nhân viên phải hiểu task của mình nằm ở đâu trong video).
- **LUẬT CHIA NHỎ + TEST (Han chốt 06/11 ~21:47): chia task nhỏ
  ra; sau mỗi task xong PHẢI test (quản lý QA kiểm chứng bằng tay
  trước khi archive, không tin báo cáo một mình). Không gộp nhiều
  việc vào 1 task rồi test một lần ở cuối.**

## Quy tắc vận hành rút từ các framework khác

- **Lập kế hoạch trước khi tạo task:** từ mục tiêu video, tách
  thành task theo pipeline rồi mới tạo task — không tạo task lẻ tẻ.
- **Release theo pipeline, theo lô:** task phụ thuộc chỉ release
  khi task trước xong; task độc lập release cùng lô để chạy song
  song. Input của task sau link rõ output task trước.
- **Review output cuối, không soi nháp giữa chừng.**
- **Giới hạn rework:** tối đa 2 lần/task; quá thì tự làm hoặc
  escalate cho Han (board.py cảnh báo).
- **Theo dõi chất lượng theo worker:** đọc `board/worker-log.md`
  (board.py tự ghi mỗi lần approve/rework); worker nào tỷ lệ
  rework cao thì train đúng chỗ đó — đó chính là "training" của hệ.
- **Mở rộng việc dần dần:** nhân viên bắt đầu đúng role chính;
  khi tỷ lệ rework thấp thì mở rộng sang việc kề (prompt → QA ảnh/
  style guide, research → ideation, QA → playbook). Không mở rộng
  ồ ạt.

## Vòng cải thiện từ dữ liệu (tới khi bật kiếm tiền)

- Sau mỗi video đăng: kéo số liệu vidIQ (views, engaged, AVD,
  traffic, breakout) ở 24h / 72h / 7 ngày.
- Chẩn đoán theo ma trận CTR/retention: video nào giữ người xem,
  video nào rớt, khác biệt nằm ở hook, chủ đề hay format.
- Kết luận đưa thẳng vào task video tiếp theo (chủ đề, hook,
  format) — không để dữ liệu nằm chết trong file.
- Han chỉ gen ảnh + lấy video về đăng; mọi phân tích và chỉ
  đạo cải thiện là việc của quản lý.
