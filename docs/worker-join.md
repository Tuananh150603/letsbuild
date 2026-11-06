# Vào team LetsBuild — lấy deploy key (5 phút)

Bạn là 1 Muse nhân viên của team LetsBuild: team 10 Muse làm video
cho kênh tài chính của Han, quản lý giao task qua repo git chung,
bạn làm task rồi nộp lại lên repo. File này là bước đầu tiên: lấy
quyền vào repo.

Repo: https://github.com/Tuananh150603/youtube-room (private)

## Bước 1 — Tạo deploy key (SSH) và gửi cho Han NGAY

Tên bạn là tên Han gọi bạn (vd `worker 2`). Dùng tên đó trong lệnh dưới.

Kiểm tra key cũ trước — có rồi thì dùng lại, KHÔNG tạo mới:

```bash
ls ~/.ssh/letsbuild_ed25519
```

Chưa có thì tạo mới (không passphrase):

```bash
ssh-keygen -t ed25519 -C "worker-2@letsbuild" -f ~/.ssh/letsbuild_ed25519 -N ""
```

Gửi cho Han NGAY toàn bộ 1 dòng public key:

```bash
cat ~/.ssh/letsbuild_ed25519.pub
```

Copy đúng cả dòng đó (bắt đầu bằng `ssh-ed25519`, kết thúc bằng tên
bạn), gửi trong chat với Han, kèm tên bạn.

**CHỈ gửi file `.pub`. KHÔNG BAO GIỜ gửi file không có `.pub`
(private key) cho bất kỳ ai.**

## Bước 2 — Chờ Han thêm key

Han thêm public key của bạn vào repo Settings → Deploy keys (bật
Allow write access). Chờ Han báo "xong" rồi mới sang bước 3.
(Chưa được thêm thì clone sẽ bị từ chối — đó là bình thường.)

## Bước 3 — Clone repo

Thêm SSH config để git dùng đúng key này (không đụng key GitHub
khác nếu bạn đã có):

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-letsbuild
  HostName github.com
  User git
  IdentityFile ~/.ssh/letsbuild_ed25519
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

Clone:

```bash
git clone git@github-letsbuild:Tuananh150603/youtube-room.git
```

Kiểm tra nhanh (phải thấy báo xác thực thành công):

```bash
ssh -T git@github-letsbuild
```

## Bước 4 — Setup máy (1 lệnh)

```bash
cd youtube-room && bash tools/setup-worker.sh
```

Chờ in `ALL OK`. Lỗi thì ghi nguyên log lại, báo Han, KHÔNG tự
sửa script.

## Bước 5 — Đọc onboarding + chờ task

Đọc `docs/worker-onboarding.md` trong repo, làm theo. Xong thì báo
Han: "setup xong, chờ task". Quản lý sẽ giao task qua board.
