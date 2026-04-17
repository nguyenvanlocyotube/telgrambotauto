# 🤖 Shop Mã Xã Hội — Telegram Bot + Admin Panel

Bot bán mã tài khoản xã hội tự động, có admin panel web để quản lý toàn bộ.

---

## 📁 Cấu trúc dự án

```
telegram-bot/
├── bot.py              ← Bot Telegram chính
├── admin_app.py        ← Web Admin Panel (Flask)
├── models.py           ← Database models (SQLAlchemy)
├── config.py           ← Cấu hình từ .env
├── requirements.txt    ← Thư viện Python
├── .env.example        ← Mẫu file cấu hình
├── deploy.sh           ← Script deploy tự động
├── docker-compose.yml  ← Deploy bằng Docker
├── templates/          ← Giao diện Admin Panel
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── orders.html
│   ├── order_detail.html
│   ├── products.html
│   ├── codes.html
│   ├── deposits.html
│   ├── users.html
│   ├── user_detail.html
│   ├── categories.html
│   └── settings.html
└── data/               ← Database SQLite (tự tạo)
```

---

## ✨ Tính năng đầy đủ

### Bot Telegram
- ✅ Menu chính với keyboard nút bấm
- ✅ Duyệt danh mục & sản phẩm
- ✅ Giỏ hàng (thêm/xóa/checkout)
- ✅ Mua ngay (1 click)
- ✅ Giao mã tự động sau khi mua
- ✅ Nạp tiền qua chuyển khoản ngân hàng
- ✅ Lịch sử đơn hàng & xem lại mã
- ✅ Lịch sử giao dịch
- ✅ Trang cá nhân + số dư
- ✅ Hệ thống referral (giới thiệu bạn bè)
- ✅ Gửi tin nhắn hỗ trợ tới admin
- ✅ Chế độ bảo trì
- ✅ Admin commands: /stats, /broadcast, /addbalance

### Admin Web Panel
- ✅ Dashboard thống kê + biểu đồ doanh thu 7 ngày
- ✅ Quản lý đơn hàng (lọc, tìm kiếm, xem chi tiết)
- ✅ Quản lý sản phẩm (thêm/ẩn/hiện)
- ✅ Nhập mã hàng loạt (bulk import)
- ✅ Quản lý danh mục
- ✅ Duyệt/từ chối yêu cầu nạp tiền
- ✅ Quản lý khách hàng (cộng/trừ tiền, cấm/bỏ cấm)
- ✅ Cài đặt bot (tin nhắn welcome, bảo trì, bonus...)
- ✅ Auto-refresh thông báo nạp tiền chờ duyệt

---

## 🚀 HƯỚNG DẪN DEPLOY

### Bước 1 — Chuẩn bị VPS

Yêu cầu tối thiểu:
- **OS**: Ubuntu 20.04 / 22.04
- **RAM**: 512MB (1GB khuyến nghị)
- **CPU**: 1 vCPU
- **Giá tham khảo**: DigitalOcean $6/tháng, Vultr $5/tháng, Contabo $5/tháng

Các nhà cung cấp VPS rẻ tốt tại Việt Nam:
- **DigitalOcean**: https://digitalocean.com (có free credit)
- **Vultr**: https://vultr.com
- **BizFly Cloud**: https://bizflycloud.vn (VPS Việt Nam)
- **Viettel IDC**: https://viettelidc.com.vn

---

### Bước 2 — Tạo Bot Telegram

1. Mở Telegram, tìm **@BotFather**
2. Gõ `/newbot`
3. Đặt tên bot (VD: `Shop Mã Xã Hội`)
4. Đặt username (VD: `shopmasxahoi_bot`)
5. Copy **token** nhận được (dạng `1234567890:ABCdef...`)

Lấy Telegram ID của bạn (để làm admin):
- Mở **@userinfobot** hoặc **@getmyid_bot**
- Copy ID số (VD: `123456789`)

---

### Bước 3 — Upload code lên VPS

**Cách A — Upload trực tiếp (FileZilla/WinSCP)**:
```
Host: IP_VPS
Username: ubuntu
Port: 22
```
Upload thư mục `telegram-bot/` vào `/home/ubuntu/`

**Cách B — Git clone** (nếu đã đẩy lên GitHub):
```bash
ssh ubuntu@YOUR_VPS_IP
git clone https://github.com/yourname/telegram-bot.git /home/ubuntu/telegram-bot
```

---

### Bước 4 — Cấu hình .env

```bash
ssh ubuntu@YOUR_VPS_IP
cd /home/ubuntu/telegram-bot
cp .env.example .env
nano .env
```

Chỉnh sửa các thông tin sau:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwx    # Token từ BotFather
ADMIN_IDS=123456789                                  # Telegram ID của bạn
ADMIN_PASSWORD=MatKhauManhCuaBan123!                # Đổi mật khẩu admin
ADMIN_SECRET_KEY=random_string_dai_kho_doan_xyz      # Chuỗi bí mật ngẫu nhiên
BANK_NAME=MB Bank
BANK_ACCOUNT=0123456789
BANK_OWNER=NGUYEN VAN A
SUPPORT_USERNAME=@your_username
```

Lưu file: `Ctrl+X` → `Y` → `Enter`

---

### Bước 5 — Chạy deploy script

```bash
cd /home/ubuntu/telegram-bot
chmod +x deploy.sh
sudo ./deploy.sh
```

Script tự động:
- Cài Python, Nginx
- Tạo virtual environment
- Cài thư viện
- Cấu hình systemd services
- Cấu hình Nginx

---

### Bước 6 — Start services

```bash
# Start bot
sudo systemctl start shop-bot

# Start admin panel
sudo systemctl start shop-admin

# Kiểm tra trạng thái
sudo systemctl status shop-bot
sudo systemctl status shop-admin
```

---

### Bước 7 — Truy cập Admin Panel

Mở trình duyệt: `http://YOUR_VPS_IP/admin`

Đăng nhập với:
- Username: `admin` (hoặc ADMIN_USERNAME trong .env)
- Password: Mật khẩu đã đặt trong .env

---

## 🐳 Deploy bằng Docker (Cách đơn giản hơn)

```bash
# Cài Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu

# Copy .env
cp .env.example .env
nano .env  # Điền thông tin

# Chạy
docker-compose up -d

# Xem log
docker-compose logs -f bot
docker-compose logs -f admin
```

---

## 📋 Các lệnh quản lý thường dùng

```bash
# Xem log bot realtime
journalctl -u shop-bot -f

# Xem log admin
journalctl -u shop-admin -f

# Restart bot (sau khi sửa code)
sudo systemctl restart shop-bot

# Restart admin
sudo systemctl restart shop-admin

# Stop/Start
sudo systemctl stop shop-bot
sudo systemctl start shop-bot

# Xem database SQLite
sqlite3 /home/ubuntu/telegram-bot/data/bot_data.db
.tables
SELECT * FROM users LIMIT 10;
.quit
```

---

## 🔒 Cài SSL (HTTPS) miễn phí

```bash
# Cài certbot
sudo apt install certbot python3-certbot-nginx -y

# Lấy SSL (cần có domain trỏ về IP VPS)
sudo certbot --nginx -d yourdomain.com

# SSL tự động renew
sudo systemctl enable certbot.timer
```

---

## 📦 Nhập mã hàng vào bot

1. Đăng nhập Admin Panel
2. Vào **Sản phẩm** → chọn sản phẩm → **Mã**
3. Dán mã vào ô nhập liệu (mỗi dòng 1 mã)
4. Click **Nhập mã**

**Format mã hỗ trợ** (mỗi dòng 1 mã):
```
email@gmail.com|Password123
0912345678|pass456
username:password:email@mail.com
```

---

## ⚡ Lệnh Admin trong Bot

Gõ trong Telegram với tài khoản admin:

```
/stats                          → Xem thống kê
/broadcast Tin nhắn ở đây      → Gửi thông báo tới tất cả users
/addbalance 123456789 50000     → Cộng 50.000đ cho user ID
```

---

## 🛠 Cập nhật code

```bash
cd /home/ubuntu/telegram-bot

# Nếu dùng git
git pull

# Nếu upload tay thì upload file mới, sau đó:
sudo systemctl restart shop-bot
sudo systemctl restart shop-admin
```

---

## ❓ Xử lý lỗi thường gặp

**Bot không chạy:**
```bash
journalctl -u shop-bot -n 50
# Thường do: sai BOT_TOKEN, hoặc thiếu thư viện
```

**Admin panel lỗi 502:**
```bash
sudo systemctl status shop-admin
# Thường do: admin chưa start hoặc bị crash
```

**Không kết nối được database:**
```bash
ls -la /home/ubuntu/telegram-bot/data/
# Tạo thư mục nếu chưa có:
mkdir -p /home/ubuntu/telegram-bot/data
```

---

## 💡 Tips

- **Backup database**: `cp data/bot_data.db data/bot_data_backup_$(date +%Y%m%d).db`
- **Đổi mật khẩu admin**: Sửa trong `.env` rồi `systemctl restart shop-admin`
- **Thêm admin bot**: Thêm Telegram ID vào `ADMIN_IDS` (phân cách bằng dấu phẩy)
- **PostgreSQL**: Đổi `DATABASE_URL` để dùng PostgreSQL cho production lớn
