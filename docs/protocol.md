# Protocol trao đổi — LetsBuild

Mọi trao đổi giữa quản lý và nhân viên tuân theo protocol này, KHÔNG
phụ thuộc transport. Protocol định nghĩa từ đầu và không đổi khi đổi
transport: v1 chạy trên file trong kho chung, v2 chạy trên message
queue/WebSocket qua mạng riêng — message và trường giữ nguyên, chỉ
đổi cách truyền.

## Nguyên tắc

- Mọi message đều có: type, task_id, from (manager / tên worker),
  timestamp UTC ISO8601, body.
- Chỉ quản lý mới chuyển task giữa queue/done/archive. Chỉ nhân
  viên mới tạo claim. Chỉ nhân viên đã claim mới nộp task đó.
- Không message ngoài protocol: không chat riêng, không thỏa thuận
  miệng — mọi thứ đi qua message để có log.

## Các message

1. **task_created** (manager → board): tạo task file trong
   `board/queue/` theo task-template (đủ spec + tiêu chí nghiệm thu
   + mục tiêu why).
2. **task_claimed** (worker → board): tạo `board/doing/<ID>.claim.json`
   `{worker, claimed_at}`. Claim đầu tiên thắng; đã có claim thì
   không ghi đè.
3. **task_submitted** (worker → manager): chuyển task file sang
   `board/done/` + ghi output vào `outputs/<ID>/` + `report.md`
   (mở đầu bằng kết quả).
4. **qa_approved** (manager → worker): chuyển task file sang
   `board/archive/` + board.py ghi log vào `worker-log.md`.
5. **qa_rework** (manager → worker): ghi note QA vào task file,
   chuyển về `board/queue/`, xóa claim. Tối đa 2 lần rework/task.
6. **task_blocked** (worker → manager): không làm được thì ghi rõ
   lý do vào report, chuyển task về queue, xóa claim — không im
   lặng ôm task.

## Transport

- **v1 (hiện tại):** file trong kho chung. Tốc độ trao đổi = tần
  suất mỗi bên check board (phút). Protocol làm trao đổi nhanh
  theo nghĩa không mơ hồ, không phải hỏi lại — không phải theo
  nghĩa mili-giây.
- **v2 (sau):** message queue/WebSocket qua Tailscale. Cùng message,
  cùng trường, chỉ đổi transport → tốc độ thành mili-giây. Việc
  setup queue + Tailscale làm cùng lúc thêm nhân viên, không đợi
  phase riêng.

## State machine

```
queue → doing (claimed) → done (submitted) → archive (approved)
                                    ↘ queue (rework / blocked)
```

Claim quá 24h không động tĩnh: quản lý thu hồi về queue.
