# Bài học từ các framework quản lý agent (áp dụng vào tầng 3)

Nguồn đã đọc (05/11 ~00:00): CrewAI (hierarchical / manager delegation),
Swarms (HierarchicalSwarm), smolagents (managed_agents), Paperclip
(company / ticketing / governance / budgets / training).

Lưu ý quan trọng: code của các framework này KHÔNG bê sang được —
chúng chạy trong 1 chương trình, còn hệ tầng 3 là 10 tài khoản
riêng phối hợp qua file. Chỉ pattern mới áp dụng được.

## Đã áp dụng (và nằm ở đâu trong khung)

1. **Role chuyên môn** (CrewAI: role + goal + backstory; tránh trách
   nhiệm chồng chéo) → mỗi nhân viên có 1 role chính (researcher /
   fact-checker / scriptwriter / image-prompts / qa-checker); quản
   lý giao task đúng role. → onboarding, manager-guide.
2. **Goal ancestry** (Paperclip: task mang theo "why", không chỉ
   title) → task template thêm "Mục tiêu lớn (why)": task phục vụ
   video/mục tiêu nào, vì sao cần. → task-template.
3. **Atomic checkout** (Paperclip: 1 assignee + lock chống tranh
   task) → claim file là lock; đã có claim thì không ghi đè; tranh
   chấp thì quản lý quyết theo timestamp sớm nhất. → README, onboarding.
4. **Rework cap** (CrewAI max_iter + Swarms max_loops + Paperclip
   budget) → tối đa 2 lần rework/task; quá thì quản lý tự làm hoặc
   escalate cho Han. board.py cảnh báo khi rework lần 3. → README,
   manager-guide, board.py.
5. **Report kết quả trước** (chống bottleneck ở quản lý) → report.md
   mở đầu bằng kết quả/kết luận, rồi mới tới nguồn, caveat cuối.
   Quản lý review report trước, chỉ đào sâu output khi cần.
   → onboarding, task-template.
6. **Manager review output cuối, không soi bước trung gian**
   (smolagents: manager không thấy intermediate observations)
   → không yêu cầu worker nộp nháp giữa chừng. → manager-guide.
7. **Không giao lại task ngang** (CrewAI: worker allow_delegation=
   False mặc định) → nhân viên kẹt thì trả task về queue, không tự
   chuyển cho nhân viên khác; trách nhiệm cuối vẫn là người nhận
   task. → onboarding.
8. **Quality metrics + performance review** (Paperclip: training
   pillar) → board.py ghi log approve/rework theo từng worker vào
   `board/worker-log.md`; tỷ lệ rework/worker là tín hiệu train ai,
   train cái gì. → board.py, manager-guide.
9. **Pipeline order + batch** (CrewAI: sequential trước, hierarchical
   sau; context từ task trước) → quản lý release task theo thứ tự
   pipeline; task độc lập release cùng lô để chạy song song; input
   của task sau link rõ output task trước. → manager-guide.

## Chưa áp dụng (và vì sao)

- **Server/UI/dashboard realtime, heartbeat** (Paperclip): thuộc
  phase 2 (mạng riêng + API), v1 file-based chưa cần.
- **Manager tự phát sinh subtask động** (CrewAI hierarchical): làm
  sau khi pipeline tuần tự đã chạy trơn (chính CrewAI cũng khuyên
  start simple).
- **Managed agent chạy trong cùng process** (smolagents): không khả
  thi với 10 tài khoản riêng.
