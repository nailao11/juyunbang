-- =================================================================
-- 测试用在播剧（2026 年 4 月验证用）
-- 用户提供的真实在播剧 URL/ID，用于端到端验证半自动爬虫架构
--
-- 导入方式:
--   mysql -u rejubang -p'你的数据库密码' rejubang < migrations/test_dramas.sql
--
-- 导入后:
--   1. 浏览器打开 https://<你的API域名>/admin 登录可见
--   2. SSH 上跑: ./venv/bin/python test_crawl.py --run
--   3. 等 1-2 分钟，查数据库: SELECT d.title, p.short_name, h.heat_value, h.record_time
--      FROM heat_realtime h JOIN dramas d ON h.drama_id=d.id
--      JOIN platforms p ON h.platform_id=p.id ORDER BY h.record_time DESC LIMIT 20;
-- =================================================================

USE rejubang;

-- 1. 蜜语纪（腾讯 + 爱奇艺）
INSERT INTO dramas (title, type, status, air_date)
  VALUES ('蜜语纪', 'tv_drama', 'airing', '2026-04-13')
  ON DUPLICATE KEY UPDATE status='airing', air_date='2026-04-13';
SET @id1 = (SELECT id FROM dramas WHERE title = '蜜语纪' LIMIT 1);

-- 2. 方圆八百米（腾讯 + 爱奇艺）
INSERT INTO dramas (title, type, status, air_date)
  VALUES ('方圆八百米', 'tv_drama', 'airing', '2026-04-17')
  ON DUPLICATE KEY UPDATE status='airing', air_date='2026-04-17';
SET @id2 = (SELECT id FROM dramas WHERE title = '方圆八百米' LIMIT 1);

-- 3. 优酷测试剧
INSERT INTO dramas (title, type, status, air_date)
  VALUES ('优酷测试剧', 'tv_drama', 'airing', CURDATE())
  ON DUPLICATE KEY UPDATE status='airing';
SET @id3 = (SELECT id FROM dramas WHERE title = '优酷测试剧' LIMIT 1);

-- 平台 ID（按 seed_data.sql 插入顺序固定）
SET @p_iqiyi   = (SELECT id FROM platforms WHERE short_name = 'iqiyi');
SET @p_youku   = (SELECT id FROM platforms WHERE short_name = 'youku');
SET @p_tencent = (SELECT id FROM platforms WHERE short_name = 'tencent');

-- 蜜语纪: 腾讯 mzc002006dzzunf + 爱奇艺 v_pz64qf5dtk
INSERT INTO drama_platforms (drama_id, platform_id, platform_drama_id, platform_url) VALUES
  (@id1, @p_tencent, 'mzc002006dzzunf',
   'https://m.v.qq.com/x/cover/mzc002006dzzunf.html'),
  (@id1, @p_iqiyi,   'v_pz64qf5dtk',
   'https://www.iqiyi.com/v_pz64qf5dtk.html')
ON DUPLICATE KEY UPDATE
  platform_drama_id = VALUES(platform_drama_id),
  platform_url = VALUES(platform_url);

-- 方圆八百米: 腾讯 mzc002007tp60ap + 爱奇艺 v_twylt9v918
INSERT INTO drama_platforms (drama_id, platform_id, platform_drama_id, platform_url) VALUES
  (@id2, @p_tencent, 'mzc002007tp60ap',
   'https://m.v.qq.com/x/cover/mzc002007tp60ap.html'),
  (@id2, @p_iqiyi,   'v_twylt9v918',
   'https://www.iqiyi.com/v_twylt9v918.html')
ON DUPLICATE KEY UPDATE
  platform_drama_id = VALUES(platform_drama_id),
  platform_url = VALUES(platform_url);

-- 优酷测试剧: 优酷 ccdb02ca7e5249ccbb3e
INSERT INTO drama_platforms (drama_id, platform_id, platform_drama_id, platform_url) VALUES
  (@id3, @p_youku, 'ccdb02ca7e5249ccbb3e',
   'https://v.youku.com/v_show/id_ccdb02ca7e5249ccbb3e.html')
ON DUPLICATE KEY UPDATE
  platform_drama_id = VALUES(platform_drama_id),
  platform_url = VALUES(platform_url);

-- 完成提示
SELECT '测试数据已录入，现在可以在 /admin 页面看到，或运行 test_crawl.py --run' AS info;
SELECT d.id, d.title, d.status, d.air_date,
       GROUP_CONCAT(p.short_name ORDER BY p.sort_order) AS platforms
FROM dramas d
LEFT JOIN drama_platforms dp ON dp.drama_id = d.id
LEFT JOIN platforms p ON p.id = dp.platform_id
WHERE d.title IN ('蜜语纪','方圆八百米','优酷测试剧')
GROUP BY d.id;
