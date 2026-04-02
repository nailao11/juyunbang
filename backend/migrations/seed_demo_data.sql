-- ============================================================
-- 剧云榜 — 演示数据初始化
-- 为 heat_realtime 和 heat_daily 表注入示范数据
-- 使小程序首页和数据中心能展示内容
-- 运行方式：mysql -u juyunbang -p juyunbang < seed_demo_data.sql
-- ============================================================

-- 先清理可能存在的旧演示数据
DELETE FROM heat_realtime WHERE id > 0;
DELETE FROM heat_daily WHERE id > 0;

-- ============================================================
-- 1. 实时热度数据（heat_realtime）
--    首页依赖此表，查询条件：record_time >= NOW() - 30分钟
--    所以用 NOW() 作为记录时间
-- ============================================================

INSERT INTO heat_realtime (drama_id, platform_id, heat_value, heat_rank, record_time) VALUES
-- 爱奇艺(1)热度数据
(1, 1, 9580.50, 1, NOW()),
(2, 1, 9320.30, 2, NOW()),
(3, 1, 8750.00, 3, NOW()),
(4, 1, 8210.80, 4, NOW()),
(5, 1, 7960.20, 5, NOW()),
(6, 1, 7520.00, 6, NOW()),
(7, 1, 7100.50, 7, NOW()),
(8, 1, 6830.00, 8, NOW()),
(19, 1, 6500.00, 9, NOW()),
(22, 1, 6200.00, 10, NOW()),

-- 优酷(2)热度数据
(1, 2, 8920.00, 1, NOW()),
(2, 2, 8650.50, 2, NOW()),
(4, 2, 8100.00, 3, NOW()),
(5, 2, 7800.30, 4, NOW()),
(3, 2, 7500.00, 5, NOW()),
(23, 2, 7100.00, 6, NOW()),
(24, 2, 6800.00, 7, NOW()),
(6, 2, 6500.50, 8, NOW()),

-- 腾讯视频(3)热度数据
(2, 3, 9150.00, 1, NOW()),
(1, 3, 8800.50, 2, NOW()),
(5, 3, 8350.00, 3, NOW()),
(3, 3, 7920.00, 4, NOW()),
(4, 3, 7650.30, 5, NOW()),
(8, 3, 7200.00, 6, NOW()),
(25, 3, 6900.00, 7, NOW()),
(9, 3, 6600.00, 8, NOW()),

-- 芒果TV(4)热度数据
(19, 4, 9200.00, 1, NOW()),
(20, 4, 8500.00, 2, NOW()),
(1, 4, 7800.00, 3, NOW()),
(4, 4, 7300.50, 4, NOW()),
(21, 4, 6800.00, 5, NOW()),

-- 哔哩哔哩(5)热度数据
(7, 5, 9800.00, 1, NOW()),
(13, 5, 9200.50, 2, NOW()),
(9, 5, 8600.00, 3, NOW()),
(8, 5, 8100.00, 4, NOW()),
(15, 5, 7500.00, 5, NOW()),
(14, 5, 7000.30, 6, NOW()),
(11, 5, 6500.00, 7, NOW()),
(3, 5, 6200.00, 8, NOW()),

-- 30分钟前的数据（用于计算涨跌趋势）
(1, 1, 9350.00, 1, DATE_SUB(NOW(), INTERVAL 31 MINUTE)),
(2, 1, 9400.00, 2, DATE_SUB(NOW(), INTERVAL 31 MINUTE)),
(3, 1, 8500.00, 3, DATE_SUB(NOW(), INTERVAL 31 MINUTE)),
(4, 1, 8300.00, 4, DATE_SUB(NOW(), INTERVAL 31 MINUTE)),
(5, 1, 7800.00, 5, DATE_SUB(NOW(), INTERVAL 31 MINUTE));


-- ============================================================
-- 2. 日度热度统计（heat_daily）
--    数据中心页依赖此表
--    生成最近7天的日榜数据
-- ============================================================

INSERT INTO heat_daily (drama_id, platform_id, stat_date, heat_avg, heat_max, heat_min, heat_latest, rank_avg, rank_best, published_at) VALUES
-- 今天的数据
(1, 1, CURDATE(), 9500.00, 9800.00, 9200.00, 9580.50, 1, 1, NOW()),
(2, 1, CURDATE(), 9300.00, 9600.00, 9000.00, 9320.30, 2, 1, NOW()),
(3, 1, CURDATE(), 8700.00, 9100.00, 8300.00, 8750.00, 3, 2, NOW()),
(4, 1, CURDATE(), 8200.00, 8600.00, 7800.00, 8210.80, 4, 3, NOW()),
(5, 1, CURDATE(), 7900.00, 8200.00, 7600.00, 7960.20, 5, 4, NOW()),
(6, 1, CURDATE(), 7500.00, 7800.00, 7200.00, 7520.00, 6, 5, NOW()),
(7, 1, CURDATE(), 7100.00, 7500.00, 6800.00, 7100.50, 7, 6, NOW()),
(8, 1, CURDATE(), 6800.00, 7200.00, 6500.00, 6830.00, 8, 7, NOW()),
(19, 1, CURDATE(), 6500.00, 6800.00, 6200.00, 6500.00, 9, 8, NOW()),
(22, 1, CURDATE(), 6200.00, 6500.00, 5900.00, 6200.00, 10, 9, NOW()),
(9, 3, CURDATE(), 6000.00, 6300.00, 5700.00, 6000.00, 11, 10, NOW()),
(23, 2, CURDATE(), 5800.00, 6100.00, 5500.00, 5800.00, 12, 11, NOW()),
(13, 5, CURDATE(), 5600.00, 5900.00, 5300.00, 5600.00, 13, 12, NOW()),
(15, 5, CURDATE(), 5400.00, 5700.00, 5100.00, 5400.00, 14, 13, NOW()),
(14, 5, CURDATE(), 5200.00, 5500.00, 4900.00, 5200.00, 15, 14, NOW()),

-- 昨天的数据
(1, 1, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 9400.00, 9700.00, 9100.00, 9350.00, 1, 1, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(2, 1, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 9500.00, 9800.00, 9200.00, 9400.00, 2, 1, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(3, 1, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 8500.00, 8900.00, 8100.00, 8500.00, 3, 2, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(4, 1, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 8300.00, 8700.00, 7900.00, 8300.00, 4, 3, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(5, 1, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 7800.00, 8100.00, 7500.00, 7800.00, 5, 4, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(6, 1, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 7600.00, 7900.00, 7300.00, 7600.00, 6, 5, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(7, 1, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 7200.00, 7600.00, 6900.00, 7200.00, 7, 6, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(8, 1, DATE_SUB(CURDATE(), INTERVAL 1 DAY), 6900.00, 7300.00, 6600.00, 6900.00, 8, 7, DATE_SUB(NOW(), INTERVAL 1 DAY)),

-- 前天的数据
(1, 1, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 9200.00, 9500.00, 8900.00, 9200.00, 1, 1, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(2, 1, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 9600.00, 9900.00, 9300.00, 9600.00, 2, 1, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(3, 1, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 8300.00, 8700.00, 7900.00, 8300.00, 3, 2, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(4, 1, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 8500.00, 8900.00, 8100.00, 8500.00, 4, 3, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(5, 1, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 7600.00, 7900.00, 7300.00, 7600.00, 5, 4, DATE_SUB(NOW(), INTERVAL 2 DAY));
