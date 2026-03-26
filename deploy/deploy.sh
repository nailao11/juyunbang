#!/bin/bash
# 剧云榜 — 一键部署脚本
# 用法：在服务器上执行 bash deploy.sh

set -e

echo "============================="
echo "  剧云榜 一键部署脚本"
echo "============================="

PROJECT_DIR="/opt/juyunbang"
BACKEND_DIR="$PROJECT_DIR/code/backend"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# 1. 创建目录
echo "[1/9] 创建项目目录..."
mkdir -p $PROJECT_DIR/{code,logs,static}
mkdir -p /var/www/juyunbang

# 2. 复制代码
echo "[2/9] 部署后端代码..."
rsync -av --exclude='venv' --exclude='__pycache__' --exclude='.env' \
    "$REPO_DIR/backend/" "$BACKEND_DIR/"

# 3. Python虚拟环境
echo "[3/9] 配置Python虚拟环境..."
cd $BACKEND_DIR
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. 配置环境变量
echo "[4/9] 检查环境变量配置..."
if [ ! -f "$BACKEND_DIR/.env" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "已创建 $BACKEND_DIR/.env 文件"
    echo "⚠️  请编辑 $BACKEND_DIR/.env 填入实际配置值"
    echo "vim $BACKEND_DIR/.env"
    read -p "编辑完成后按回车继续..." _
fi

# 5. 初始化数据库表结构
echo "[5/9] 初始化数据库..."
read -p "是否需要初始化数据库表结构？(y/N): " init_db
if [ "$init_db" = "y" ] || [ "$init_db" = "Y" ]; then
    # 从.env读取数据库配置
    export $(grep -E '^(DB_USER|DB_PASSWORD|DB_NAME)=' "$BACKEND_DIR/.env" | xargs)
    echo "  -> 创建表结构..."
    mysql -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "$BACKEND_DIR/migrations/schema.sql"
    echo "  -> 表结构创建完成"

    read -p "是否需要导入初始数据（平台、示例剧集）？(y/N): " init_seed
    if [ "$init_seed" = "y" ] || [ "$init_seed" = "Y" ]; then
        echo "  -> 导入初始数据..."
        mysql -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "$BACKEND_DIR/migrations/seed_data.sql"
        echo "  -> 初始数据导入完成"
    fi
fi

# 6. 创建日志目录
echo "[6/9] 创建日志目录..."
mkdir -p /opt/juyunbang/logs

# 7. Nginx配置
echo "[7/9] 配置Nginx..."
cp "$REPO_DIR/deploy/nginx.conf" /etc/nginx/sites-available/juyunbang
ln -sf /etc/nginx/sites-available/juyunbang /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# 8. Systemd服务
echo "[8/9] 配置系统服务..."
cp "$REPO_DIR/deploy/juyunbang-api.service" /etc/systemd/system/
cp "$REPO_DIR/deploy/juyunbang-crawler.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable juyunbang-api
systemctl enable juyunbang-crawler
systemctl restart juyunbang-api
systemctl restart juyunbang-crawler

# 9. 验证
echo "[9/9] 验证部署..."
sleep 3
echo ""
if systemctl is-active --quiet juyunbang-api; then
    echo "[OK] API服务运行正常"
else
    echo "[FAIL] API服务启动失败"
    echo "  查看日志: journalctl -u juyunbang-api -n 50"
fi

if systemctl is-active --quiet juyunbang-crawler; then
    echo "[OK] 采集服务运行正常"
else
    echo "[FAIL] 采集服务启动失败"
    echo "  查看日志: journalctl -u juyunbang-crawler -n 50"
fi

# 测试API
echo ""
echo "测试API..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/health 2>/dev/null || echo "000")
if [ "$response" = "200" ]; then
    echo "[OK] API健康检查通过"
else
    echo "[WARN] API健康检查返回: $response"
fi

echo ""
echo "============================="
echo "  部署完成！"
echo ""
echo "  API地址: https://api.sqnl8.cn/api/v1/test"
echo "  健康检查: https://api.sqnl8.cn/health"
echo ""
echo "  常用命令："
echo "  查看API日志:   journalctl -u juyunbang-api -f"
echo "  查看采集日志:  journalctl -u juyunbang-crawler -f"
echo "  重启API:      systemctl restart juyunbang-api"
echo "  重启采集:     systemctl restart juyunbang-crawler"
echo "============================="
