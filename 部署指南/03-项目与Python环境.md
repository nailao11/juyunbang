# 第三册：项目与 Python 环境

> **本册在哪操作**：**云服务器** SSH 命令行。
>
> **目标**：把项目代码拉到 `/opt/rejubang`，在 `backend/` 下建 Python 虚拟环境，装好所有依赖和 Playwright 浏览器。

---

## 1. 拉取项目代码

### 1.1 切到 `/opt` 目录

`/opt` 是 Linux 惯例上用于放"第三方应用"的目录，权限干净、不会和系统包冲突。

```
root@server:~# cd /opt
root@server:/opt# pwd
/opt
```

### 1.2 克隆项目

```
root@server:/opt# git clone https://github.com/nailao11/juyunbang.git /opt/rejubang
```

这会把项目下载到 `/opt/rejubang`。下载完成后：

```
root@server:/opt# cd /opt/rejubang
root@server:/opt/rejubang# ls
backend  deploy  miniapp  README.md  部署指南  部署指南.md  追剧助手微信小程序_完整开发方案.md
```

看到 `backend` / `deploy` / `miniapp` 三个核心目录就算成功。

### 1.3 如果之前已经克隆过

重新部署时只需要更新到最新代码：

```
root@server:~# cd /opt/rejubang
root@server:/opt/rejubang# git pull origin main
```

### 1.4 如果 `git clone` 提示 "Connection refused" 或 "超时"

服务器访问 GitHub 慢/不通时，可以改用 HTTPS 加速镜像：

```
root@server:/opt# git clone https://ghfast.top/https://github.com/nailao11/juyunbang.git /opt/rejubang
```

或用 `wget` 下载 zip 包再解压（略）。

---

## 2. 创建 Python 虚拟环境

### 2.1 切到后端目录

**从这里开始，几乎所有命令都在 `/opt/rejubang/backend` 下执行**，先切过去：

```
root@server:~# cd /opt/rejubang/backend
root@server:/opt/rejubang/backend# pwd
/opt/rejubang/backend
```

### 2.2 创建虚拟环境

虚拟环境的作用是把项目的 Python 依赖和系统 Python 隔离开，避免污染。

```
root@server:/opt/rejubang/backend# python3 -m venv venv
```

执行完会在当前目录下生成一个 `venv/` 文件夹（里面是一套独立的 Python）。

> ℹ️ **关于 PEP 668**：Debian 12 和 13 都默认开启 PEP 668（`externally-managed-environment`），**直接用系统 pip 装包会被拒绝**。这正是我们用 venv 的原因——venv 里的 pip 不受这个限制。本指南从不要求你往系统 Python 装包，只用 `./venv/bin/pip`。

```
root@server:/opt/rejubang/backend# ls
app  crawlers  gunicorn_config.py  migrations  processors  requirements.txt  run.py  scheduler  test_crawl.py  venv
```

### 2.3 关于"激活虚拟环境"

本文档 **不要求你激活虚拟环境**，而是直接用 `./venv/bin/` 前缀调用虚拟环境里的工具（更不容易出错）。

对比：

| 写法 | 是否需要先激活 | 推荐度 |
|---|---|---|
| `pip install xxx` | 需要先 `source venv/bin/activate` | ❌ 容易忘激活，装到系统 Python 去了 |
| `./venv/bin/pip install xxx` | **不需要激活** | ✅ 本文档全程用这种 |

---

## 3. 安装 Python 依赖

### 3.1 升级 pip（推荐，避免装依赖时老版本 pip 报奇怪错）

```
root@server:/opt/rejubang/backend# ./venv/bin/pip install --upgrade pip
```

### 3.2 装项目依赖

```
root@server:/opt/rejubang/backend# ./venv/bin/pip install -r requirements.txt
```

过程 2~5 分钟。依赖包括 Flask、Playwright、PyMySQL、Redis、APScheduler、七牛云 SDK 等。

### 3.3 如果下载很慢（国内服务器常见）

换清华大学镜像源重新装：

```
root@server:/opt/rejubang/backend# ./venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3.4 验证依赖装好

```
root@server:/opt/rejubang/backend# ./venv/bin/pip list | grep -E "Flask|playwright|PyMySQL|redis|APScheduler|lxml|cryptography"
```

应该看到：

```
APScheduler       3.10.4
cryptography      44.0.0
Flask             3.0.0
lxml              5.3.0
playwright        1.55.0
PyMySQL           1.1.0
redis             5.0.1
```

> ℹ️ **2026-04 版本升级说明**：相比早期版本，`playwright / lxml / cryptography` 三个包已经升级以适配 Python 3.13 + Debian 13。如果你 pip list 看到的是 1.40 / 4.9.3 / 41.0.7，说明你 `git pull` 没拉到最新代码，先执行 `git pull origin main` 再重装依赖。

---

## 4. 安装 Playwright 浏览器

Playwright 是 Python 包，但它还需要下载一份 Chromium 浏览器才能跑爬虫。

### 4.1 下载 Chromium

```
root@server:/opt/rejubang/backend# ./venv/bin/playwright install chromium
```

会下载约 150 MB，过程 1~3 分钟。浏览器装到 `~/.cache/ms-playwright/`（root 用户的缓存目录）。

### 4.2 装 Chromium 所需的系统库

Chromium 运行时依赖一堆 Linux 共享库（libnss3 等）。执行：

```
root@server:/opt/rejubang/backend# ./venv/bin/playwright install-deps chromium
```

### 4.3 如果 `install-deps` 报错

**先确认系统版本**，然后用对应的命令：

```
root@server:/opt/rejubang/backend# cat /etc/os-release | grep -E "VERSION_ID|VERSION_CODENAME"
```

#### 如果是 Debian 13 (Trixie) / Ubuntu 24.04+（包名带 `t64` 后缀）

```
root@server:/opt/rejubang/backend# apt install -y \
  libnss3 libnspr4 libdbus-1-3 \
  libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 \
  libasound2t64 libcups2t64 libglib2.0-0t64 \
  libdrm2 libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 \
  libxrandr2 libxcomposite1 libxdamage1 libxfixes3 \
  libx11-6 libxcb1 libxext6
```

#### 如果是 Debian 12 (Bookworm) / Ubuntu 22.04（老包名）

```
root@server:/opt/rejubang/backend# apt install -y \
  libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 \
  libasound2 libpango-1.0-0 libcairo2 libxrandr2 libx11-xcb1 \
  libxcomposite1 libxdamage1 libxfixes3 libxss1 libatk1.0-0 \
  libcups2 libgtk-3-0
```

> ℹ️ **为什么 Debian 13 改名了？** Debian 13 完成了 "64-bit time_t 迁移"（为 2038 年问题做准备），使用了 64 位 `time_t` ABI 的库都被重命名，加上了 `t64` 后缀，包名直接变了。Ubuntu 24.04 同理。
>
> 💡 `apt install` 即使 **当前目录不在 `/opt/rejubang/backend`** 也能执行，保持在这目录方便后续命令。

### 4.4 快速验证 Playwright 能启动 Chromium

```
root@server:/opt/rejubang/backend# ./venv/bin/python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True, args=['--no-sandbox']); print('OK'); b.close()"
```

**只要输出 `OK` 就说明 Playwright 完全装好了。** 其他警告（如 libGL 警告）可以忽略。

---

## 5. 测试爬虫（可选，可跳过先部署）

```
root@server:/opt/rejubang/backend# ./venv/bin/python test_crawl.py --skip-discovery
```

重点看 `[1/3] 检查Playwright...` 下面是否有两行 ✓：

```
[1/3] 检查Playwright...
  ✓ playwright模块已安装
  ✓ chromium浏览器可启动
```

这两个 ✓ 就说明 Playwright 没问题。

> ⚠️ `[3/3]` 里各平台的热度提取结果可能显示 "未发现任何剧" 或 "热度值: 0"，这是**正常现象**——视频平台页面结构会不定期变动，爬虫逻辑需要跟着调整。这不影响 API 服务启动，后续可单独排查。

---

## 6. 关于"SSH 断开后重连"的注意事项

如果你用安卓 SSH 客户端（Termius / JuiceSSH）或本地网络不稳定，SSH 断开重连后会**回到 `/root` 目录**，不在 `/opt/rejubang/backend` 了。

重连后养成习惯先 `cd` 一下：

```
root@server:~# cd /opt/rejubang/backend
root@server:/opt/rejubang/backend# pwd
/opt/rejubang/backend
```

看到提示符末尾是 `/opt/rejubang/backend#` 才能继续执行后面的命令。

---

## 7. 本册完成检查清单

- [ ] `/opt/rejubang/backend/` 下有 `app/`、`crawlers/`、`venv/` 等目录
- [ ] `./venv/bin/pip list | grep Flask` 能看到 Flask 3.0.0
- [ ] `./venv/bin/playwright install chromium` 执行完成
- [ ] Playwright 快速验证命令输出了 `OK`

---

👉 进入 [04-数据库配置.md](./04-数据库配置.md)
