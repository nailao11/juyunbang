-- ================================================================
-- 剧云榜数据库结构
-- 字符集：utf8mb4
-- ================================================================

USE juyunbang;

-- 表1：剧集/综艺主表
CREATE TABLE IF NOT EXISTS dramas (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  title           VARCHAR(200) NOT NULL COMMENT '剧名',
  title_en        VARCHAR(200) DEFAULT NULL COMMENT '英文名/拼音',
  type            ENUM('tv_drama','web_drama','variety','anime','documentary')
                  NOT NULL COMMENT '类型',
  genre           VARCHAR(200) COMMENT '题材（逗号分隔）',
  region          VARCHAR(50) COMMENT '地区',
  total_episodes  INT DEFAULT 0 COMMENT '总集数',
  current_episode INT DEFAULT 0 COMMENT '当前更新到第几集',
  status          ENUM('upcoming','airing','finished') DEFAULT 'upcoming' COMMENT '状态',
  air_date        DATE COMMENT '首播日期',
  end_date        DATE COMMENT '完结日期',
  air_weekdays    VARCHAR(50) COMMENT '更新星期',
  air_time        TIME COMMENT '更新时间',
  vip_advance     INT DEFAULT 0 COMMENT 'VIP抢先看集数',
  director        VARCHAR(200) COMMENT '导演',
  writer          VARCHAR(200) COMMENT '编剧',
  cast_main       TEXT COMMENT '主演（JSON格式）',
  cast_support    TEXT COMMENT '配角（JSON格式）',
  production      VARCHAR(200) COMMENT '制作公司',
  distributor     VARCHAR(200) COMMENT '发行方',
  synopsis        TEXT COMMENT '剧情简介',
  poster_url      VARCHAR(500) COMMENT '海报图片URL',
  poster_h_url    VARCHAR(500) COMMENT '横版海报URL',
  douban_id       VARCHAR(50) COMMENT '豆瓣ID',
  douban_score    DECIMAL(3,1) DEFAULT NULL COMMENT '豆瓣评分',
  douban_votes    INT DEFAULT 0 COMMENT '豆瓣评分人数',
  is_exclusive    TINYINT(1) DEFAULT 0 COMMENT '是否独播',
  tags            VARCHAR(500) COMMENT '标签（逗号分隔）',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  INDEX idx_type (type),
  INDEX idx_status (status),
  INDEX idx_air_date (air_date),
  INDEX idx_region (region),
  FULLTEXT INDEX idx_title (title)
) ENGINE=InnoDB COMMENT='剧集/综艺主表';

-- 表2：平台表
CREATE TABLE IF NOT EXISTS platforms (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(50) NOT NULL COMMENT '平台名称',
  short_name  VARCHAR(20) NOT NULL COMMENT '简称',
  logo_url    VARCHAR(500) COMMENT '平台logo',
  website     VARCHAR(200) COMMENT '官网地址',
  color       VARCHAR(10) COMMENT '品牌色值',
  sort_order  INT DEFAULT 0 COMMENT '排序',
  is_active   TINYINT(1) DEFAULT 1 COMMENT '是否启用',
  UNIQUE KEY uk_short_name (short_name)
) ENGINE=InnoDB COMMENT='平台表';

INSERT IGNORE INTO platforms (name, short_name, color, sort_order) VALUES
('爱奇艺', 'iqiyi', '#00BE06', 1),
('优酷', 'youku', '#1EBCF2', 2),
('腾讯视频', 'tencent', '#FF6600', 3),
('芒果TV', 'mgtv', '#FF5F00', 4),
('哔哩哔哩', 'bilibili', '#FB7299', 5),
('搜狐视频', 'sohu', '#F04E23', 6),
('抖音', 'douyin', '#000000', 7),
('微博', 'weibo', '#E6162D', 8),
('百度', 'baidu', '#2932E1', 9);

-- 表3：剧集-平台关联表
CREATE TABLE IF NOT EXISTS drama_platforms (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  drama_id          INT NOT NULL,
  platform_id       INT NOT NULL,
  platform_drama_id VARCHAR(100) COMMENT '该剧在平台上的ID',
  platform_url      VARCHAR(500) COMMENT '该剧在平台上的链接',
  is_exclusive      TINYINT(1) DEFAULT 0 COMMENT '是否独播',

  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  FOREIGN KEY (platform_id) REFERENCES platforms(id),
  UNIQUE KEY uk_drama_platform (drama_id, platform_id)
) ENGINE=InnoDB COMMENT='剧集平台关联表';

-- 表4：分集信息表
CREATE TABLE IF NOT EXISTS drama_episodes (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  drama_id        INT NOT NULL,
  episode_number  INT NOT NULL COMMENT '集数',
  title           VARCHAR(200) COMMENT '单集标题',
  air_date        DATE COMMENT '播出日期',
  air_time        TIME COMMENT '播出时间',
  is_vip_advance  TINYINT(1) DEFAULT 0 COMMENT '是否VIP抢先看',
  duration_minutes INT COMMENT '时长(分钟)',

  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  UNIQUE KEY uk_drama_episode (drama_id, episode_number),
  INDEX idx_air_date (air_date)
) ENGINE=InnoDB COMMENT='分集信息表';

-- 表5：实时热度数据表
CREATE TABLE IF NOT EXISTS heat_realtime (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  drama_id    INT NOT NULL,
  platform_id INT NOT NULL,
  heat_value  DECIMAL(12,2) NOT NULL COMMENT '热度值',
  heat_rank   INT COMMENT '排名',
  record_time DATETIME NOT NULL COMMENT '记录时间',

  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  FOREIGN KEY (platform_id) REFERENCES platforms(id),
  INDEX idx_drama_time (drama_id, record_time),
  INDEX idx_platform_time (platform_id, record_time),
  INDEX idx_record_time (record_time)
) ENGINE=InnoDB COMMENT='实时热度数据表';

-- 表6：日度热度统计表
CREATE TABLE IF NOT EXISTS heat_daily (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  drama_id     INT NOT NULL,
  platform_id  INT NOT NULL,
  stat_date    DATE NOT NULL COMMENT '统计日期',
  heat_avg     DECIMAL(12,2) COMMENT '日均热度',
  heat_max     DECIMAL(12,2) COMMENT '日最高热度',
  heat_min     DECIMAL(12,2) COMMENT '日最低热度',
  heat_latest  DECIMAL(12,2) COMMENT '当日最后热度值',
  rank_avg     INT COMMENT '日均排名',
  rank_best    INT COMMENT '最佳排名',
  published_at DATETIME COMMENT '数据发布时间',

  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  FOREIGN KEY (platform_id) REFERENCES platforms(id),
  UNIQUE KEY uk_drama_platform_date (drama_id, platform_id, stat_date),
  INDEX idx_stat_date (stat_date)
) ENGINE=InnoDB COMMENT='日度热度统计表';

-- 表7：播放量快照表
CREATE TABLE IF NOT EXISTS playcount_snapshot (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  drama_id        INT NOT NULL,
  platform_id     INT NOT NULL,
  total_playcount BIGINT COMMENT '累计播放量',
  record_time     DATETIME NOT NULL COMMENT '记录时间',

  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  FOREIGN KEY (platform_id) REFERENCES platforms(id),
  INDEX idx_drama_platform_time (drama_id, platform_id, record_time)
) ENGINE=InnoDB COMMENT='播放量快照表';

-- 表8：日播放量统计表
CREATE TABLE IF NOT EXISTS playcount_daily (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY,
  drama_id          INT NOT NULL,
  platform_id       INT NOT NULL,
  stat_date         DATE NOT NULL COMMENT '统计日期',
  daily_increment   BIGINT COMMENT '日播放增量',
  total_accumulated BIGINT COMMENT '累计播放量',
  episode_latest    INT COMMENT '当日最新集数',
  avg_per_episode   BIGINT COMMENT '集均播放量',
  is_anomaly        TINYINT(1) DEFAULT 0 COMMENT '是否异常数据',
  anomaly_note      VARCHAR(200) COMMENT '异常说明',
  published_at      DATETIME COMMENT '数据发布时间',

  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  FOREIGN KEY (platform_id) REFERENCES platforms(id),
  UNIQUE KEY uk_drama_platform_date (drama_id, platform_id, stat_date),
  INDEX idx_stat_date (stat_date)
) ENGINE=InnoDB COMMENT='日播放量统计表';

-- 表9：社交媒体日数据表
CREATE TABLE IF NOT EXISTS social_daily (
  id                        BIGINT AUTO_INCREMENT PRIMARY KEY,
  drama_id                  INT NOT NULL,
  stat_date                 DATE NOT NULL COMMENT '统计日期',
  weibo_topic_read          BIGINT COMMENT '微博话题累计阅读量',
  weibo_topic_read_incr     BIGINT COMMENT '微博话题日增阅读量',
  weibo_topic_discuss       BIGINT COMMENT '微博话题累计讨论量',
  weibo_topic_discuss_incr  BIGINT COMMENT '微博话题日增讨论量',
  weibo_super_topic_fans    INT COMMENT '超话粉丝数',
  weibo_hot_search_count    INT COMMENT '当日上微博热搜次数',
  douyin_topic_views        BIGINT COMMENT '抖音话题累计播放量',
  douyin_topic_views_incr   BIGINT COMMENT '抖音话题日增播放量',
  douyin_video_count        INT COMMENT '抖音相关视频数',
  baidu_index               INT COMMENT '百度搜索指数',
  wechat_index              INT COMMENT '微信指数',
  published_at              DATETIME COMMENT '数据发布时间',

  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  UNIQUE KEY uk_drama_date (drama_id, stat_date),
  INDEX idx_stat_date (stat_date)
) ENGINE=InnoDB COMMENT='社交媒体日数据表';

-- 表10：剧力指数日数据表
CREATE TABLE IF NOT EXISTS drama_index_daily (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  drama_id         INT NOT NULL,
  stat_date        DATE NOT NULL COMMENT '统计日期',
  index_total      DECIMAL(5,2) COMMENT '剧力指数总分(0-100)',
  index_heat       DECIMAL(5,2) COMMENT '平台热度维度得分',
  index_social     DECIMAL(5,2) COMMENT '全网讨论度维度得分',
  index_playcount  DECIMAL(5,2) COMMENT '播放表现维度得分',
  index_reputation DECIMAL(5,2) COMMENT '口碑评价维度得分',
  rank_total       INT COMMENT '综合排名',
  rank_change      INT DEFAULT 0 COMMENT '排名变化',
  published_at     DATETIME COMMENT '数据发布时间',

  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  UNIQUE KEY uk_drama_date (drama_id, stat_date),
  INDEX idx_stat_date (stat_date),
  INDEX idx_rank (stat_date, rank_total)
) ENGINE=InnoDB COMMENT='剧力指数日数据表';

-- 表11：用户表
CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  openid        VARCHAR(100) NOT NULL COMMENT '微信openid',
  unionid       VARCHAR(100) COMMENT '微信unionid',
  nickname      VARCHAR(100) COMMENT '昵称',
  avatar_url    VARCHAR(500) COMMENT '头像URL',
  gender        TINYINT COMMENT '性别 0未知 1男 2女',
  province      VARCHAR(50) COMMENT '省份',
  city          VARCHAR(50) COMMENT '城市',
  theme_mode    ENUM('light','dark','auto') DEFAULT 'auto' COMMENT '主题模式',
  notify_enabled TINYINT(1) DEFAULT 1 COMMENT '是否开启通知',
  last_login_at DATETIME COMMENT '最后登录时间',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_openid (openid),
  INDEX idx_unionid (unionid)
) ENGINE=InnoDB COMMENT='用户表';

-- 表12：用户追剧记录表
CREATE TABLE IF NOT EXISTS user_tracking (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT NOT NULL,
  drama_id        INT NOT NULL,
  status          ENUM('watching','want_to_watch','watched','dropped')
                  DEFAULT 'watching' COMMENT '追剧状态',
  current_episode INT DEFAULT 0 COMMENT '当前观看到第几集',
  user_score      DECIMAL(3,1) COMMENT '用户评分(1-10)',
  user_comment    TEXT COMMENT '用户短评',
  started_at      DATE COMMENT '开始追的日期',
  finished_at     DATE COMMENT '看完的日期',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  UNIQUE KEY uk_user_drama (user_id, drama_id),
  INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB COMMENT='用户追剧记录表';

-- 表13：用户追剧笔记表
CREATE TABLE IF NOT EXISTS user_notes (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT NOT NULL,
  drama_id        INT NOT NULL,
  episode_number  INT COMMENT '关联集数',
  content         TEXT NOT NULL COMMENT '笔记内容',
  is_private      TINYINT(1) DEFAULT 1 COMMENT '是否私密',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (drama_id) REFERENCES dramas(id),
  INDEX idx_user_drama (user_id, drama_id)
) ENGINE=InnoDB COMMENT='用户追剧笔记表';

-- 表14：影视资讯表
CREATE TABLE IF NOT EXISTS news (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  title             VARCHAR(300) NOT NULL COMMENT '标题',
  content           TEXT COMMENT '内容',
  summary           VARCHAR(500) COMMENT '摘要',
  cover_url         VARCHAR(500) COMMENT '封面图',
  source            VARCHAR(100) COMMENT '来源',
  source_url        VARCHAR(500) COMMENT '原文链接',
  category          ENUM('schedule','production','review','data_report','other')
                    COMMENT '分类',
  related_drama_ids VARCHAR(200) COMMENT '关联剧集ID',
  view_count        INT DEFAULT 0 COMMENT '浏览次数',
  is_published      TINYINT(1) DEFAULT 0 COMMENT '是否发布',
  published_at      DATETIME COMMENT '发布时间',
  created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='影视资讯表';

-- 表15：每日数据简报表
CREATE TABLE IF NOT EXISTS daily_report (
  id                      INT AUTO_INCREMENT PRIMARY KEY,
  stat_date               DATE NOT NULL COMMENT '统计日期',
  top_heat_drama_id       INT COMMENT '热度冠军剧集ID',
  top_heat_title          VARCHAR(200) COMMENT '热度冠军剧名',
  top_heat_value          DECIMAL(12,2) COMMENT '热度冠军热度值',
  top_play_drama_id       INT COMMENT '播放冠军剧集ID',
  top_play_title          VARCHAR(200) COMMENT '播放冠军剧名',
  top_play_value          BIGINT COMMENT '播放冠军播放量',
  biggest_riser_drama_id  INT COMMENT '最大黑马剧集ID',
  biggest_riser_title     VARCHAR(200) COMMENT '最大黑马剧名',
  biggest_riser_change    INT COMMENT '最大黑马排名上升位数',
  total_dramas            INT COMMENT '当日追踪剧集总数',
  summary                 TEXT COMMENT '日报摘要文字',
  generated_at            DATETIME COMMENT '生成时间',

  UNIQUE KEY uk_stat_date (stat_date)
) ENGINE=InnoDB COMMENT='数据简报表';

-- 表16：采集任务记录表
CREATE TABLE IF NOT EXISTS crawl_tasks (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  task_type     VARCHAR(50) NOT NULL COMMENT '任务类型',
  platform_id   INT COMMENT '平台ID',
  status        ENUM('pending','running','success','failed') DEFAULT 'pending',
  start_time    DATETIME COMMENT '开始时间',
  end_time      DATETIME COMMENT '结束时间',
  records_count INT DEFAULT 0 COMMENT '采集记录数',
  error_message TEXT COMMENT '错误信息',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='采集任务记录表';

-- 表17：系统配置表
CREATE TABLE IF NOT EXISTS system_config (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  config_key   VARCHAR(100) NOT NULL COMMENT '配置键',
  config_value TEXT COMMENT '配置值',
  description  VARCHAR(200) COMMENT '说明',
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_key (config_key)
) ENGINE=InnoDB COMMENT='系统配置表';

INSERT INTO system_config (config_key, config_value, description) VALUES
('crawl_interval_heat', '15', '热度采集间隔(分钟)'),
('crawl_interval_social', '60', '社交数据采集间隔(分钟)'),
('daily_publish_time', '15:00', '日榜发布时间'),
('weekly_publish_day', '1', '周榜发布星期(1=周一)'),
('index_weight_heat', '0.35', '剧力指数-热度权重'),
('index_weight_social', '0.25', '剧力指数-讨论度权重'),
('index_weight_play', '0.25', '剧力指数-播放量权重'),
('index_weight_reputation', '0.15', '剧力指数-口碑权重');

-- 表18：用户反馈表
CREATE TABLE IF NOT EXISTS feedback (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT COMMENT '用户ID',
  content    TEXT NOT NULL COMMENT '反馈内容',
  contact    VARCHAR(200) COMMENT '联系方式',
  type       VARCHAR(50) DEFAULT 'suggestion' COMMENT '类型',
  status     ENUM('pending','processing','resolved') DEFAULT 'pending',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='用户反馈表';
