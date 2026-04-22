"""
管理后台（剧集录入）

路由:
    GET  /admin                         → 登录页/管理面板 HTML
    POST /admin/login                   → 提交 ADMIN_TOKEN，换 Cookie
    POST /admin/logout                  → 清 Cookie
    GET  /admin/dramas                  → 当前在播剧列表（JSON）
    POST /admin/dramas                  → 新增/更新一部剧（JSON 或表单）
    POST /admin/dramas/<id>/delete      → 下架（设为 finished）
    POST /admin/dramas/<id>/reair       → 重新上架（设为 airing）
    POST /admin/test_extract            → 测试单条 URL 的热度提取（不入库）

认证:
    用 .env 里的 ADMIN_TOKEN 做简单 token 认证。登录后写 HttpOnly Cookie，
    后续请求通过 Cookie 验证。不需要微信登录。
"""

import os
from functools import wraps
from datetime import date
from flask import Blueprint, request, jsonify, make_response, render_template_string

from ..config import Config
from ..utils.db import query, query_one, execute, insert
from ..utils.platform_url import parse_multi, parse_platform_input, normalize_platform


admin_bp = Blueprint('admin', __name__)


# ================================================================
# 认证
# ================================================================

COOKIE_NAME = 'rejubang_admin'


def _expected_token():
    tok = os.getenv('ADMIN_TOKEN') or getattr(Config, 'ADMIN_TOKEN', '')
    return tok.strip() if tok else ''


def require_admin(fn):
    """装饰器：验证请求带了合法的 ADMIN_TOKEN"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = _expected_token()
        if not expected:
            return jsonify({'code': 500,
                            'msg': 'ADMIN_TOKEN 未配置，无法使用管理后台'}), 500
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


# ================================================================
# 剧集录入
# ================================================================

@admin_bp.route('/dramas', methods=['GET'])
@require_admin
def list_dramas():
    """列出所有在播剧 + 已配置的平台清单"""
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
    # 把日期/时间对象转字符串
    for r in rows:
        if r.get('air_date'):
            r['air_date'] = r['air_date'].isoformat()
        if r.get('last_crawl'):
            r['last_crawl'] = r['last_crawl'].isoformat(sep=' ', timespec='seconds')
    return jsonify({'code': 0, 'data': rows})


@admin_bp.route('/dramas', methods=['POST'])
@require_admin
def add_drama():
    """新增或更新一部剧（按标题 upsert）"""
    data = request.get_json(silent=True) or request.form
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'code': 400, 'msg': '缺少剧名'}), 400

    air_date = (data.get('air_date') or '').strip() or date.today().isoformat()
    poster_url = (data.get('poster_url') or '').strip() or None
    drama_type = (data.get('type') or 'tv_drama').strip()
    synopsis = (data.get('synopsis') or '').strip() or None

    # 收集各平台输入（支持 URL 或裸 ID）
    platform_inputs = {
        'tencent': (data.get('tencent') or '').strip(),
        'iqiyi':   (data.get('iqiyi')   or '').strip(),
        'youku':   (data.get('youku')   or '').strip(),
        'mgtv':    (data.get('mgtv')    or '').strip(),
    }

    parsed, errors = parse_multi(platform_inputs)
    if not parsed:
        return jsonify({'code': 400,
                        'msg': '至少需要一个平台的有效 URL/ID',
                        'errors': errors}), 400

    # 查/建 drama
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

    # 查询平台 ID 映射
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
                 'linked': linked, 'warnings': errors}
    })


@admin_bp.route('/dramas/<int:drama_id>/delete', methods=['POST'])
@require_admin
def delete_drama(drama_id):
    """下架：把剧标记为 finished（不删数据）"""
    execute("UPDATE dramas SET status='finished' WHERE id=%s", (drama_id,))
    return jsonify({'code': 0, 'msg': '已下架'})


@admin_bp.route('/dramas/<int:drama_id>/reair', methods=['POST'])
@require_admin
def reair_drama(drama_id):
    """重新上架"""
    execute("UPDATE dramas SET status='airing' WHERE id=%s", (drama_id,))
    return jsonify({'code': 0, 'msg': '已上架'})


@admin_bp.route('/test_extract', methods=['POST'])
@require_admin
def test_extract():
    """测试：对给定 URL 或 ID 立即启动 Playwright 提取一次热度（不入库）"""
    data = request.get_json(silent=True) or request.form
    platform = normalize_platform(data.get('platform'))
    raw = (data.get('url') or '').strip()

    if not platform or not raw:
        return jsonify({'code': 400, 'msg': '缺少 platform 或 url'}), 400

    drama_id, url = parse_platform_input(platform, raw)
    if not url:
        return jsonify({'code': 400, 'msg': f'无法从输入中解析出 {platform} 的 ID'}), 400

    from crawlers.browser_helper import BrowserHelper
    from crawlers.airing_crawler import AiringCrawler

    crawler = AiringCrawler()
    extractor_name = crawler.PLATFORM_EXTRACTORS.get(platform)
    if not extractor_name:
        return jsonify({'code': 400, 'msg': f'{platform} 不支持热度提取'}), 400

    try:
        with BrowserHelper(headless=True) as browser:
            extractor = getattr(crawler, extractor_name)
            value = extractor(browser, url)
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'提取异常: {e}'}), 500

    return jsonify({
        'code': 0,
        'msg': '提取完成' if value else '未提取到数值（平台页面可能改版或有反爬）',
        'data': {
            'platform': platform,
            'url': url,
            'platform_drama_id': drama_id,
            'value': value,
        }
    })


# ================================================================
# 管理面板 HTML
# ================================================================

ADMIN_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>热剧榜 · 管理后台</title>
<style>
  * { box-sizing: border-box; }
  body { font: 14px/1.5 -apple-system,"Segoe UI",Roboto,sans-serif;
         background: linear-gradient(135deg,#667eea 0%,#764ba2 100%);
         margin: 0; padding: 0; min-height: 100vh; color: #333; }
  .wrap { max-width: 960px; margin: 0 auto; padding: 30px 20px; }
  h1 { color: #fff; text-shadow: 0 2px 10px rgba(0,0,0,.2); font-size: 28px; margin: 0 0 6px; }
  .sub { color: rgba(255,255,255,.9); margin: 0 0 24px; }
  .card { background: #fff; border-radius: 14px; padding: 24px; margin-bottom: 20px;
          box-shadow: 0 4px 20px rgba(0,0,0,.08); }
  .card h2 { margin: 0 0 16px; font-size: 18px; color: #333; }
  label { display: block; margin: 10px 0 4px; font-weight: 600; color: #555; font-size: 13px; }
  input, textarea, select {
    width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px;
    font-size: 14px; font-family: inherit; transition: border-color .2s;
  }
  input:focus, textarea:focus { outline: none; border-color: #667eea; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 600px) { .row { grid-template-columns: 1fr; } }
  button { background: #667eea; color: #fff; border: 0; padding: 10px 20px;
           border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600;
           transition: background .2s; }
  button:hover { background: #5a6fd6; }
  button.secondary { background: #6c757d; }
  button.danger { background: #e74c3c; }
  button.small { padding: 6px 12px; font-size: 12px; }
  .hint { color: #888; font-size: 12px; margin-top: 4px; }
  .result { margin-top: 16px; padding: 12px; border-radius: 8px; white-space: pre-wrap;
            font-family: Menlo,Consolas,monospace; font-size: 13px; }
  .ok { background: #d4edda; color: #155724; }
  .err { background: #f8d7da; color: #721c24; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
  th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid #eee; }
  th { background: #f8f9fa; font-weight: 600; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
           font-size: 11px; margin-right: 4px; color: #fff; }
  .p-tencent { background: #12b7f5; }
  .p-iqiyi { background: #00a862; }
  .p-youku { background: #ff6600; }
  .p-mgtv { background: #ff5f00; }
  #loginCard { max-width: 420px; margin: 60px auto; }
</style>
</head>
<body>
<div class="wrap">

<div id="loginView" style="display:none">
  <h1>热剧榜 · 管理后台</h1>
  <p class="sub">请输入 ADMIN_TOKEN 登录（.env 中配置）</p>
  <div class="card" id="loginCard">
    <label>Admin Token</label>
    <input type="password" id="tokenInput" placeholder="粘贴 .env 中的 ADMIN_TOKEN">
    <div style="margin-top:16px"><button onclick="doLogin()">登录</button></div>
    <div id="loginResult"></div>
  </div>
</div>

<div id="mainView" style="display:none">
  <h1>热剧榜 · 管理后台</h1>
  <p class="sub">
    录入后 15 分钟内爬虫自动采集；立刻提交请 <code>systemctl restart rejubang-crawler</code>
    <span style="float:right"><button class="secondary small" onclick="doLogout()">退出</button></span>
  </p>

  <div class="card">
    <h2>➕ 新增 / 更新剧集</h2>
    <label>剧名 <span style="color:#e74c3c">*</span></label>
    <input id="title" placeholder="例：蜜语纪">

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

    <label>海报图 URL（可选，留空爬虫会按需补充）</label>
    <input id="poster_url" placeholder="https://...">

    <hr style="margin:20px 0; border:none; border-top:1px solid #eee;">
    <p style="color:#666; margin:0 0 10px;">
      <strong>各平台链接</strong>（至少填 1 个，支持整条详情页 URL 或裸 ID）
    </p>

    <label>腾讯视频</label>
    <input id="tencent" placeholder="https://v.qq.com/x/cover/mzc002006dzzunf.html  或  mzc002006dzzunf">

    <label>爱奇艺</label>
    <input id="iqiyi" placeholder="https://www.iqiyi.com/v_pz64qf5dtk.html  或  v_pz64qf5dtk">

    <label>优酷</label>
    <input id="youku" placeholder="https://v.youku.com/v_show/id_xxxxxxx.html">

    <label>芒果TV</label>
    <input id="mgtv" placeholder="https://www.mgtv.com/b/742534/25318094.html">

    <label>剧情简介（可选）</label>
    <textarea id="synopsis" rows="3"></textarea>

    <div style="margin-top:16px">
      <button onclick="submitDrama()">保存录入</button>
      <button class="secondary" onclick="testExtract()">先测试热度提取</button>
    </div>
    <div id="submitResult"></div>
  </div>

  <div class="card">
    <h2>📋 当前在播剧清单 <button class="small secondary" onclick="loadList()">刷新</button></h2>
    <div id="dramaList">加载中…</div>
  </div>
</div>

</div>

<script>
const API = '/api/v1/admin';

function toast(el, msg, ok) {
  el.innerHTML = '<div class="result '+(ok?'ok':'err')+'">'+msg+'</div>';
}

async function doLogin() {
  const token = document.getElementById('tokenInput').value.trim();
  const res = await fetch(API+'/login', {
    method:'POST', credentials:'same-origin',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({token})
  });
  const d = await res.json();
  if (res.ok && d.code === 0) {
    showMain();
  } else {
    toast(document.getElementById('loginResult'), d.msg || '登录失败', false);
  }
}

async function doLogout() {
  await fetch(API+'/logout', {method:'POST', credentials:'same-origin'});
  location.reload();
}

async function submitDrama() {
  const payload = {};
  ['title','air_date','type','poster_url','tencent','iqiyi','youku','mgtv','synopsis']
    .forEach(k => { payload[k] = document.getElementById(k).value.trim(); });

  if (!payload.title) {
    toast(document.getElementById('submitResult'), '剧名不能为空', false);
    return;
  }
  if (!payload.tencent && !payload.iqiyi && !payload.youku && !payload.mgtv) {
    toast(document.getElementById('submitResult'), '至少填一个平台的 URL/ID', false);
    return;
  }

  const res = await fetch(API+'/dramas', {
    method:'POST', credentials:'same-origin',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  const d = await res.json();
  if (d.code === 0) {
    let html = '✓ 已保存，drama_id=' + d.data.drama_id + '\n';
    (d.data.linked||[]).forEach(l => {
      html += '  [' + l.platform + '] ' + l.id + ' → ' + l.url + '\n';
    });
    if (d.data.warnings && d.data.warnings.length) {
      html += '\n⚠ 以下输入被忽略：\n' + d.data.warnings.join('\n');
    }
    toast(document.getElementById('submitResult'), html, true);
    loadList();
    // 清空表单（保留日期）
    ['title','poster_url','tencent','iqiyi','youku','mgtv','synopsis']
      .forEach(k => document.getElementById(k).value = '');
  } else {
    toast(document.getElementById('submitResult'),
          '✗ ' + (d.msg || '保存失败') +
          (d.errors ? '\n' + d.errors.join('\n') : ''), false);
  }
}

async function testExtract() {
  const platforms = ['tencent','iqiyi','youku','mgtv'];
  const out = [];
  for (const p of platforms) {
    const v = document.getElementById(p).value.trim();
    if (!v) continue;
    out.push('正在测试 '+p+' …');
    document.getElementById('submitResult').innerHTML =
      '<div class="result ok">' + out.join('\n') + '</div>';
    try {
      const res = await fetch(API+'/test_extract', {
        method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({platform: p, url: v})
      });
      const d = await res.json();
      if (d.code === 0 && d.data.value > 0) {
        out[out.length-1] = '✓ '+p+' 热度/播放量 = '+d.data.value+'  (URL: '+d.data.url+')';
      } else {
        out[out.length-1] = '✗ '+p+' 未提取到数值  msg='+(d.msg||'?');
      }
    } catch (e) {
      out[out.length-1] = '✗ '+p+' 异常: '+e;
    }
    document.getElementById('submitResult').innerHTML =
      '<div class="result ok">' + out.join('\n') + '</div>';
  }
}

async function loadList() {
  document.getElementById('dramaList').innerText = '加载中…';
  const res = await fetch(API+'/dramas', {credentials:'same-origin'});
  const d = await res.json();
  if (d.code !== 0) {
    document.getElementById('dramaList').innerHTML =
      '<div class="result err">加载失败: '+(d.msg||'?')+'</div>';
    return;
  }
  if (!d.data.length) {
    document.getElementById('dramaList').innerHTML =
      '<p style="color:#888">尚无数据。在上方表单录入第一部剧试试。</p>';
    return;
  }
  let html = '<table><tr><th>剧名</th><th>状态</th><th>开播</th><th>平台</th><th>最近采集</th><th>操作</th></tr>';
  d.data.forEach(r => {
    const plats = (r.platforms||'').split(',').filter(Boolean)
      .map(p => '<span class="badge p-'+p+'">'+p+'</span>').join('');
    html += '<tr>'+
      '<td><strong>'+(r.title||'?')+'</strong></td>'+
      '<td>'+(r.status||'?')+'</td>'+
      '<td>'+(r.air_date||'-')+'</td>'+
      '<td>'+(plats||'-')+'</td>'+
      '<td>'+(r.last_crawl||'<span style="color:#aaa">未采</span>')+'</td>'+
      '<td>'+
        (r.status === 'airing'
          ? '<button class="small danger" onclick="setStatus('+r.id+",'delete')\">下架</button>"
          : '<button class="small" onclick="setStatus('+r.id+",'reair')\">上架</button>")+
      '</td></tr>';
  });
  html += '</table>';
  document.getElementById('dramaList').innerHTML = html;
}

async function setStatus(id, action) {
  await fetch(API+'/dramas/'+id+'/'+action, {method:'POST', credentials:'same-origin'});
  loadList();
}

async function checkAuth() {
  const res = await fetch(API+'/dramas', {credentials:'same-origin'});
  return res.ok;
}

function showMain() {
  document.getElementById('loginView').style.display = 'none';
  document.getElementById('mainView').style.display = 'block';
  // 默认日期=今天
  document.getElementById('air_date').value = new Date().toISOString().split('T')[0];
  loadList();
}

(async function init() {
  if (await checkAuth()) showMain();
  else document.getElementById('loginView').style.display = 'block';
})();
</script>
</body>
</html>
"""


@admin_bp.route('', methods=['GET'])
@admin_bp.route('/', methods=['GET'])
def admin_page():
    return ADMIN_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}
