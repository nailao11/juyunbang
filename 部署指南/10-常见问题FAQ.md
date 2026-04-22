# 第十册：常见问题 FAQ

> 按问题的**现象**组织，遇到问题时从目录里找最接近的那一条。

---

## 目录

- [Q1. SSH 登录后执行命令报错 `command not found`](#q1)
- [Q2. `apt install` 提示 "Unable to locate package"](#q2)
- [Q3. pip 安装包很慢或卡住](#q3)
- [Q4. Playwright `install chromium` 失败](#q4)
- [Q5. Playwright 启动报 `BrowserType.launch: Executable doesn't exist`](#q5)
- [Q6. MariaDB 登录报 `Access denied for user 'root'`](#q6)
- [Q7. 项目启动时报 `Access denied for user 'rejubang'`](#q7)
- [Q8. `cat .env` 里密码有问题怎么改？](#q8)
- [Q9. Certbot 申请证书失败](#q9)
- [Q10. `nginx -t` 报 `cannot load certificate`](#q10)
- [Q11. 浏览器访问 HTTPS 显示"不安全"](#q11)
- [Q12. API 返回 502 Bad Gateway](#q12)
- [Q13. API 返回 500 Internal Server Error](#q13)
- [Q14. 小程序报 "request:fail url not in domain list"](#q14)
- [Q15. 爬虫服务跑了但数据库没数据](#q15)
- [Q16. 服务器内存不足进程被杀](#q16)
- [Q17. SSH 连接经常断开](#q17)
- [Q18. 磁盘被日志占满](#q18)
- [Q19. 如何修改域名（换域名）](#q19)
- [Q20. 如何关闭/卸载整个服务](#q20)
- [Q21. 访问 /admin 提示 "Token 错误" / 打不开](#q21)
- [Q22. 管理后台"测试热度提取"显示"未提取到数值"](#q22)
- [Q23. 录入一部剧后多久能采到数据？](#q23)
- [Q24. 一部剧完结了怎么下架？](#q24)
- [Q25. 数据库空间会无限增长吗？怎么控制？](#q25)

---

## <a id="q1"></a>Q1. SSH 登录后执行命令报错 `command not found`

**可能原因 1**：系统包没装。回 [02-系统环境安装.md](./02-系统环境安装.md) 第 2 步重装。

**可能原因 2**：执行 Python 相关命令没用虚拟环境的 `./venv/bin/` 前缀。

❌ 错误：

```
root@server:/opt/rejubang/backend# playwright install chromium
-bash: playwright: command not found
```

✅ 正确：

```
root@server:/opt/rejubang/backend# ./venv/bin/playwright install chromium
```

---

## <a id="q2"></a>Q2. `apt install` 提示 `Unable to locate package`

**原因**：`apt update` 没跑过（包索引为空）或系统不是 Debian 12。

```
root@server:~# apt update
root@server:~# apt install -y python3 python3-venv ...
```

如果是 Ubuntu，大部分包名一致，但 `python3-venv` 在部分 Ubuntu 版本叫 `python3.X-venv`，用：

```
root@server:~# apt install -y python3.11-venv
```

---

## <a id="q3"></a>Q3. pip 安装包很慢或卡住

换国内镜像重装：

```
root@server:~# cd /opt/rejubang/backend
root@server:/opt/rejubang/backend# ./venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

或写到全局配置永久生效：

```
root@server:~# mkdir -p ~/.pip
root@server:~# cat > ~/.pip/pip.conf <<'EOF'
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
EOF
```

之后 `./venv/bin/pip install ...` 会自动走清华源。

---

## <a id="q4"></a>Q4. Playwright `install chromium` 失败

### 4.1 报网络错误

Playwright 默认从 `playwright.azureedge.net` 下载 Chromium。国内服务器可能连不上，换镜像：

```
root@server:~# export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
root@server:~# cd /opt/rejubang/backend
root@server:/opt/rejubang/backend# ./venv/bin/playwright install chromium
```

### 4.2 报 `install-deps` 失败

手动装依赖：

```
root@server:~# apt install -y \
  libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 \
  libasound2 libpango-1.0-0 libcairo2 libxrandr2 libx11-xcb1 \
  libxcomposite1 libxdamage1 libxfixes3 libxss1 libatk1.0-0 \
  libcups2 libgtk-3-0
```

---

## <a id="q5"></a>Q5. Playwright 启动报 `BrowserType.launch: Executable doesn't exist`

Chromium 没下载成功。重装：

```
root@server:~# cd /opt/rejubang/backend
root@server:/opt/rejubang/backend# ./venv/bin/playwright install chromium --force
```

---

## <a id="q6"></a>Q6. MariaDB 登录报 `Access denied for user 'root'`

**情况 1**：忘了 root 密码。

如果还记得本文档预设的密码是 `RootDB_Pass_2026_NaiLao!`，就用它：

```
root@server:~# mysql -u root -p'RootDB_Pass_2026_NaiLao!'
```

**情况 2**：密码已忘，重设 root 密码：

```
# 停止 MariaDB
root@server:~# systemctl stop mariadb

# 以跳过权限检查的方式启动
root@server:~# mysqld_safe --skip-grant-tables &

# 登录（无密码）
root@server:~# mysql -u root

# 在 MariaDB 里执行
MariaDB [(none)]> FLUSH PRIVILEGES;
MariaDB [(none)]> ALTER USER 'root'@'localhost' IDENTIFIED BY 'RootDB_Pass_2026_NaiLao!';
MariaDB [(none)]> EXIT;

# 杀掉 safe 模式进程
root@server:~# pkill mysqld

# 正常重启
root@server:~# systemctl start mariadb
```

---

## <a id="q7"></a>Q7. 项目启动时报 `Access denied for user 'rejubang'`

`.env` 里 `DB_PASSWORD` 和第四册创建 `rejubang` 用户时用的密码不一致。

### 方案 A：修改 `.env` 对上数据库里的密码

```
root@server:~# nano /opt/rejubang/backend/.env
# 把 DB_PASSWORD 改为数据库里实际的密码
root@server:~# systemctl restart rejubang-api rejubang-crawler
```

### 方案 B：修改数据库密码对上 `.env`

```
root@server:~# mysql -u root -p'RootDB_Pass_2026_NaiLao!' -e "
ALTER USER 'rejubang'@'localhost' IDENTIFIED BY 'i7qxW0ZUGwWBMSUqm2TdJCB3DefTwosA';
FLUSH PRIVILEGES;
"
```

然后重启服务：

```
root@server:~# systemctl restart rejubang-api rejubang-crawler
```

---

## <a id="q8"></a>Q8. `cat .env` 里密码有问题怎么改？

直接用 nano 改：

```
root@server:~# nano /opt/rejubang/backend/.env
```

改完 `Ctrl + O` → 回车 → `Ctrl + X`。然后重启服务：

```
root@server:~# systemctl restart rejubang-api rejubang-crawler
```

---

## <a id="q9"></a>Q9. Certbot 申请证书失败

| 报错关键字 | 原因 | 处理 |
|---|---|---|
| `DNS problem: NXDOMAIN` | DNS 没生效 | 本地 `ping 域名` 确认解析；没生效等 10 分钟 |
| `Connection refused` | 80 端口未开放 | 服务器安全组放行 80；本机 `ss -ltn\|grep :80` 确认 Nginx 在监听 |
| `unauthorized: Invalid response` | 解析到的 IP 不是本机 | 本地 `nslookup 域名` 看到的 IP 必须和服务器公网 IP 一致 |
| `too many requests` | Let's Encrypt 频率限制 | 同域名一周最多失败 5 次，等 1 小时后再试；测试阶段加 `--staging` |

---

## <a id="q10"></a>Q10. `nginx -t` 报 `cannot load certificate`

证书路径不对。检查 `/etc/nginx/sites-available/rejubang` 里的 `ssl_certificate` 路径：

```
root@server:~# grep ssl_certificate /etc/nginx/sites-available/rejubang
```

路径必须和证书真实位置一致：

```
root@server:~# ls /etc/letsencrypt/live/
<你的主域名>
```

**证书目录名是主域名**（例如 `nailao.asia`），不是 `api.nailao.asia`。如果路径不一致，用 nano 改配置：

```
root@server:~# nano /etc/nginx/sites-available/rejubang
root@server:~# nginx -t && systemctl restart nginx
```

---

## <a id="q11"></a>Q11. 浏览器访问 HTTPS 显示"不安全"

### 情况 1：整条证书链没配全

检查 Nginx 用的是 `fullchain.pem`（包含中间证书）**不是** `cert.pem`：

```
root@server:~# grep ssl_certificate /etc/nginx/sites-available/rejubang
    ssl_certificate /etc/letsencrypt/live/<域名>/fullchain.pem;   ✅
    # ssl_certificate /etc/letsencrypt/live/<域名>/cert.pem;      ❌
```

### 情况 2：证书过期

```
root@server:~# certbot renew
root@server:~# systemctl restart nginx
```

---

## <a id="q12"></a>Q12. API 返回 502 Bad Gateway

**含义**：Nginx 能收到请求，但转发到 `127.0.0.1:5000` 时后端无响应。

```
# 1. API 服务是不是挂了
root@server:~# systemctl status rejubang-api --no-pager

# 2. 看 API 日志里最近的错误
root@server:~# journalctl -u rejubang-api -n 100 --no-pager | tail -50

# 3. 手动试试能不能直连后端
root@server:~# curl http://127.0.0.1:5000/health
```

- 如果 1 显示 `inactive` / `failed` → `systemctl restart rejubang-api`
- 如果 2 里有 `ModuleNotFoundError` → 依赖漏装，`./venv/bin/pip install -r requirements.txt`
- 如果 3 返回连接拒绝 → gunicorn 没起来，看日志修

---

## <a id="q13"></a>Q13. API 返回 500 Internal Server Error

后端代码抛异常了。看日志：

```
root@server:~# journalctl -u rejubang-api -n 200 --no-pager | grep -E "(ERROR|Traceback)" -A 10
```

常见：
- `Can't connect to MySQL server` → MariaDB 没启动，`systemctl start mariadb`
- `Redis connection error` → Redis 没启动，`systemctl start redis-server`
- `KeyError: 'xxx'` → `.env` 某个必需的 key 没写

---

## <a id="q14"></a>Q14. 小程序报 "request:fail url not in domain list"

**原因**：微信公众平台的合法域名没配好或没生效。

1. 回 [08-小程序配置与发布.md](./08-小程序配置与发布.md) 第 1.2 节，确认 request 合法域名是 `https://<你的API域名>`
2. 确认保存时已扫码确认
3. 修改域名后**需要重启微信开发者工具**重新编译
4. 开发阶段临时绕过：微信开发者工具 → 右上角"详情" → "本地设置" → 勾选"不校验合法域名..."（正式提审前不影响）

---

## <a id="q15"></a>Q15. 爬虫服务跑了但数据库没数据

### 检查步骤

**步骤 1**：看爬虫日志

```
root@server:~# tail -100 /opt/rejubang/logs/scheduler_$(date +%Y-%m-%d).log
```

关键词：
- `采集成功` / `保存成功` → 爬虫在工作
- `未发现任何剧` → 平台页面结构变了，爬虫需要维护
- `登录/验证码` → 被反爬拦截

**步骤 2**：确认 dramas 表有"近 30 天"的剧（爬虫只爬近期新剧）

```
root@server:~# mysql -u rejubang -p'i7qxW0ZUGwWBMSUqm2TdJCB3DefTwosA' rejubang -e "
SELECT title, air_date, status FROM dramas
WHERE air_date > DATE_SUB(NOW(), INTERVAL 30 DAY)
LIMIT 20;
"
```

如果一行都没有 → seed_data.sql 里的种子剧 air_date 是历史数据，已过 30 天阈值。

**步骤 3**：手动跑一次确认爬虫能工作

```
root@server:~# cd /opt/rejubang/backend
root@server:/opt/rejubang/backend# ./venv/bin/python test_crawl.py --platform tencent
```

看输出里有没有 `热度值: 12345` 这类数字。如果全是 0，说明爬虫逻辑需要更新。

---

## <a id="q16"></a>Q16. 服务器内存不足进程被杀

```
root@server:~# dmesg | grep -i "out of memory" | tail -5
```

看到 `Killed process XXX (mariadbd)` 这类输出就确认被 OOM 了。

### 处理

**短期**：重启所有服务

```
root@server:~# systemctl restart mariadb redis-server nginx rejubang-api rejubang-crawler
```

**长期**：

1. 确认 Swap 生效：`free -h`，Swap 行不应是 0
2. 改爬虫并发：编辑 `/opt/rejubang/backend/scheduler/task_scheduler.py`，降低 Playwright 并发数
3. 加内存：云服务器控制台升配到 8G

---

## <a id="q17"></a>Q17. SSH 连接经常断开

### 服务器端开启 KeepAlive

```
root@server:~# echo -e "ClientAliveInterval 60\nClientAliveCountMax 3" >> /etc/ssh/sshd_config
root@server:~# systemctl restart ssh
```

### 客户端开启 KeepAlive

Mac/Linux 本地 `~/.ssh/config`（没有就创建）：

```
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

---

## <a id="q18"></a>Q18. 磁盘被日志占满

```
root@server:~# df -h
root@server:~# du -sh /opt/rejubang/logs /var/log /opt/backup
```

按大到小清理：

```
# 项目日志（30 天前的）
root@server:~# find /opt/rejubang/logs/ -name "*.log" -mtime +30 -delete

# journalctl 日志（只留 7 天）
root@server:~# journalctl --vacuum-time=7d

# Nginx 轮转日志
root@server:~# find /var/log/nginx/ -name "*.gz" -mtime +14 -delete

# 数据库备份（只留 14 天，cron 已自动清理，手动也可跑）
root@server:~# find /opt/backup/ -name "rejubang_*.sql" -mtime +14 -delete

# apt 缓存
root@server:~# apt clean
```

---

## <a id="q19"></a>Q19. 如何修改域名（换域名）

1. **买新域名，配 A 记录**（回 [01-前置准备.md](./01-前置准备.md) 第 3 节）
2. **申请新域名的证书**：

   ```
   root@server:~# certbot certonly --nginx -d <新主域名> -d <新API域名>
   ```

3. **修改 Nginx 配置**：

   ```
   root@server:~# nano /etc/nginx/sites-available/rejubang
   # 替换 server_name 和 ssl_certificate 路径
   root@server:~# nginx -t && systemctl restart nginx
   ```

4. **修改小程序**：
   - 微信公众平台的合法域名改为新 API 域名
   - 本地 `miniapp/app.js` 的 `baseUrl` 改为新域名
   - 重新上传新版本小程序并提审

5. **旧域名的 certbot 证书可以删**：

   ```
   root@server:~# certbot delete --cert-name <旧主域名>
   ```

---

## <a id="q20"></a>Q20. 如何关闭/卸载整个服务

### 仅停止（保留数据）

```
root@server:~# systemctl stop rejubang-api rejubang-crawler
root@server:~# systemctl disable rejubang-api rejubang-crawler
```

### 彻底卸载（删代码、删服务单元）

```
root@server:~# systemctl stop rejubang-api rejubang-crawler
root@server:~# systemctl disable rejubang-api rejubang-crawler
root@server:~# rm /etc/systemd/system/rejubang-api.service
root@server:~# rm /etc/systemd/system/rejubang-crawler.service
root@server:~# systemctl daemon-reload

# 先备份再删
root@server:~# mysqldump -u rejubang -p'i7qxW0ZUGwWBMSUqm2TdJCB3DefTwosA' --single-transaction rejubang > /opt/backup/FINAL_BACKUP.sql

root@server:~# rm -rf /opt/rejubang
```

### 删数据库（**不可恢复**）

```
root@server:~# mysql -u root -p'RootDB_Pass_2026_NaiLao!' -e "DROP DATABASE rejubang; DROP USER 'rejubang'@'localhost';"
```

---

---

## <a id="q21"></a>Q21. 访问 /admin 提示 "Token 错误" / 打不开

### 情况 1：404 / 502

后端没起来或 Nginx 配置旧。

```
root@server:~# systemctl status rejubang-api
root@server:~# nginx -t && grep admin /etc/nginx/sites-available/rejubang
```

如果 Nginx 配置里没有 `location = /admin {` 这段，说明你用的是老版本 nginx.conf，重新复制：

```
root@server:~# cp /opt/rejubang/deploy/nginx.conf /etc/nginx/sites-available/rejubang
# 然后再按第六册 3.3 替换域名
root@server:~# nginx -t && systemctl restart nginx
```

### 情况 2："ADMIN_TOKEN 未配置，无法使用管理后台"

`.env` 里没有 `ADMIN_TOKEN` 字段。编辑加上：

```
root@server:~# nano /opt/rejubang/backend/.env
# 加一行：ADMIN_TOKEN=zCfQR0OkgWbZwaG4iw5Vb1E3ksvGAxTpR8nGk7gd--c
root@server:~# systemctl restart rejubang-api
```

### 情况 3：登录页输完点按钮报 "Token 错误"

粘贴的 token 里带了空格或换行。打开 `.env` 确认：

```
root@server:~# grep ADMIN_TOKEN /opt/rejubang/backend/.env
```

复制**等号右边完整字符串**粘贴到登录框。

---

## <a id="q22"></a>Q22. 管理后台"测试热度提取"显示"未提取到数值"

**原因排查**：

| 情况 | 处理 |
|---|---|
| URL 本身错的 | 浏览器直接打开这个 URL，如果进不去剧集详情页，说明 URL 有问题 |
| 剧刚开播，页面还没热度值 | 等几小时再试 |
| 平台页面改版了 | 需要更新 `backend/crawlers/airing_crawler.py` 里对应的 `_extract_xxx_heat()` 正则 |
| Playwright 被反爬阻断 | `tail -100 /opt/rejubang/logs/app_$(date +%Y-%m-%d).log` 看报错，可能是 Chromium 启动问题 |
| 芒果TV 的 URL 只有一段数字 | 芒果需要 `partId/clipId` 两段，缺一不可 |

快速验证 Playwright 能启动：
```
root@server:/opt/rejubang/backend# ./venv/bin/python test_crawl.py --env
```

---

## <a id="q23"></a>Q23. 录入一部剧后多久能采到数据？

- **默认**：下一个 15 分钟整点，爬虫自动跑时会带上新剧
- **立即**：SSH 上执行 `systemctl restart rejubang-crawler`（会触发首次启动立即采集）
- **或者**：`cd /opt/rejubang/backend && ./venv/bin/python test_crawl.py --run`

采集后查：

```
root@server:~# mysql -u rejubang -p'i7qxW0ZUGwWBMSUqm2TdJCB3DefTwosA' rejubang -e "
SELECT d.title, p.short_name, h.heat_value, h.record_time
FROM heat_realtime h
JOIN dramas d ON h.drama_id=d.id
JOIN platforms p ON h.platform_id=p.id
WHERE h.record_time > DATE_SUB(NOW(), INTERVAL 1 HOUR)
ORDER BY h.record_time DESC;
"
```

---

## <a id="q24"></a>Q24. 一部剧完结了怎么下架？

**方式 1：管理后台**（推荐）：登录 `/admin` → "当前在播剧清单"表格 → 点该剧右侧 **"下架"** 按钮。

下架后：
- 状态变为 `finished`
- 爬虫下一轮跳过这部剧（不再浪费 Playwright 资源）
- 已积累的历史数据**保留**（小程序继续能查）
- 若以后想重新上架，同一页点 **"上架"** 即可

**方式 2：直接改库**：

```
root@server:~# mysql -u rejubang -p'i7qxW0ZUGwWBMSUqm2TdJCB3DefTwosA' rejubang -e "
UPDATE dramas SET status='finished' WHERE title='蜜语纪';
"
```

---

## <a id="q25"></a>Q25. 数据库空间会无限增长吗？怎么控制？

**不会**。项目已内置自动归档策略（每日 04:00 运行）：

| 数据表 | 保留期 | 稳态空间 |
|---|---|---|
| `heat_realtime`（原始 15 分钟粒度） | 90 天 | ~100 MB（30 剧场景） |
| `playcount_snapshot` | 90 天 | ~10 MB |
| `heat_daily`（每天 1 条聚合） | 365 天 | ~1.5 MB |
| `dramas` / `drama_platforms` | 永久 | ~0.1 MB |

**手动查一下当前占用**：

```
root@server:~# mysql -u root -p'RootDB_Pass_2026_NaiLao!' -e "
SELECT table_name, ROUND(data_length/1024/1024,2) AS data_mb,
       ROUND(index_length/1024/1024,2) AS idx_mb, table_rows
FROM information_schema.tables
WHERE table_schema='rejubang'
ORDER BY data_length DESC;
"
```

**如果归档任务没跑**（表大小异常增长）：

```
# 手动触发一次
root@server:~# cd /opt/rejubang/backend
root@server:/opt/rejubang/backend# ./venv/bin/python -c "
from app import create_app
app = create_app()
with app.app_context():
    from scheduler.task_scheduler import job_archive_old_heat
    job_archive_old_heat()
"
```

---

## 还没解决？

1. 先把**完整的错误信息**（包括 Traceback）收集齐
2. 查看对应服务的最近日志（`journalctl -u <服务名> -n 200 --no-pager`）
3. 用错误关键词 Google / 向项目维护者反馈

返回 [README.md](./README.md) 目录
