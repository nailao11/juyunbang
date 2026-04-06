# 剧云榜部署指南（Playwright采集版）

> **采集架构说明**：
> 由于4个视频平台（爱奇艺/腾讯/优酷/芒果TV）的热度值都是通过JavaScript动态渲染，
> 纯HTTP爬虫无法获取。本方案使用 **Playwright 无头浏览器** 真实渲染页面后提取热度值。
>
> **采集策略**：
> - 只采集 **近30天内上线的新剧**
> - 每15分钟一次增量采集，同剧同平台10分钟内不重复
> - 每部剧通过平台详情页抓取真实站内热度值

---

## 1. 环境要求

| 项目 | 要求 |
|---|---|
| 系统 | Debian 11+ / Ubuntu 20.04+ |
| Python | 3.9+ |
| 内存 | ≥ 2GB（Playwright 运行 chromium 需要） |
| MySQL/MariaDB | 10.3+ |
| Redis | 6.0+ |

---

## 2. 安装步骤（在服务器上执行）

### 第1步：拉取最新代码

```bash
cd /opt/juyunbang
git fetch origin
git checkout claude/review-project-codebase-XCo0t
git pull origin claude/review-project-codebase-XCo0t
```

### 第2步：创建 Python 虚拟环境

```bash
cd /opt/juyunbang/backend
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

### 第3步：安装 Playwright 浏览器

```bash
# 安装 chromium
./venv/bin/playwright install chromium

# 安装 Debian/Ubuntu 系统依赖（chromium 运行必须）
./venv/bin/playwright install-deps chromium

# 或手动安装依赖（如果上面失败）：
apt install -y libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 \
    libasound2 libpango-1.0-0 libcairo2 libxrandr2 libx11-xcb1 libxcomposite1 \
    libxdamage1 libxfixes3 libxss1 libatk1.0-0 libcups2 libgtk-3-0
```

### 第4步：验证安装

```bash
cd /opt/juyunbang/backend
./venv/bin/python test_crawl.py
```

看到以下输出说明安装成功：
```
[1/3] 检查Playwright...
  ✓ playwright模块已安装
  ✓ chromium浏览器可启动
```

### 第5步：配置后端服务

```bash
# 确保日志目录存在
mkdir -p /opt/juyunbang/logs

# 修正或创建 systemd 服务配置
cat > /etc/systemd/system/juyunbang.service << 'EOF'
[Unit]
Description=JuYunBang Backend API
After=network.target mariadb.service redis-server.service

[Service]
Type=notify
User=root
Group=root
WorkingDirectory=/opt/juyunbang/backend
Environment="PATH=/opt/juyunbang/backend/venv/bin:/usr/bin"
ExecStart=/opt/juyunbang/backend/venv/bin/gunicorn -c gunicorn_config.py run:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 第6步：配置采集服务

```bash
cat > /etc/systemd/system/juyunbang-crawler.service << 'EOF'
[Unit]
Description=JuYunBang Crawler Service (Playwright)
After=network.target mariadb.service redis-server.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/juyunbang/backend
Environment="PATH=/opt/juyunbang/backend/venv/bin:/usr/bin"
Environment=PYTHONPATH=/opt/juyunbang/backend
ExecStart=/opt/juyunbang/backend/venv/bin/python scheduler/task_scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启动两个服务
systemctl daemon-reload
systemctl enable juyunbang juyunbang-crawler
systemctl restart juyunbang
systemctl restart juyunbang-crawler
```

### 第7步：验证服务状态

```bash
systemctl status juyunbang
systemctl status juyunbang-crawler

# 查看采集日志
tail -f /opt/juyunbang/logs/scheduler_$(date +%Y-%m-%d).log
```

---

## 3. 测试命令

```bash
cd /opt/juyunbang/backend

# 测试Playwright + 各平台连通性（不写库）
./venv/bin/python test_crawl.py

# 只测试某个平台的热度提取
./venv/bin/python test_crawl.py --platform tencent
./venv/bin/python test_crawl.py --platform iqiyi
./venv/bin/python test_crawl.py --platform youku
./venv/bin/python test_crawl.py --platform mgtv

# 完整采集并写入数据库
./venv/bin/python test_crawl.py --save
```

---

## 4. 数据采集原理

### 各平台热度获取方式

| 平台 | 访问端 | URL 模式 | 提取字段 |
|---|---|---|---|
| 腾讯视频 | 移动端 | `m.v.qq.com/x/cover/{cid}.html` | "XXXXX热度" |
| 爱奇艺 | PC端 | 由PCW API返回的页面URL | 热度图标+数字（自动关闭广告弹窗） |
| 优酷 | PC端 | `v.youku.com/v_show/id_XXX.html` | "XXXX热度" |
| 芒果TV | 移动端 | `m.mgtv.com/b/{part_id}/{vid}.html` | "X.X亿次播放"（替代热度） |

### 采集流程

```
每15分钟执行一次:
  1. 发现阶段：从各平台的轻量列表API获取在播剧（title, url, 首播日期）
  2. 过滤：只保留近30天内上线的新剧
  3. 提取热度：启动无头浏览器 → 依次访问每部剧的详情页 → 等JS渲染 → 正则提取热度值
  4. 去重：同剧同平台10分钟内已采集则跳过
  5. 保存：写入 heat_realtime 表
  6. 记录平台URL到 drama_platforms 表（供下次复用）
```

### 去重机制

- **剧集去重**：通过标题归一化匹配，同名剧只在 `dramas` 表中存一条
- **采集去重**：同一剧集同一平台10分钟内不重复采集（`_has_recent_heat` 方法）
- **URL缓存**：平台URL存入 `drama_platforms` 表，下次可直接复用

---

## 5. 常见问题

### Q1: Playwright 安装报错
```bash
# 清理并重装
./venv/bin/pip uninstall -y playwright
./venv/bin/pip install playwright==1.40.0
./venv/bin/playwright install chromium --force
```

### Q2: chromium 启动失败（缺少系统依赖）
```bash
./venv/bin/playwright install-deps chromium
```
如果仍报错，按错误信息用 `apt install` 安装缺失的库。

### Q3: 采集结果为空
- 查看日志：`journalctl -u juyunbang-crawler -f`
- 单独测试：`./venv/bin/python test_crawl.py --platform tencent`
- 检查 dramas 表中是否有近30天的 air_date 数据

### Q4: 采集速度慢
单次完整采集（4平台 × 约20部新剧 = 80个页面）约 2-4 分钟，属正常范围。
如需加速，调整 `airing_crawler.py` 中的 `MAX_DRAMAS_PER_PLATFORM` 参数。

### Q5: 芒果TV没有热度值
芒果TV平台本身不显示热度值，仅显示播放量。本项目将芒果TV的播放量写入 `heat_realtime`
作为"热度"替代，供前端统一展示。后续可由 `processors` 计算日增长量。

### Q6: 爱奇艺热度被广告遮挡
代码已包含广告关闭逻辑（见 `airing_crawler.py` 的 `close_selectors`）。
如仍无法提取，可能是新弹窗样式，需要更新选择器。

---

## 6. 数据验证

```bash
# 连接数据库查看最新采集结果
mysql -u root -p juyunbang -e "
SELECT d.title, p.name as platform, h.heat_value, h.record_time
FROM heat_realtime h
JOIN dramas d ON h.drama_id = d.id
JOIN platforms p ON h.platform_id = p.id
ORDER BY h.record_time DESC LIMIT 20;
"
```

---

## 7. 代码结构

```
backend/crawlers/
├── base_crawler.py        # 基类（含 _match_drama, _has_recent_heat, _is_new_drama）
├── browser_helper.py      # Playwright 浏览器封装
├── airing_crawler.py      # 新剧采集主爬虫（4平台统一）
├── iqiyi_crawler.py       # 旧版爱奇艺爬虫（兼容保留）
├── tencent_crawler.py     # 旧版腾讯爬虫（兼容保留）
├── youku_crawler.py       # 旧版优酷爬虫（兼容保留）
├── mgtv_crawler.py        # 旧版芒果TV爬虫（兼容保留）
├── dailyhot_crawler.py    # 废弃（DailyHot不支持视频平台）
└── douban_crawler.py      # 豆瓣评分爬虫（独立任务）
```
