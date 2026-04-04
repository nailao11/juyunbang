#!/usr/bin/env python3
"""调试腾讯视频pbaccess API的实际返回数据结构"""
import requests, json

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/json',
    'Referer': 'https://v.qq.com/',
    'Origin': 'https://v.qq.com',
})

body = {
    'page_context': {'page_index': '0'},
    'page_params': {
        'page_id': 'channel_list_second_page',
        'page_type': 'operation',
        'channel_id': '100113',
        'filter_params': 'sort=75',
        'page': '0',
    },
    'page_bypass_params': {
        'params': {'page_size': '30', 'page_num': '0', 'caller_id': '3000010', 'platform_id': '2'},
        'global_params': {'ckey': '', 'vuession': ''},
    },
}

resp = session.post(
    'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage',
    json=body, timeout=15
)
data = resp.json()

print("=== 顶层key ===")
print(list(data.keys()))
print("\n=== data key ===")
print(list(data.get('data', {}).keys()))

card_list = data.get('data', {}).get('CardList', []) or data.get('data', {}).get('card_list', []) or []
print(f"\n=== CardList数量: {len(card_list)} ===")

for ci, card in enumerate(card_list[:3]):
    print(f"\n--- Card {ci} key: {list(card.keys())[:10]}")

    # 尝试找children
    for path_name, children in [
        ('children_list.list.cards', card.get('children_list', {}).get('list', {}).get('cards', [])),
        ('card.card_data.cards', card.get('card', {}).get('card_data', {}).get('cards', [])),
        ('children_list.list.items', card.get('children_list', {}).get('list', {}).get('items', [])),
    ]:
        if children:
            print(f"    路径: {path_name}, 数量: {len(children)}")
            # 打印第一个children的完整结构
            if children:
                first = children[0]
                print(f"    第1个child key: {list(first.keys())}")
                # 打印params
                if 'params' in first:
                    p = first['params']
                    print(f"    params key: {sorted(p.keys())}")
                    # 打印所有params值
                    for k, v in sorted(p.items()):
                        v_str = str(v)[:80]
                        print(f"      {k} = {v_str}")
                # 打印其他顶层字段
                for k, v in first.items():
                    if k != 'params':
                        v_str = str(v)[:100]
                        print(f"    {k} = {v_str}")
            # 打印前3个的title
            print(f"\n    前5条:")
            for i, child in enumerate(children[:5]):
                p = child.get('params', {})
                # 尝试所有可能的title字段
                title = (p.get('title') or p.get('show_title') or p.get('uni_title')
                         or p.get('second_title') or child.get('title') or '???')
                heat = (p.get('hot_value') or p.get('hotval') or p.get('score')
                        or p.get('play_count') or '?')
                cover = (p.get('new_pic_hz') or p.get('image_url') or p.get('pic')
                         or p.get('pic_160x90') or p.get('pic_hz') or '无')
                print(f"      [{i+1}] {title} | 热度={heat} | 封面={cover[:60] if cover else '无'}")

print("\n\n=== bu/pagesheet/list HTML结构 ===")
resp2 = session.get('https://v.qq.com/x/bu/pagesheet/list', params={
    '_all': '1', 'append': '1', 'channel': 'tv',
    'listpage': '2', 'offset': '0', 'pagesize': '10', 'sort': '75'
}, headers={'Referer': 'https://v.qq.com/channel/tv', 'Accept': 'text/html'}, timeout=15)

import re
# 提取list_item中的标题和链接
items = re.findall(r'<a[^>]*href="(https://v\.qq\.com/x/cover/[^"]*)"[^>]*title="([^"]*)"', resp2.text)
print(f"从HTML中提取到 {len(items)} 条:")
for i, (url, title) in enumerate(items[:10]):
    print(f"  [{i+1}] {title} | {url}")

# 提取图片
imgs = re.findall(r'<img[^>]*src="([^"]*)"[^>]*>', resp2.text)
print(f"\n图片URL数量: {len(imgs)}")
if imgs:
    print(f"  示例: {imgs[0][:80]}")
