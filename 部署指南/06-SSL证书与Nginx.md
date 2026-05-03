# 第六册：SSL 证书与 Nginx

> **本册在哪操作**：**云服务器** SSH 命令行。
>
> **目标**：给你的域名申请免费的 HTTPS 证书，配置 Nginx 反向代理，让 `https://api.<你的域名>/` 能正常访问。

---

## 📌 本册要用到的域名

后面命令里 **`<你的域名>`** 和 **`<你的API域名>`** 每次都要替换成你真实的域名。为了节省视觉成本，**一次性定义**好：

| 占位符 | 在本文档中用什么替换 |
|---|---|
| `<你的域名>` | 你买的主域名，例如 `nailao.asia` |
| `<你的API域名>` | 通常是 `api.<你的域名>`，例如 `api.nailao.asia` |

**建议先导出为 shell 变量**，后面命令直接引用：

📍 **位置**：云服务器 · 当前目录 `/root`

```bash
export DOMAIN=<你的域名>
export API_DOMAIN=<你的API域名>

# 举例
# export DOMAIN=nailao.asia
# export API_DOMAIN=api.nailao.asia

# 验证
echo "主域名=$DOMAIN, API域名=$API_DOMAIN"
主域名=nailao.asia, API域名=api.nailao.asia
```

> ⚠️ **`export` 只在当前 SSH 会话有效**。如果中途断开 SSH 重连了，记得重新 export。

---

## 1. 申请 HTTPS 证书前的检查

证书颁发机构（Let's Encrypt）会通过 HTTP 请求访问你的域名来验证所有权，所以必须保证：

### 1.1 DNS 已解析到服务器

在 **本地电脑** 执行：

📍 **位置**：本地电脑

```
ping <你的域名>
ping <你的API域名>
```

两条都应该解析到**你服务器的公网 IP**。没解析到回第一册重新配 DNS，等 10 分钟再试。

### 1.2 服务器 80 端口对外开放

- 服务商控制台 → 安全组 → 入站规则：**确认 80 端口允许任何源（0.0.0.0/0）访问**
- 服务器上 Nginx 正在监听 80 端口：

📍 **位置**：云服务器 · 当前目录 `/root`

```
ss -ltn | grep :80
LISTEN 0  511  0.0.0.0:80  0.0.0.0:*
```

---

## 2. 申请证书

📍 **位置**：云服务器 · 当前目录 `/root`

```
certbot certonly --nginx -d $DOMAIN -d $API_DOMAIN
```

等价于（不 export 变量的写法）：

📍 **位置**：云服务器 · 当前目录 `/root`

```
certbot certonly --nginx -d <你的域名> -d <你的API域名>
# 举例：certbot certonly --nginx -d nailao.asia -d api.nailao.asia
```

参数含义：
- `certonly`：只申请证书，不自动改 Nginx 配置（我们后面自己配）
- `--nginx`：用 Nginx 插件做域名验证（临时借用 Nginx 响应验证请求）
- `-d 域名`：要申请证书的域名，可多个

### 2.1 交互过程

**第 1 问：输入邮箱**

```
Enter email address (used for urgent renewal and security notices)
```

输入**任意一个你常用的邮箱**（证书快过期时会发邮件提醒）。

**第 2 问：是否同意服务条款**

```
Please read the Terms of Service at ... (Y)es/(N)o:
```

输入 `Y` 回车。

**第 3 问：是否订阅 EFF 邮件**

```
Would you be willing to share your email... (Y)es/(N)o:
```

随意，输 `N` 回车（不订阅）。

**证书申请成功**

看到以下内容表示成功：

```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/<你的域名>/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/<你的域名>/privkey.pem
```

**注意证书目录是以"主域名"命名的**（例如 `/etc/letsencrypt/live/nailao.asia/`），不是 `api.nailao.asia`。

### 2.2 验证证书文件存在

📍 **位置**：云服务器 · 当前目录 `/root`

```
ls /etc/letsencrypt/live/$DOMAIN/
README  cert.pem  chain.pem  fullchain.pem  privkey.pem
```

看到 `fullchain.pem` 和 `privkey.pem` 就行了。

### 2.3 如果证书申请失败

常见错误与处理：

| 报错 | 原因 | 处理 |
|---|---|---|
| `DNS problem: NXDOMAIN` | DNS 未生效 | 回第一册确认 A 记录已添加，等 10 分钟 |
| `Connection refused` | 80 端口未开 | 检查安全组放行 80 |
| `unauthorized: Invalid response` | 解析到的不是本机 IP | 本地 ping 确认解析正确 |
| `too many requests` | Let's Encrypt 频率限制 | 等 1 小时再试 |

---

## 3. 配置 Nginx

### 3.1 为什么需要改默认的 nginx.conf？

项目自带的 `/opt/rejubang/deploy/nginx.conf` 里写死了 `nailao.asia`。如果你的域名不是这个，需要先替换。

### 3.2 切到 deploy 目录

📍 **位置**：云服务器 · 起始目录 `/root`（块内会切换到 `/opt/rejubang/deploy`，下方 `cd` 已写入代码，整段复制即可）

```
cd /opt/rejubang/deploy
ls
deploy.sh  nginx.conf  rejubang-api.service  rejubang-crawler.service
```

### 3.3 用 sed 替换 nginx.conf 里的域名

📍 **位置**：云服务器 · 当前目录 `/opt/rejubang/deploy`

```
sed -i "s|nailao\.asia|$DOMAIN|g" nginx.conf
sed -i "s|api\.$DOMAIN|$API_DOMAIN|g" nginx.conf
```

> 📌 **2026-04 版变更**：nginx.conf 里新增了 `/admin` 的反向代理（指向管理后台），无需额外配置，sed 替换域名后即生效。

第一条：把所有 `nailao.asia` 换成你的主域名（包括证书路径里的）
第二条：如果你的 API 子域名不是 `api.<主域名>`，把 `api.<你的主域名>` 再换成你实际的 API 域名

> 💡 如果你的 API 域名就是 `api.<你的主域名>`（推荐方案），第二条命令执行不执行结果都一样。

### 3.4 检查替换结果

📍 **位置**：云服务器 · 当前目录 `/opt/rejubang/deploy`

```
grep -E "server_name|ssl_certificate" nginx.conf
    server_name <你的域名> <你的API域名>;
    server_name <你的API域名>;
    ssl_certificate /etc/letsencrypt/live/<你的域名>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<你的域名>/privkey.pem;
    server_name <你的域名>;
    ssl_certificate /etc/letsencrypt/live/<你的域名>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<你的域名>/privkey.pem;
```

**确认 `server_name` 和 `ssl_certificate` 路径都是你真实的域名**，不能再出现 `nailao.asia`（除非你域名本来就是这个）。

### 3.5 把配置复制到 Nginx 目录

📍 **位置**：云服务器 · 当前目录 `/opt/rejubang/deploy`

```
cp nginx.conf /etc/nginx/sites-available/rejubang
ln -sf /etc/nginx/sites-available/rejubang /etc/nginx/sites-enabled/rejubang
rm -f /etc/nginx/sites-enabled/default
```

三条命令的作用：

| 命令 | 作用 |
|---|---|
| `cp nginx.conf /etc/nginx/sites-available/rejubang` | 把配置放到"可用站点"目录 |
| `ln -sf ... /etc/nginx/sites-enabled/rejubang` | 用软链接在"已启用站点"目录激活 |
| `rm -f /etc/nginx/sites-enabled/default` | 删除 Nginx 默认欢迎页，避免冲突 |

### 3.6 测试 Nginx 配置语法

📍 **位置**：云服务器 · 当前目录 `/opt/rejubang/deploy`

```
nginx -t
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

**看到 `test is successful` 才能继续**。如果报错，多半是证书路径不对，回到 3.4 确认。

### 3.7 重启 Nginx

📍 **位置**：云服务器 · 当前目录 `/opt/rejubang/deploy`

```
systemctl restart nginx
systemctl is-active nginx
active
```

---

## 4. 验证 HTTPS 可访问

### 4.1 在 **服务器** 上本地测

后端 Flask 还没启动，所以 `/api/` 路径会返回 502，但根路径应返回一段 JSON：

📍 **位置**：云服务器 · 当前目录 `/root`

```
curl -I https://$API_DOMAIN/
HTTP/2 200
server: nginx/...
```

**HTTP/2 200** 就说明 HTTPS 通了。

### 4.2 在 **本地电脑** 浏览器访问

浏览器打开 `https://<你的API域名>/`（例如 `https://api.nailao.asia/`），应该看到：

```json
{"service":"rejubang-api","status":"running"}
```

地址栏看到🔒小锁图标，说明 HTTPS 证书被浏览器信任。

### 4.3 `/api/` 路径返回 502 是正常的

📍 **位置**：云服务器 · 当前目录 `/root`

```
curl -I https://$API_DOMAIN/api/v1/heat/realtime/rank
HTTP/2 502
```

因为 Flask 还没启动，Nginx 转发请求时后端无响应。**下一册启动后端服务后会正常返回 200。**

---

## 5. 证书自动续期（Let's Encrypt 证书 90 天过期）

Certbot 会自动创建 systemd 定时器，每天检查一次证书，到期前 30 天内自动续期。

验证自动续期任务已启用：

📍 **位置**：云服务器 · 当前目录 `/root`

```
systemctl list-timers | grep certbot
Sun 2026-04-22 03:41:12 UTC ... certbot.timer  ...
```

有一行 `certbot.timer` 就说明自动续期已就位，无需额外操作。

### 5.1 手动测试续期（可选）

📍 **位置**：云服务器 · 当前目录 `/root`

```
certbot renew --dry-run
```

`--dry-run` 是模拟续期，不会真的更新证书。最后看到 `Congratulations, all simulated renewals succeeded` 就说明续期机制可以工作。

---

## 6. 本册完成检查清单

- [ ] `ls /etc/letsencrypt/live/<你的域名>/` 能看到 `fullchain.pem` 和 `privkey.pem`
- [ ] `nginx -t` 返回 `test is successful`
- [ ] `systemctl is-active nginx` 返回 `active`
- [ ] 本地浏览器访问 `https://<你的API域名>/` 看到 `{"service":"rejubang-api","status":"running"}`
- [ ] 地址栏有🔒小锁（证书受浏览器信任）

---

👉 进入 [07-启动服务与验证.md](./07-启动服务与验证.md)
