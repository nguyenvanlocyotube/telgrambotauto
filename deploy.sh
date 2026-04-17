#!/bin/bash
# ============================================================
# DEPLOY SCRIPT - Shop Mã Xã Hội Bot
# Chạy trên Ubuntu 20.04 / 22.04
# Sử dụng: chmod +x deploy.sh && sudo ./deploy.sh
# ============================================================

set -e
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  DEPLOY SHOP MÃ XÃ HỘI BOT${NC}"
echo -e "${GREEN}========================================${NC}"

# ── 1. Cập nhật hệ thống ─────────────────────────────────────
echo -e "\n${YELLOW}[1/7] Cập nhật hệ thống...${NC}"
apt-get update -q
apt-get install -y python3 python3-pip python3-venv nginx git curl

# ── 2. Tạo thư mục project ────────────────────────────────────
echo -e "\n${YELLOW}[2/7] Tạo thư mục project...${NC}"
PROJECT_DIR="/home/ubuntu/telegram-bot"
mkdir -p $PROJECT_DIR/data
mkdir -p $PROJECT_DIR/templates

# Copy files vào đây (nếu deploy từ git thì dùng git clone)
# cd $PROJECT_DIR && git clone YOUR_REPO_URL .

# ── 3. Tạo virtual environment ────────────────────────────────
echo -e "\n${YELLOW}[3/7] Cài Python packages...${NC}"
cd $PROJECT_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Python packages đã cài xong${NC}"

# ── 4. Cấu hình .env ─────────────────────────────────────────
echo -e "\n${YELLOW}[4/7] Kiểm tra file .env...${NC}"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp $PROJECT_DIR/.env.example $PROJECT_DIR/.env
    echo -e "${RED}⚠️  File .env chưa được cấu hình!${NC}"
    echo -e "${RED}   Mở file $PROJECT_DIR/.env và điền thông tin của bạn${NC}"
    echo -e "${RED}   Sau đó chạy lại script này hoặc start service thủ công${NC}"
else
    echo -e "${GREEN}✓ File .env đã tồn tại${NC}"
fi

# ── 5. Cài systemd services ───────────────────────────────────
echo -e "\n${YELLOW}[5/7] Cài đặt systemd services...${NC}"

cat > /etc/systemd/system/shop-bot.service << EOF
[Unit]
Description=Shop Ma Xa Hoi - Telegram Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
EnvironmentFile=$PROJECT_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/shop-admin.service << EOF
[Unit]
Description=Shop Ma Xa Hoi - Admin Web Panel
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 admin_app:app
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
EnvironmentFile=$PROJECT_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable shop-bot shop-admin
echo -e "${GREEN}✓ Services đã được cài đặt${NC}"

# ── 6. Cấu hình Nginx ─────────────────────────────────────────
echo -e "\n${YELLOW}[6/7] Cấu hình Nginx...${NC}"
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")

cat > /etc/nginx/sites-available/shop-admin << EOF
server {
    listen 80;
    server_name $SERVER_IP;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 120;
        client_max_body_size 16M;
    }
}
EOF

ln -sf /etc/nginx/sites-available/shop-admin /etc/nginx/sites-enabled/shop-admin
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
echo -e "${GREEN}✓ Nginx đã được cấu hình${NC}"

# ── 7. Mở firewall ────────────────────────────────────────────
echo -e "\n${YELLOW}[7/7] Cấu hình firewall...${NC}"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
echo -e "${GREEN}✓ Firewall đã mở port 22, 80, 443${NC}"

# ── Hoàn thành ────────────────────────────────────────────────
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  DEPLOY HOÀN TẤT!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e ""
echo -e "📝 ${YELLOW}Các bước tiếp theo:${NC}"
echo -e "   1. Chỉnh sửa file .env: ${GREEN}nano $PROJECT_DIR/.env${NC}"
echo -e "   2. Start bot: ${GREEN}systemctl start shop-bot${NC}"
echo -e "   3. Start admin: ${GREEN}systemctl start shop-admin${NC}"
echo -e ""
echo -e "🌐 Admin Panel: ${GREEN}http://$SERVER_IP/admin${NC}"
echo -e ""
echo -e "📊 Xem log bot: ${GREEN}journalctl -u shop-bot -f${NC}"
echo -e "📊 Xem log admin: ${GREEN}journalctl -u shop-admin -f${NC}"
