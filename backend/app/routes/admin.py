"""
管理后台（剧集录入）

路由:
    GET  /admin                         登录页/管理面板 HTML
    POST /admin/login                   提交 ADMIN_TOKEN，换 Cookie
    POST /admin/logout                  清 Cookie
    GET  /admin/dramas                  当前剧集列表（JSON）
    POST /admin/dramas                  新增/更新一部剧
    POST /admin/dramas/<id>/delete      下架（设为 finished）
    POST /admin/dramas/<id>/reair       重新上架（设为 airing）
    POST /admin/test_extract            测试单条 URL 的热度提取（不入库），返回 debug 字段

认证：使用 .env 里的 ADMIN_TOKEN，登录后写 HttpOnly Cookie。
"""

import os
from functools import wraps
from datetime import date
from flask import Blueprint, request, jsonify, make_response

from ..config import Config
from ..utils.db import query, query_one, execute, insert
from ..utils.platform_url import parse_multi, parse_platform_input, normalize_platform


admin_bp = Blueprint('admin', __name__)


COOKIE_NAME = 'rejubang_admin'


def _expected_token():
    tok = os.getenv('ADMIN_TOKEN') or getattr(Config, 'ADMIN_TOKEN', '')
    return tok.strip() if tok else ''


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = _expected_token()
        if not expected:
            return jsonify({'code': 500, 'msg': 'ADMIN_TOKEN 未配置'}), 500
        got = request.cookies.get(COOKIE_NAME) \
            or request.headers.get('X-Admin-Token') \
            or request.args.get('token')
        if got != expected:
            return jsonify({'code': 401, 'msg': '未登录或 token 错误'}), 401
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route('/login', methods=['POST'])
def admin_login():
    expected = _expected_token()
    if not expected:
        return jsonify({'code': 500, 'msg': 'ADMIN_TOKEN 未配置'}), 500

    data = request.get_json(silent=True) or request.form
    token = (data.get('token') or '').strip()
    if token != expected:
        return jsonify({'code': 401, 'msg': 'Token 错误'}), 401

    resp = make_response(jsonify({'code': 0, 'msg': 'ok'}))
    resp.set_cookie(COOKIE_NAME, expected,
                    max_age=7 * 86400, httponly=True, samesite='Lax',
                    secure=request.is_secure)
    return resp


@admin_bp.route('/logout', methods=['POST'])
def admin_logout():
    resp = make_response(jsonify({'code': 0, 'msg': 'ok'}))
    resp.delete_cookie(COOKIE_NAME)
    return resp


@admin_bp.route('/dramas', methods=['GET'])
@require_admin
def list_dramas():
    rows = query("""
        SELECT d.id, d.title, d.status, d.air_date, d.poster_url,
               GROUP_CONCAT(p.short_name ORDER BY p.sort_order SEPARATOR ',') AS platforms,
               GROUP_CONCAT(CONCAT(p.short_name,':',IFNULL(dp.platform_drama_id,''))
                            ORDER BY p.sort_order SEPARATOR '|') AS platform_ids,
               (SELECT MAX(record_time) FROM heat_realtime h WHERE h.drama_id = d.id) AS last_crawl
        FROM dramas d
        LEFT JOIN drama_platforms dp ON dp.drama_id = d.id
        LEFT JOIN platforms p ON p.id = dp.platform_id
        GROUP BY d.id
        ORDER BY d.status = 'airing' DESC, d.air_date DESC
        LIMIT 200
    """)
    for r in rows:
        if r.get('air_date'):
            r['air_date'] = r['air_date'].isoformat()
        if r.get('last_crawl'):
            r['last_crawl'] = r['last_crawl'].isoformat(sep=' ', timespec='seconds')
    return jsonify({'code': 0, 'data': rows})


@admin_bp.route('/dramas', methods=['POST'])
@require_admin
def add_drama():
    """新增/更新一部剧（按标题 upsert）"""
    data = request.get_json(silent=True) or request.form
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'code': 400, 'msg': '缺少剧名'}), 400

    air_date = (data.get('air_date') or '').strip() or date.today().isoformat()
    poster_url = (data.get('poster_url') or '').strip() or None
    drama_type = (data.get('type') or 'tv_drama').strip()
    synopsis = (data.get('synopsis') or '').strip() or None

    platform_inputs = {
        'tencent': (data.get('tencent') or '').strip(),
        'iqiyi':   (data.get('iqiyi')   or '').strip(),
        'youku':   (data.get('youku')   or '').strip(),
        'mgtv':    (data.get('mgtv')    or '').strip(),
    }
    parsed, errors = parse_multi(platform_inputs)
    if not parsed:
        return jsonify({
            'code': 400,
            'msg': '至少需要一个平台的完整页面链接',
            'errors': errors,
        }), 400

    existing = query_one("SELECT id FROM dramas WHERE title = %s LIMIT 1", (title,))
    if existing:
        drama_id = existing['id']
        execute("""UPDATE dramas SET status='airing', air_date=%s,
                   poster_url=COALESCE(%s, poster_url),
                   synopsis=COALESCE(%s, synopsis)
                   WHERE id=%s""",
                (air_date, poster_url, synopsis, drama_id))
    else:
        drama_id = insert("""INSERT INTO dramas
            (title, type, status, air_date, poster_url, synopsis)
            VALUES (%s, %s, 'airing', %s, %s, %s)""",
            (title, drama_type, air_date, poster_url, synopsis))

    plat_rows = query("SELECT id, short_name FROM platforms")
    plat_map = {r['short_name']: r['id'] for r in plat_rows}

    linked = []
    for short_name, pid, url in parsed:
        platform_id = plat_map.get(short_name)
        if not platform_id:
            continue
        execute("""INSERT INTO drama_platforms
            (drama_id, platform_id, platform_drama_id, platform_url)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                platform_drama_id = VALUES(platform_drama_id),
                platform_url = VALUES(platform_url)""",
            (drama_id, platform_id, pid, url))
        linked.append({'platform': short_name, 'id': pid, 'url': url})

    return jsonify({
        'code': 0,
        'msg': '已保存',
        'data': {'drama_id': drama_id, 'title': title,
                 'linked': linked, 'warnings': errors},
    })


@admin_bp.route('/dramas/<int:drama_id>/delete', methods=['POST'])
@require_admin
def delete_drama(drama_id):
    execute("UPDATE dramas SET status='finished' WHERE id=%s", (drama_id,))
    return jsonify({'code': 0, 'msg': '已下架'})


@admin_bp.route('/dramas/<int:drama_id>/reair', methods=['POST'])
@require_admin
def reair_drama(drama_id):
    execute("UPDATE dramas SET status='airing' WHERE id=%s", (drama_id,))
    return jsonify({'code': 0, 'msg': '已上架'})


@admin_bp.route('/test_extract', methods=['POST'])
@require_admin
def test_extract():
    """对给定完整页面链接立即跑一次提取（不入库），返回 value + debug。"""
    data = request.get_json(silent=True) or request.form
    platform = normalize_platform(data.get('platform'))
    raw = (data.get('url') or '').strip()

    if not platform or not raw:
        return jsonify({'code': 400, 'msg': '缺少 platform 或 url'}), 400

    drama_id, url = parse_platform_input(platform, raw)
    if not url:
        return jsonify({
            'code': 400,
            'msg': f'{platform}: 请填写完整页面链接',
        }), 400

    from crawlers.browser_helper import BrowserHelper
    from crawlers.airing_crawler import AiringCrawler

    crawler = AiringCrawler()
    extractor_name = crawler.PLATFORM_EXTRACTORS.get(platform)
    if not extractor_name:
        return jsonify({'code': 400, 'msg': f'{platform} 不支持热度提取'}), 400

    value = 0
    error = None
    try:
        with BrowserHelper(headless=True) as browser:
            extractor = getattr(crawler, extractor_name)
            value = extractor(browser, url)
    except Exception as e:
        error = f'{type(e).__name__}: {e}'

    debug = crawler.get_last_debug()
    if error:
        debug.setdefault('errors', []).append(error)

    return jsonify({
        'code': 0,
        'msg': '提取完成' if value else '未提取到数值',
        'data': {
            'platform': platform,
            'url': url,
            'platform_drama_id': drama_id,
            'value': value,
            'debug': debug,
        },
    })


# ================================================================
# 管理面板 HTML（响应式卡片布局）
# ================================================================

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>神奇奶酪 · 热剧榜管理后台</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; min-height: 100%; }
  body {
    font: 14px/1.55 -apple-system,"Segoe UI",Roboto,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    background: linear-gradient(135deg,#667eea 0%,#764ba2 100%);
    color: #2a2a3a; min-height: 100vh; padding: 24px 16px 80px;
  }
  .wrap { max-width: 980px; margin: 0 auto; }
  h1 { color: #fff; font-size: 24px; margin: 4px 0 6px; text-shadow: 0 2px 8px rgba(0,0,0,.18); }
  .sub { color: rgba(255,255,255,.85); margin: 0 0 22px; font-size: 13px; }
  .sub code { background: rgba(255,255,255,.18); padding: 1px 6px; border-radius: 4px; }
  .topbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
  .card { background: #fff; border-radius: 14px; padding: 22px;
          box-shadow: 0 6px 22px rgba(0,0,0,.10); margin-bottom: 18px; }
  .card h2 { margin: 0 0 14px; font-size: 17px; color: #333; display: flex; align-items: center; gap: 8px; }
  .card h2 .ico { display: inline-flex; width: 26px; height: 26px; border-radius: 8px;
                  background: linear-gradient(135deg,#667eea,#764ba2); color:#fff; font-size:14px;
                  align-items: center; justify-content: center; }
  label { display: block; margin: 12px 0 4px; font-weight: 600; color: #555; font-size: 13px; }
  input, textarea, select {
    width: 100%; padding: 9px 12px; border: 1px solid #dde2ea; border-radius: 8px;
    font-size: 14px; font-family: inherit; transition: border-color .15s, box-shadow .15s;
    background: #fafbfc;
  }
  input:focus, textarea:focus, select:focus {
    outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102,126,234,.15); background: #fff;
  }
  textarea { resize: vertical; min-height: 60px; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .grid-platforms { display: grid; grid-template-columns: 1fr; gap: 4px; }
  @media (min-width: 720px) { .grid-platforms { grid-template-columns: 1fr 1fr; gap: 14px; } }
  .hint { color: #888; font-size: 12px; margin-top: 4px; line-height: 1.5; }
  .btn { background: linear-gradient(135deg,#667eea,#764ba2); color: #fff; border: 0;
         padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600;
         transition: transform .12s ease, box-shadow .15s ease; }
  .btn:hover { box-shadow: 0 4px 14px rgba(102,126,234,.4); }
  .btn:active { transform: translateY(1px); }
  .btn.secondary { background: #6c757d; }
  .btn.danger { background: #e74c3c; }
  .btn.small { padding: 6px 14px; font-size: 12px; }
  .btn-row { margin-top: 16px; display: flex; flex-wrap: wrap; gap: 10px; }
  .result { margin-top: 14px; padding: 12px; border-radius: 8px; white-space: pre-wrap; word-break: break-all;
            font-family: ui-monospace,Menlo,Consolas,monospace; font-size: 12.5px; line-height: 1.55; }
  .result.ok { background: #e8f7ee; color: #185c2c; border-left: 3px solid #2dce89; }
  .result.err { background: #fdecee; color: #6f1c24; border-left: 3px solid #e74c3c; }
  .result.info { background: #eef2ff; color: #2d3a76; border-left: 3px solid #667eea; }

  /* 在播剧清单：响应式卡片 */
  .drama-grid { display: grid; grid-template-columns: 1fr; gap: 10px; }
  @media (min-width: 720px) { .drama-grid { grid-template-columns: 1fr 1fr; } }
  .drama-row { border: 1px solid #eef0f4; border-radius: 10px; padding: 12px 14px;
               display: flex; flex-direction: column; gap: 6px; background: #fcfcfd; }
  .drama-row .dname { font-weight: 700; font-size: 15px; color: #2a2a3a; word-break: break-all; }
  .drama-row .dmeta { color: #777; font-size: 12px; }
  .drama-row .dplats { display: flex; flex-wrap: wrap; gap: 6px; }
  .drama-row .dactions { display: flex; gap: 8px; margin-top: 4px; }
  .badge { display: inline-block; padding: 2px 9px; border-radius: 11px; font-size: 11px;
           color: #fff; line-height: 1.6; }
  .p-tencent { background: #12b7f5; }
  .p-iqiyi   { background: #00a862; }
  .p-youku   { background: #ff6600; }
  .p-mgtv    { background: #ff5f00; }
  .status-pill { display: inline-block; padding: 2px 8px; border-radius: 8px; font-size: 11px;
                 background: #e8eaf2; color: #555; }
  .status-pill.airing { background: #e8f7ee; color: #185c2c; }
  .status-pill.finished { background: #f1f3f8; color: #888; }

  /* 测试结果展示 */
  .debug-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12.5px; }
  .debug-table th, .debug-table td { padding: 6px 10px; border-bottom: 1px solid #eef0f4;
                                     text-align: left; vertical-align: top; word-break: break-all; }
  .debug-table th { background: #f5f6fa; font-weight: 600; color: #555; width: 32%; }

  /* 登录卡 */
  #loginCard { max-width: 420px; margin: 60px auto 0; }
  #loginCard input { font-size: 15px; }

  /* 顶部退出按钮 */
  .quick-actions { display: flex; gap: 8px; align-items: center; }
  footer { text-align: center; color: rgba(255,255,255,.7); font-size: 12px; margin-top: 24px; }
</style>
</head>
<body>
<div class="wrap">

<div id="loginView" style="display:none">
  <h1>神奇奶酪 · 热剧榜管理后台</h1>
  <p class="sub">请输入 <code>ADMIN_TOKEN</code> 登录</p>
  <div class="card" id="loginCard">
    <label>Admin Token</label>
    <input type="password" id="tokenInput" placeholder="粘贴 .env 中的 ADMIN_TOKEN">
    <div class="btn-row"><button class="btn" onclick="doLogin()">登录</button></div>
    <div id="loginResult"></div>
  </div>
</div>

<div id="mainView" style="display:none">
  <div class="topbar">
    <div>
      <h1>神奇奶酪 · 热剧榜管理后台</h1>
      <p class="sub">
        录入后约 15 分钟内爬虫自动采集；如需立即采集请 <code>systemctl restart rejubang-crawler</code>
      </p>
    </div>
    <div class="quick-actions">
      <button class="btn secondary small" onclick="doLogout()">退出登录</button>
    </div>
  </div>

  <div class="card">
    <h2><span class="ico">＋</span>新增 / 更新剧集</h2>

    <label>剧名 <span style="color:#e74c3c">*</span></label>
    <input id="title" placeholder="例：方圆八百米">

    <div class="row">
      <div>
        <label>开播日期</label>
        <input id="air_date" type="date">
        <div class="hint">留空默认为今天</div>
      </div>
      <div>
        <label>类型</label>
        <select id="type">
          <option value="tv_drama">电视剧</option>
          <option value="web_drama">网络剧</option>
          <option value="variety">综艺</option>
          <option value="anime">动漫</option>
          <option value="documentary">纪录片</option>
        </select>
      </div>
    </div>

    <label>海报图 URL（可选）</label>
    <input id="poster_url" placeholder="https://...">

    <div style="margin:18px 0 8px; padding-top:14px; border-top:1px dashed #e0e3eb;">
      <strong style="color:#444;">各平台完整页面链接</strong>
      <span style="color:#999;font-size:12px;">（至少填 1 个；不再接受裸 ID，请填浏览器地址栏完整 URL）</span>
    </div>

    <div class="grid-platforms">
      <div>
        <label>腾讯视频 — 移动播放页</label>
        <input id="tencent" placeholder="https://m.v.qq.com/x/m/play?cid=...&vid=...">
        <div class="hint">用手机浏览器打开剧集任意一集，复制地址栏 URL（带 cid 和 vid）</div>
      </div>
      <div>
        <label>爱奇艺 — PC 专辑页</label>
        <input id="iqiyi" placeholder="https://www.iqiyi.com/a_xxx.html">
        <div class="hint">必须是带 <code>a_</code> 前缀的专辑页，不要单集页 <code>v_</code></div>
      </div>
      <div>
        <label>优酷 — PC 播放页</label>
        <input id="youku" placeholder="https://v.youku.com/v_show/id_xxx.html">
        <div class="hint">从 v.youku.com 剧集详情或单集播放页复制完整 URL</div>
      </div>
      <div>
        <label>芒果TV — 完整页面链接</label>
        <input id="mgtv" placeholder="https://www.mgtv.com/b/{partId}/{clipId}.html">
        <div class="hint">从 mgtv.com 剧集页面复制完整 URL（含两段数字 ID）</div>
      </div>
    </div>

    <label>剧情简介（可选）</label>
    <textarea id="synopsis" rows="3"></textarea>

    <div class="btn-row">
      <button class="btn" onclick="submitDrama()">保存录入</button>
      <button class="btn secondary" onclick="testExtract()">先测试热度提取</button>
    </div>
    <div id="submitResult"></div>
  </div>

  <div class="card" id="testCard" style="display:none">
    <h2><span class="ico">⚙</span>热度提取测试结果</h2>
    <div id="testResultBox"></div>
  </div>

  <div class="card">
    <h2 style="display:flex;align-items:center;justify-content:space-between;">
      <span style="display:flex;align-items:center;gap:8px;"><span class="ico">📋</span>当前剧集</span>
      <button class="btn secondary small" onclick="loadList()">刷新</button>
    </h2>
    <div id="dramaList">加载中…</div>
  </div>

  <footer>神奇奶酪出品 · 热剧榜后台</footer>
</div>

</div>

<script>
const API = '/api/v1/admin';
const $ = id => document.getElementById(id);

function toast(el, msg, kind) {
  el.innerHTML = '<div class="result ' + (kind || 'info') + '">' + msg + '</div>';
}

async function doLogin() {
  const token = $('tokenInput').value.trim();
  const res = await fetch(API + '/login', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token })
  });
  const d = await res.json();
  if (res.ok && d.code === 0) showMain();
  else toast($('loginResult'), d.msg || '登录失败', 'err');
}

async function doLogout() {
  await fetch(API + '/logout', { method: 'POST', credentials: 'same-origin' });
  location.reload();
}

function escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function submitDrama() {
  const payload = {};
  ['title','air_date','type','poster_url','tencent','iqiyi','youku','mgtv','synopsis']
    .forEach(k => { payload[k] = ($(k).value || '').trim(); });

  if (!payload.title) {
    toast($('submitResult'), '剧名不能为空', 'err');
    return;
  }
  if (!payload.tencent && !payload.iqiyi && !payload.youku && !payload.mgtv) {
    toast($('submitResult'), '请至少填写一个平台的完整页面链接', 'err');
    return;
  }

  const res = await fetch(API + '/dramas', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const d = await res.json();
  if (d.code === 0) {
    let html = '✓ 已保存，drama_id=' + d.data.drama_id + '\n';
    (d.data.linked || []).forEach(l => {
      html += '  [' + l.platform + '] ' + l.id + ' → ' + l.url + '\n';
    });
    if (d.data.warnings && d.data.warnings.length) {
      html += '\n⚠ 以下输入被忽略：\n' + d.data.warnings.join('\n');
    }
    toast($('submitResult'), escHtml(html), 'ok');
    loadList();
    ['title','poster_url','tencent','iqiyi','youku','mgtv','synopsis']
      .forEach(k => { $(k).value = ''; });
  } else {
    let msg = '✗ ' + (d.msg || '保存失败');
    if (d.errors && d.errors.length) msg += '\n' + d.errors.join('\n');
    toast($('submitResult'), escHtml(msg), 'err');
  }
}

function debugTable(d) {
  if (!d) return '';
  const rows = [
    ['platform', d.platform],
    ['source_type', d.source_type],
    ['match_pattern', d.match_pattern],
    ['matched_snippet', d.matched_snippet],
    ['final_url', d.final_url],
    ['errors', (d.errors && d.errors.length) ? d.errors.join(' | ') : ''],
  ];
  if (d.candidate_urls && d.candidate_urls.length) {
    rows.push(['candidate_urls', d.candidate_urls.join('\n')]);
  }
  let html = '<table class="debug-table">';
  rows.forEach(r => {
    html += '<tr><th>' + escHtml(r[0]) + '</th><td style="white-space:pre-wrap;word-break:break-all;">' +
            escHtml(r[1] == null ? '' : r[1]) + '</td></tr>';
  });
  html += '</table>';
  return html;
}

async function testExtract() {
  const platforms = ['tencent','iqiyi','youku','mgtv'];
  const items = platforms
    .map(p => ({ p, v: ($(p).value || '').trim() }))
    .filter(x => x.v);

  if (!items.length) {
    toast($('submitResult'), '请先填写至少一个平台链接再点测试', 'err');
    return;
  }

  $('testCard').style.display = '';
  const box = $('testResultBox');
  box.innerHTML = '<div class="result info">测试中…</div>';

  const blocks = [];
  for (const it of items) {
    blocks.push('<div class="result info" style="margin-top:10px;"><strong>' +
      escHtml(it.p) + '</strong> 测试中… ' + escHtml(it.v) + '</div>');
    box.innerHTML = blocks.join('');
    try {
      const res = await fetch(API + '/test_extract', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: it.p, url: it.v })
      });
      const d = await res.json();
      const ok = d.code === 0 && d.data && Number(d.data.value) > 0;
      const cls = ok ? 'ok' : 'err';
      const mark = ok ? '✓' : '✗';
      const valTxt = (d.data && d.data.value) ? d.data.value : '0';
      const block =
        '<div class="result ' + cls + '" style="margin-top:10px;">' +
        '<strong>' + mark + ' ' + escHtml(it.p) + '</strong>　value = <strong>' +
        escHtml(valTxt) + '</strong>' +
        (d.msg ? '　<span style="opacity:.7;">' + escHtml(d.msg) + '</span>' : '') +
        debugTable(d.data && d.data.debug) +
        '</div>';
      blocks[blocks.length - items.length + items.indexOf(it)] = block;
      box.innerHTML = blocks.join('');
    } catch (e) {
      blocks.push('<div class="result err" style="margin-top:10px;">✗ ' +
        escHtml(it.p) + ' 异常：' + escHtml(e.message || e) + '</div>');
      box.innerHTML = blocks.join('');
    }
  }
}

async function loadList() {
  $('dramaList').innerHTML = '<div class="result info">加载中…</div>';
  const res = await fetch(API + '/dramas', { credentials: 'same-origin' });
  const d = await res.json();
  if (d.code !== 0) {
    $('dramaList').innerHTML = '<div class="result err">加载失败：' + escHtml(d.msg || '?') + '</div>';
    return;
  }
  if (!d.data.length) {
    $('dramaList').innerHTML = '<div class="result info">尚无剧集，请在上方表单录入。</div>';
    return;
  }
  let html = '<div class="drama-grid">';
  d.data.forEach(r => {
    const plats = (r.platforms || '').split(',').filter(Boolean)
      .map(p => '<span class="badge p-' + escHtml(p) + '">' + escHtml(p) + '</span>').join('');
    const statusCls = r.status === 'airing' ? 'airing' : (r.status === 'finished' ? 'finished' : '');
    const action = r.status === 'airing'
      ? '<button class="btn danger small" onclick="setStatus(' + r.id + ",'delete')\">下架</button>"
      : '<button class="btn small" onclick="setStatus(' + r.id + ",'reair')\">上架</button>";
    html +=
      '<div class="drama-row">' +
        '<div class="dname">' + escHtml(r.title || '?') + '</div>' +
        '<div class="dmeta">' +
          '<span class="status-pill ' + statusCls + '">' + escHtml(r.status || '?') + '</span>' +
          '　开播：' + escHtml(r.air_date || '-') +
          '　最近采集：' + escHtml(r.last_crawl || '未采') +
        '</div>' +
        '<div class="dplats">' + (plats || '<span class="status-pill">无平台</span>') + '</div>' +
        '<div class="dactions">' + action + '</div>' +
      '</div>';
  });
  html += '</div>';
  $('dramaList').innerHTML = html;
}

async function setStatus(id, action) {
  await fetch(API + '/dramas/' + id + '/' + action, { method: 'POST', credentials: 'same-origin' });
  loadList();
}

async function checkAuth() {
  const res = await fetch(API + '/dramas', { credentials: 'same-origin' });
  return res.ok;
}

function showMain() {
  $('loginView').style.display = 'none';
  $('mainView').style.display = 'block';
  $('air_date').value = new Date().toISOString().split('T')[0];
  loadList();
}

(async function init() {
  if (await checkAuth()) showMain();
  else $('loginView').style.display = 'block';
})();
</script>
</body>
</html>
"""


@admin_bp.route('', methods=['GET'])
@admin_bp.route('/', methods=['GET'])
def admin_page():
    return ADMIN_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}
