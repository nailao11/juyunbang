# 热剧榜

全平台剧集实时热度监控与数据分析微信小程序。

## 功能特性

- 实时热度排行：聚合爱奇艺、优酷、腾讯视频、芒果TV 四大平台的热度数据
- 数据中心：日榜/周榜/月榜，播放量榜/热度榜/剧力指数榜/讨论度榜
- 剧集详情：热度展示、播放量统计、剧力指数雷达、多维度数据
- 多剧对比：选两部剧横向对比热度/播放/社交/口碑
- 搜索发现：按剧名搜索 + 热搜榜
- 深色模式：支持亮色/暗色/跟随系统

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 微信小程序原生（WXML + WXSS + JS） |
| 后端 | Python + Flask |
| 数据库 | MySQL (MariaDB) |
| 缓存 | Redis |
| Web服务器 | Nginx + SSL (Let's Encrypt) |
| WSGI | Gunicorn |
| 定时任务 | APScheduler |
| 文件存储 | 七牛云对象存储 |

## 项目结构

```
rejubang/
├── backend/                 # 后端代码
│   ├── app/                 # Flask应用
│   │   ├── routes/          # 7个API蓝图（auth/heat/daily/weekly/drama/search/system）
│   │   └── utils/           # 工具函数（db/cache/response/qiniu_helper/request_helpers）
│   ├── crawlers/            # 数据采集器（Playwright）
│   ├── processors/          # 数据处理器（清洗/日度/指数/异动）
│   ├── scheduler/           # APScheduler 定时任务
│   └── migrations/          # 数据库迁移
├── miniapp/                 # 微信小程序前端
│   ├── pages/               # 11个页面
│   ├── components/          # 7个公共组件
│   ├── utils/               # 工具函数
│   └── images/              # 图片资源
└── deploy/                  # 部署配置
    ├── nginx.conf
    ├── deploy.sh
    └── *.service
```

## 部署指南

详细的服务器搭建、数据库初始化、Playwright 安装、Nginx + SSL、systemd 服务等步骤请阅读：

- **部署指南.md** — 完整部署流程（一步一步操作指引）
- **追剧助手微信小程序_完整开发方案.md** — 前期设计文档（产品定位、功能清单、页面设计、算法说明）

## 环境要求

- 服务器：Debian / Ubuntu
- Python 3.8+
- MySQL 8.0+ / MariaDB 10.5+
- Redis 6.0+
- Nginx 1.18+
- Node.js（微信开发者工具需要）
