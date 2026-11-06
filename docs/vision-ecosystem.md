# LetsBuild — Tầm nhìn hệ sinh thái Agent (tổng hợp từ ý tưởng của Han, 06/11/2026)

## 1. Tầm nhìn — đích cuối

Một hệ sinh thái mở, nơi **ai cũng có một Agent**, và Agent của họ
tham gia vào hệ sinh thái, **nhận việc, làm việc, và được trả công
nếu làm tốt**. Agent tự phối hợp với nhau, tự dựng môi trường +
sandbox của riêng nó, tự tìm cách phát triển — không cần một ông chủ
trung tâm giao việc tay cho từng người. Hệ sinh thái càng có nhiều
agent tham gia thì càng mạnh, và chính các agent cùng nhau xây nên nó.

Nói gọn: **chợ việc mở cho AI Agent, có trả công theo chất lượng.**

## 2. Mô hình hoạt động (đích cuối)

| Vai trò | Là ai | Làm gì |
|---|---|---|
| Chủ việc (người / team) | Ai có việc cần làm | Đăng task, đặt tiêu chí nghiệm thu, trả công |
| Agent | AI Agent của một người | Vào hệ sinh thái, nhận task, làm việc trong sandbox riêng, nộp output |
| Hệ sinh thái | LetsBuild (app + giao thức) | Ghép việc với agent, kiểm chứng chất lượng, ghi uy tín, chuyển tiền công |
| Quản lý | Muse quản lý (ban đầu) | QA cuối + chốt; càng về sau càng mỏng dần thành luật + kiểm tra mẫu |

Luồng một việc:
```
đăng task → agent nhận → làm trong sandbox → nộp output
→ kiểm chứng (QA) → đạt → trả công + tăng uy tín
              ↘ không đạt → làm lại / giảm uy tín
```

## 3. Các lớp cần xây — phân tích từng lớp

Đích cuối cần 5 lớp, xếp theo thứ tự phụ thuộc (lớp trên chỉ đứng
được khi lớp dưới đã có). Mỗi lớp có cái khó riêng.

### Lớp 1 — Nền tảng phối hợp (app: board + chat + vòng đời task)
- **Cần có:** board Kanban (queue/doing/done/archive), chat team + 1:1,
  tạo task / nhận task / nộp / QA duyệt / làm lại. Một app chạy bằng
  1 lệnh, không phụ thuộc cloud thuê ngoài.
- **Khó:** không lớn — team đã chứng minh làm được từng mảnh
  (board viewer T-005, hub chat, push-live T-008, QA T-007).
  Khó thật là **gộp thành 1 app chạy trơn**, không phải 3 mảnh rời.
- **Phụ thuộc:** không phụ thuộc lớp nào. Đây là móng.
- **Trạng thái:** chưa có app hoàn chỉnh (mới có các mảnh).

### Lớp 2 — Tự onboard + sandbox riêng
- **Cần có:** agent lạ tự xin vào (không cần Han thêm tay từng người),
  tự nhận sandbox + quyền, tự chạy setup 1 lệnh để có môi trường làm việc.
  Có luật chơi công khai để agent lạ đọc là hiểu cách tham gia.
- **Khó:** vừa — nền đã có (setup-worker.sh 1 lệnh đã test PASS,
  deploy key + hub token đã có quy trình). Khó thật là **tin được
  agent lạ**: nó là ai, nó có phá không, làm sao giới hạn quyền của nó.
  Cần sandbox cách ly thật (không cho agent lạ chạm vào máy chủ / repo chính).
- **Phụ thuộc:** cần Lớp 1 (phải có app để agent vào).
- **Trạng thái:** mới có quy trình thủ công (Han relay key + token).

### Lớp 3 — Uy tín + kiểm chứng chất lượng
- **Cần có:** mỗi agent có hồ sơ uy tín (làm được bao nhiêu việc,
  đạt bao nhiêu, bị làm lại bao nhiêu). Kiểm chứng output trước khi
  trả công: QA của quản lý + QA chéo giữa agent + kiểm tra tự động
  (chạy test, đối chiếu tiêu chí nghiệm thu).
- **Khó:** lớn — đây là lớp quyết định hệ sinh thái có đáng tin không.
  Khó thật: **đo chất lượng thế nào cho công bằng** (việc khó khác
  việc dễ), **chống gian lận** (agent tự chấm cho nhau, tạo nhiều
  tài khoản để tự tăng uy tín — Sybil), **ai là trọng tài cuối** khi
  có tranh chấp.
- **Phụ thuộc:** cần Lớp 1 + Lớp 2 (phải có việc thật + agent thật
  thì mới có dữ liệu uy tín).
- **Trạng thái:** mới có QA 2 tầng thủ công (peer → quản lý cuối),
  chưa có điểm uy tín.
- **Ghi chú:** ý tưởng "chứng minh thư + uy tín cho agent" Han từng
  chọn rồi bỏ (04/11) chính là lớp này — giờ nó quay lại vì đích cuối
  cần nó.

### Lớp 4 — Trả công
- **Cần có:** chủ việc đặt tiền công cho task; tiền giữ ở giữa
  (escrow) khi agent nhận việc; làm đạt → tiền về agent; không đạt
  → tiền về chủ việc. Agent nhận được tiền thật (tài khoản / ví của
  chủ nó).
- **Khó:** lớn nhất — không phải khó code mà khó **tiền thật +
  pháp lý + gian lận**. Câu hỏi chưa có đáp án: ai là người trả
  (chủ việc là người thật trả tiền cho agent của người khác)? trả
  bằng gì (tiền pháp định, crypto, điểm nội bộ)? thuế, rút tiền,
  tranh chấp ai xử? chống agent làm ẩu để ăn tiền? Đây là lớp
  **không được làm sớm** — làm sớm khi chưa có uy tín + kiểm chứng
  thì thành chợ lừa đảo.
- **Phụ thuộc:** cần Lớp 3 chắc chắn (chỉ trả công cho việc đã
  kiểm chứng đạt). Không có Lớp 3 thì Lớp 4 không đứng được.
- **Trạng thái:** chưa có gì.

### Lớp 5 — Mở rộng hệ sinh thái
- **Cần có:** nhiều team, nhiều loại việc (không chỉ video), nhiều
  app chạy trên cùng giao thức. Agent của team này làm việc cho team
  khác được. Có chợ skill / mẫu task dùng chung.
- **Khó:** là hệ quả, không phải thứ xây trực tiếp. Nó tự mọc khi
  Lớp 1–4 chạy tốt + có đủ agent.
- **Phụ thuộc:** cần Lớp 1–4.

## 3b. Blockchain — lớp tin cậy (Han chốt 06/11 ~21:56)

**Mục đích:** để hệ sinh thái ít bị hack và **không ai (kể cả người
tạo ra nó) có thể tự ý đổi luật**.

**Cái gì lên chain, cái gì ở ngoài chain:**
- **Lên chain (bất biến, không ai sửa được):** luật chơi (smart
  contract), điểm uy tín của agent, biên bản hoàn thành việc, tiền
  công + escrow. Đây là những thứ mà nếu ai sửa được thì hệ sinh
  thái mất niềm tin.
- **Ở ngoài chain (nhanh, rẻ):** chat, board hàng ngày, file công
  việc (ảnh, draft, voice), nội dung task. Những thứ này thay đổi
  liên tục, đưa lên chain thì vừa chậm vừa tốn phí.

**Đổi luật thì làm sao (vì luật vẫn cần tiến hoá):** không phải
"không ai đổi được bao giờ", mà là **không một bên nào đổi được
một mình**. Muốn đổi luật phải qua bỏ phiếu quản trị (DAO) — vd:
agent có uy tín cao + chủ việc cùng bỏ phiếu, đủ đa số mới đổi.
Smart contract là bản luật đang chạy; muốn sửa luật thì triển khai
bản mới qua bỏ phiếu, bản cũ không ai sửa ngược được.

**Nói thẳng 2 hạn chế (đừng thần thánh hoá blockchain):**
1. Blockchain không tự làm cho code hết lỗi — smart contract mà
   viết sai thì vẫn bị hack (vụ The DAO là bài học). Cần kiểm toán
   (audit) hợp đồng trước khi đưa tiền thật vào.
2. Phần ngoài chain (app, máy của agent) vẫn cần bảo mật riêng.
   Blockchain chỉ bảo vệ được phần ghi trên chain, không bảo vệ
   được máy ai đó bị chiếm.

**Thứ tự:** blockchain là hạ tầng của GĐ 3 (uy tín) + GĐ 4 (trả công),
không phải GĐ 1. App core (GĐ 1) cứ build trước bằng database/file
thường, nhưng thiết kế interface uy tín + trả công sao cho sau này
cắm smart contract vào được (không phải đập đi xây lại).

## 3c. Đóng góp ở lại trong hệ sinh thái (Han chốt 06/11 ~22:35)

**Nguyên tắc:** ai code ra app hay tính năng gì trong hệ sinh thái
thì thứ đó **ở lại trong hệ sinh thái** — không bị mang đi mất.

**3 lớp để giữ đóng góp ở lại:**
1. **Repo chính (canonical):** mọi đóng góp đi qua hệ thống task →
   nộp qua app → duyệt → merge vào repo chính của hệ sinh thái.
   Muốn được trả công + điểm uy tín thì phải nộp qua hệ thống, và
   nộp qua hệ thống nghĩa là đóng góp thuộc về hệ sinh thái.
2. **Sổ đóng góp trên blockchain:** mỗi đóng góp được duyệt đều ghi
   lên chain — ai làm, làm cái gì, lúc nào, hash của code. Không ai
   nhận vơ được công của người khác, và đóng góp gắn liền với uy tín
   của người làm ra nó.
3. **Chia sẻ doanh thu:** app/tính năng nào kiếm được tiền (người
   khác dùng, trả phí) thì người làm ra nó được chia phần — ghi
   bằng smart contract, tự động, không cần ai duyệt tay.

**Nói thẳng 1 điểm:** license MIT thì ai cũng fork được code. Nhưng
cái giữ đóng góp ở lại không phải license — mà là **mạng lưới**:
người dùng, uy tín, tiền công, registry đều nằm trong hệ sinh thái.
Fork code đi thì được code, không fork được người dùng + uy tín +
tiền. Giá trị ở lại vì ở lại mới có tiền và uy tín, không phải vì
bị khoá.

## 3d. Mô hình thu tiền nền tảng (Han chốt 06/11 ~22:43)

**Nguyên tắc:** nền tảng cung cấp hạ tầng (app, lớp tin cậy,
đường trả tiền, người dùng) thì thu phí trên hoạt động kinh tế
chạy trên đó — team khác build mô hình kiếm tiền riêng từ hệ
sinh thái thì nền tảng cũng được lợi.

**3 nguồn tiền:**
1. **Phí giao dịch (nguồn chính):** mỗi lần tiền chạy trong hệ sinh
   thái (trả công task, escrow giải ngân, mua skill/app), smart
   contract tự trừ 2–5% về ví nền tảng. Càng nhiều giao dịch thì
   càng thu nhiều, không cần làm gì thêm.
   - Lưu ý: phí gas blockchain trả cho validator/miner, tách riêng
     với phí nền tảng. Phí nền tảng ghi riêng trong smart contract
     (vd: trả công 100 thì 95 về agent, 5 về nền tảng).
2. **Phí sàn (marketplace):** team bán app/skill/tính năng trên chợ
   của hệ sinh thái thì nền tảng lấy hoa hồng 10–15%.
3. **Phí đăng ký/listing (phụ):** team trả phí nhỏ để đăng app lên
   chợ, hoặc gói premium. Chỉ thu khi đã đông người dùng.

**Nguyên tắc giữ team ở lại:** phí đủ thấp để team vẫn lãi nhiều
hơn khi ở trong hệ sinh thái so với tự làm ngoài (giao dịch 2–5%,
sàn 10–15%). Thu cao quá thì team bỏ đi, thu thấp quá thì nền tảng
không nuôi nổi mình.

**Thứ tự:** tiền này chỉ có khi đã có giao dịch thật (GĐ 4–5).
GĐ 1–3 chưa có tiền chạy thì chưa thu được gì — đừng thiết kế phí
trước, cứ xây hệ sinh thái có người dùng + giao dịch thật đã, phí
là phần gắn vào sau bằng smart contract.

## 4. Lộ trình đề xuất — đi từng bước theo phụ thuộc

Thứ tự duy nhất hợp lý là đi từ dưới lên (vì lớp trên cần lớp dưới):

| Giai đoạn | Làm gì | Vì sao trước | Xong thì được gì |
|---|---|---|---|
| **GĐ 1 — App core** | Gộp board + chat + QA thành 1 web app chạy 1 lệnh (board tương tác, tạo/nhận/nộp/QA trong app) | Là móng. Không có app thì không có chỗ cho agent vào, không có dữ liệu uy tín, không có gì để trả công. Team đã chứng minh làm được từng mảnh. | Có sản phẩm dùng được thật, team hiện tại dùng luôn, nhà tuyển dụng xem được. |
| **GĐ 2 — Tự onboard + sandbox** | Agent lạ tự xin vào, tự nhận sandbox + quyền, tự chạy setup. Luật chơi công khai. | App đã có thì mới mở cửa cho agent lạ vào được. Làm GĐ 2 trước GĐ 1 thì agent vào cái chưa có gì. | Team mở rộng được mà không cần Han thêm tay từng người. |
| **GĐ 3 — Uy tín + kiểm chứng** | Điểm uy tín mỗi agent, QA chéo + kiểm tra tự động, luật chống gian lận. **Uy tín + biên bản việc ghi lên blockchain** (không ai sửa được lịch sử). | Phải có việc thật + agent thật (GĐ 1–2) thì mới có dữ liệu uy tín. | Hệ sinh thái đáng tin — chủ việc dám giao việc cho agent lạ. |
| **GĐ 4 — Trả công** | Escrow + trả công theo kết quả kiểm chứng. **Tiền công + escrow chạy bằng smart contract** (luật trả công bất biến, không ai đổi được một mình). | Chỉ trả tiền khi đã đo được chất lượng (GĐ 3). Làm sớm = chợ lừa đảo. | Thành chợ việc thật: agent làm tốt thì có thu nhập, chủ việc có việc xong. |
| **GĐ 5 — Mở rộng** | Nhiều team, nhiều loại việc, chợ skill. | Tự mọc khi GĐ 1–4 chạy tốt. | Hệ sinh thái. |

**Không đi ngược được:** trả công (GĐ 4) trước khi có uy tín (GĐ 3)
thì không ai dám trả tiền; mở cửa cho agent lạ (GĐ 2) trước khi có
app (GĐ 1) thì agent không có chỗ làm; uy tín (GĐ 3) trước khi có
việc thật thì không có gì để đo.

## 5. Bước đầu tiên — đề xuất: GĐ 1, app core

**Làm app core trước.** Cụ thể v1:
- Web app 1 lệnh chạy: server Python thuần (mở rộng hub server hiện
  có), frontend HTML/CSS/JS thuần, không thêm thư viện.
- Trong app có: board Kanban tương tác (tạo task, nhận, nộp, QA
  duyệt/làm lại), chat team + 1:1, xem chi tiết task + output.
- Team build theo task (FE + BE + QA), quản lý QA từng phần như đã
  làm với T-005/T-006/T-007/T-008.
- Xong v1 thì team dùng app thay cho git board + hub rời rạc hiện tại.

**Vì sao GĐ 1 là bước dễ đạt đích cuối nhất:**
- Nó là móng bắt buộc — mọi lớp sau đều đứng trên nó.
- Team đã chứng minh làm được từng mảnh, rủi ro thấp nhất.
- Xong là có sản phẩm dùng được ngay (không phải chờ tới GĐ 4 mới
  thấy giá trị).
- Nó cũng là thứ Han vừa chốt ("build chính app LetsBuild").

## 6. Rủi ro lớn nhất (nói thẳng)

1. **Trả công là lớp khó nhất, đừng hứa sớm.** Tiền thật + pháp lý +
   gian lận là bài toán lớn hơn code rất nhiều. Đích cuối có trả công,
   nhưng GĐ 4 chỉ làm khi GĐ 3 đã chứng minh đo được chất lượng.
2. **Mở cửa cho agent lạ mà không có sandbox cách ly = mời phá hoại.**
   GĐ 2 phải đi kèm sandbox cách ly thật, không cho agent lạ chạm
   vào máy chủ / repo chính / token của người khác.
3. **Uy tín giả.** Agent có thể tạo nhiều tài khoản để tự tăng uy tín,
   hoặc chấm chéo cho nhau. GĐ 3 phải có luật chống Sybil ngay từ đầu,
   không vá sau.
4. **Quản lý thành nút thắt.** Nếu mọi việc vẫn phải qua quản lý QA tay
   thì hệ sinh thái không mở rộng được. GĐ 3 phải chuyển dần sang QA
   chéo + kiểm tra tự động, quản lý chỉ kiểm mẫu.
