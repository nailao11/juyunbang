#!/bin/bash
# 剧云榜 — 一键部署脚本
# 用法：在服务器上执行 bash deploy.sh

set -e

echo "============================="
echo "  剧云榜 一键部署脚本"
echo "============================="

PROJECT_DIR="/opt/juyunbang"
BACKEND_DIR="$PROJECT_DIR/backend"

# 1. 创建目录
echo "[1/8] 创建项目目录..."
mkdir -p $PROJECT_DIR/{backend,logs,static}
mkdir -p /var/www/juyunbang

# 2. 复制代码
echo "[2/8] 部署后端代码..."
cp -r backend/* $BACKEND_DIR/

# 3. Python虚拟环境
echo "[3/8] 配置Python虚拟环境..."
cd $BACKEND_DIR
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

# 4. 配置环境变量
echo "[4/8] 检查环境变量配置..."
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "请先创建 $BACKEND_DIR/.env 文件！参考 .env.example"
    echo "cp $BACKEND_DIR/.env.example $BACKEND_DIR/.env"
    echo "然后编辑 .env 填入实际配置值"
    exit 1
fi

# 5. 初始化数据库
echo "[5/8] 初始化数据库..."
read -p "是否需要初始化数据库？(y/N): " init_db
if [ "$init_db" = "y" ] || [ "$init_db" = "Y" ]; then
    source $BACKEND_DIR/.env
    mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < $BACKEND_DIR/migrations/schema.sql
    echo "数据库初始化完成"
fi

# 6. Nginx配置
echo "[6/8] 配置Nginx..."
cp deploy/nginx.conf /etc/nginx/sites-available/juyunbang
ln -sf /etc/nginx/sites-available/juyunbang /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# 7. Systemd服务
echo "[7/8] 配置系统服务..."
cp deploy/juyunbang-api.service /etc/systemd/system/
cp deploy/juyunbang-crawler.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable juyunbang-api
systemctl enable juyunbang-crawler
systemctl restart juyunbang-api
systemctl restart juyunbang-crawler

# 8. 验证
echo "[8/8] 验证部署..."
sleep 3
if systemctl is-active --quiet juyunbang-api; then
    echo "✅ API服务运行正常"
else
    echo "❌ API服务启动失败，请检查日志：journalctl -u juyunbang-api -n 50"
fi

if systemctl is-active --quiet juyunbang-crawler; then
    echo "✅ 采集服务运行正常"
else
    echo "❌ 采集服务启动失败，请检查日志：journalctl -u juyunbang-crawler -n 50"
fi

echo ""
echo "============================="
echo "  部署完成！"
echo "  API地址: https://api.sqnl8.cn/api/v1/test"
echo "  查看日志: journalctl -u juyunbang-api -f"
echo "============================="
