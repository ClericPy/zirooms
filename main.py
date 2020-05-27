# -*- coding: utf-8 -*-

import os
import re
from tkinter.messagebox import showerror

from bs4 import BeautifulSoup
from torequests import Async, threads, tPool
from torequests.utils import Counts, Saver, countdown, find_one, md5, ttime


def refresh_proxy():
    req = tPool()
    r = req.get(
        'https://ip.ihuan.me/today.html',
        retry=2,
        timeout=3,
        headers={
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "Dnt": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cookie": ""
        })
    detail = 'https://ip.ihuan.me/today/%s' % find_one('href="/today/([^"]+)"',
                                                       r.text)[1]
    detail_text = req.get(
        detail,
        retry=2,
        timeout=3,
        headers={
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "Dnt": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cookie": ""
        }).text
    ips = re.findall(r'\d+\.\d+\.\d+\.\d+:\d+', detail_text)
    print(len(ips), 'ips')
    local_text = req.get('http://myip.ipip.net/', retry=1, timeout=3).text
    for PROXY in ips:
        print('代理测试:', PROXY)
        proxy_r = req.get('http://myip.ipip.net/',
                          timeout=1,
                          proxies={
                              'http': PROXY,
                              'https': PROXY
                          }).x
        if not proxy_r or proxy_r.text == local_text:
            print(f'{PROXY} 代理错误, 更换代理地址. {proxy_r}: {proxy_r.text}')
            continue
        else:
            break
    else:
        print('代理获取全部失败, 程序崩溃')
        os._exit(1)
    print('代理地址 OK, 开始抓取')
    kwargs['proxies'] = {'http': PROXY, 'https': PROXY}
    return PROXY


IPS = '''https://ip.ihuan.me/address/5YyX5Lqs.html'''
CHECK_INTERVAL = 180
MAX_DISTANCE = 1200

req = tPool()
kwargs = {
    'headers': {
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
        "Dnt": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": ""
    },
    'retry': 2,
    'proxies': {
        'http': None,
        'https': None
    },
    'timeout': 3
}
keys = 'room_id, title, rooms, location, distance, price, area, target, floor, max_floor, other_rooms, girls, score, time, status, tags, url'.split(
    ', ')
cc = Counts()
total_rooms_count = 0
ss = Saver('./data.json')
if not ss.rooms:
    ss.rooms = {}


def new_line_item(title, url):
    item = {
        "room_id": f'-{md5(url, 10)}',
        "url": url,
        "title": title,
        "area": '-',
        "floor": '-',
        "max_floor": '-',
        "distance": '-',
        "location": "-",
        "status": "-",
        "rooms": '-',
        "other_rooms": "-",
        "target": "-",
        "girls": '-',
        "score": '-',
        "price": "-",
        "time": "-",
        "tags": "-"
    }
    return item


def fetch_list(url, with_new_line=False):
    scode = ''
    result = {'items': []}
    for _ in range(5):
        if 'class="Z_list-box"' in scode and 'id="page"' in scode:
            break
        elif 'Z_list-empty' in scode:
            return result
        r = req.get(url, **kwargs)
        scode = r.text
    else:
        print(scode)
        print('程序崩溃, fetch_list 重试次数过多', url)
        raise RequestErrorForRetry()
    html = BeautifulSoup(scode, features='html.parser')
    # print(scode)
    title = html.select_one('title').text
    page = html.select_one('#page>a.active')
    page = page.text if page else '1'
    total_page = find_one(r'<span>(共\d+页)</span>', scode)[1] or '共1页'
    print(f'采集第 {page} 页 ({total_page}) {title}')
    if total_page != '共1页':
        page1_link = html.select_one('#page>a:nth-of-type(1)')
        if page1_link:
            href = page1_link.get('href')
            if href:
                if href.startswith('//'):
                    href = f'http:{href}'
                if '-p1/' in href:
                    template = re.sub(r'-p1/(\?|$)', '-p{}/\\1', href)
                    max_page = int(find_one(r'\d+', total_page)[0])
                    result['next_pages'] = [
                        template.format(page)
                        for page in range(2, max_page + 1)
                    ]
    items = html.select('.Z_list>.Z_list-box>.item')
    for i in items:
        a = i.select_one('h5.title>a')
        location = i.select_one('.location')
        if a and location:
            href = a.get('href')
            if href:
                if href.startswith('//'):
                    href = f'http:{href}'
                location, distance = re.findall(r'距(.*?)站步行约(\d+)米',
                                                str(location))[0]
                desc = i.select_one('.desc>div')
                title = a.text.strip().replace('自如友家·', '')
                area, floor, max_floor = re.findall(
                    r'([\.0-9]+)㎡ \| (\d+)/(\d+)层', desc.text)[0]
                tag = i.select_one('.info-box>h5').get('class')[-1]
                result['items'].append({
                    'room_id': find_one(r'/x/(\d+)\.html', href)[1],
                    'url': href,
                    'title': title,
                    'area': float(area),
                    'floor': int(floor),
                    'max_floor': int(max_floor),
                    'distance': int(distance),
                    'location': location,
                    'status': tag,
                    'referer': url,
                })
    print(f'采集到 {len(items)} 个房间, 在第 {page} 页 {title}')
    if with_new_line:
        # 加个间隔行
        query = html.select_one('#Z_search_input').get('value') or ''
        filters = [i.text.strip() for i in html.select('.f-res>.ct>a')]
        title = f'- {query}{": " if query else ""}{", ".join(filters)}'
        result['items'].insert(0, new_line_item(title, url))
    return result


def get_score(item):
    score = 0
    target_score = ['朝南', '朝东南', '朝东', '朝西南', '朝北', '朝东北', '朝西北', '朝西']
    # 朝向加分
    if item['target'] in target_score:
        score += (10 - target_score.index(item['target'])) / 10
    else:
        score += 0
    # 独立卫生间 + 1, 独立阳台 * 1.1
    if '独立卫生间' in item.get('tags', ''):
        score += 1
    if '独立阳台' in item.get('tags', ''):
        score *= 1.1
    # 女生数量减分, 每多一个, 减 0.5 分
    score -= 0.5 * item['girls']
    # 地铁距离分数, 越近分数越高
    score += (1000 - item['distance']) / 1000
    # 楼层分数, 越高越好, 但是顶楼和 1 楼则分数打 1 折
    if item['floor'] == item['max_floor'] or item['floor'] == 1:
        score -= 1
    else:
        floor = item['floor']
        # 2 - 5, 6 - 9, 10+ 分三档
        if 2 <= floor <= 4:
            # 蚊子有点多, 也就比 1 楼好一丁点
            # 所以 2 3 4 分三个档
            score -= [0.7, 0.6, 0.5][floor - 2]
        elif 5 <= floor <= 7:
            # 蚊子少了点, 5 6 7 也是三个档, 但相对来说问题不算太大
            score -= [0.3, 0.2, 0.1][floor - 5]
        else:
            # 蚊子在 8 楼以上就很少了, 越高分越高吧, 但不要超过 1 分
            score += min(((floor - 8) / 10, 1))
    # 面积越大越好, 最小算 6 平的话, 每比 6 平多一平, 分数上升 0.2
    score += (item['area'] - 6) / 5
    # 房间数影响很大, 所以二居室比三居室提升巨大, 所以直接按比例来搞
    # 一般都是三居室, 所以用 3 除以房间数
    score *= 3 / item['rooms']
    # 有可能遇到签约时间不到一年的, 打八折
    if '可签约至' in item['status']:
        score *= 0.8
    return round(score, 2)


def get_string(item):
    string = '\t'.join([str(item[i]) for i in keys])
    return string


@threads(3)
def fetch_detail(item):
    if not item['room_id'].isdigit():
        return item
    if item['room_id'] in ss.rooms:
        exist_item = ss.rooms[item['room_id']]
        if 'tags' in exist_item and 'string' not in exist_item and '√' in exist_item.get(
                'status', '') and 'release' not in exist_item.get('status', ''):
            # 已经抓过 tags, string 作为过期字段已经被清理掉, 可签约, 不是待释放
            item.update(exist_item)
            return item
        else:
            item['time'] = exist_item.get('time') or ttime()
    print(cc.x,
          '/',
          total_rooms_count,
          '采集房间',
          item.get('title', ''),
          item['url'],
          flush=1)
    scode = ''
    for _ in range(5):
        if 'Z_name' in scode:
            break
        r = req.get(item['url'], **kwargs)
        scode = r.text
    else:
        print(scode)
        print('程序崩溃, fetch_detail 重试次数过多', item['url'])
        raise RequestErrorForRetry()

    html = BeautifulSoup(scode, features='html.parser')
    item['title'] = html.select_one('h1.Z_name').text.replace('自如友家·', '')
    neighbors = html.select('#meetinfo ul.rent_list>li')
    item['rooms'] = len(neighbors) + 1
    genders = {'女', '男'}
    other_rooms = ''
    for n in neighbors:
        gender = n.select_one('.info>.mt10>span').text.strip()
        if gender in genders:
            other_rooms += gender
        else:
            other_rooms += '空'
    item['other_rooms'] = other_rooms
    duration = '未知时长'
    for i in html.select('#live-tempbox .jiance>li'):
        if '签约时长' in i.text:
            tag = i.select_one('.info_value')
            if tag:
                duration = tag.text
            break
    # 空气检测
    air = '空气检测结果未知'
    for i in html.select('#areacheck .jiance>li'):
        if '检测日期' in i.text:
            tag = i.select_one('.info_value')
            if tag:
                air = '检测日期: %s' % tag.text
            break
        elif '空置时长' in i.text:
            tag = i.select_one('.info_value')
            if tag:
                air = '空置时长: %s' % tag.text
            break
    ok = '-'
    if not ('√' in item['status'] or 'X' in item['status']):
        ok = bool(html.select_one('[class="Z_prelook active"]'))
    item['status'] = f'{"√" if ok else "X"}: {item["status"]}({duration}|{air})'
    item['target'] = html.select_one(
        '.Z_home_info>.Z_home_b>dl:nth-of-type(2)>dd').text
    tags = [i.text for i in html.select('.Z_tags>.tag')]
    tags = ", ".join(tags)
    item['tags'] = tags or '-'
    item['girls'] = item['other_rooms'].count('女')
    item['score'] = get_score(item)
    item['price'] = '-'
    item['time'] = item.get('time') or ttime()
    print(get_string(item), flush=1)
    return item


def fetch_rooms(url):
    rooms = []
    result = fetch_list(url, with_new_line=True)
    items = result.get('items')
    if items:
        rooms.extend(items)
    next_pages = result.get('next_pages')
    if next_pages:
        print('loading next_pages:', next_pages)
        async_fetch_list = Async(fetch_list, 3)
        tasks = [async_fetch_list(new_url) for new_url in next_pages]
        for task in tasks:
            tmp_result = task.x
            if not tmp_result and isinstance(tmp_result.error, RequestErrorForRetry):
                raise tmp_result.error
            items = tmp_result.get('items') or []
            rooms.extend(items)
    return rooms


def alert():
    import winsound
    for _ in range(3):
        winsound.Beep(900, 300)
    import os
    os.system(r'explorer.exe .')


def main():
    global total_rooms_count
    rooms = []
    SEARCH_URLS = []
    with open('list_urls.txt', encoding='u8') as f:
        for line in f:
            if line.startswith('http'):
                SEARCH_URLS.append(line.strip())
    if not SEARCH_URLS:
        print('需要先在 list_urls.txt 文件里按行放入自如搜索页的 URL')
        os._exit(1)
    for url in SEARCH_URLS:
        rooms += fetch_rooms(url)
        # print(rooms)
    new_room_keys = {i['room_id'] for i in rooms}
    # 把之前有, 新搜索结果没有的补进去重新抓取一次
    old_rooms = ss.rooms
    old_keys = set(old_rooms.keys())
    refresh_keys = old_keys - new_room_keys
    for key in refresh_keys:
        room = old_rooms.pop(key)
        referer = room.get('referer')
        if referer and referer in SEARCH_URLS:
            rooms.append(room)
        else:
            print('忽略错误 referer 的房间:', room)
    ss.rooms = old_rooms
    rooms = [
        i for i in rooms
        if i['distance'] == '-' or i['distance'] <= MAX_DISTANCE
    ]
    total_rooms_count = len(rooms)
    tasks = [fetch_detail(room) for room in rooms]
    rooms = [i.x for i in tasks]
    for i in rooms:
        if not i:
            raise i.error
    # 不做去重, 因为是那个搜索结果页里的
    print('\n'.join([get_string(i) for i in rooms]),
          file=open('data.txt', 'w', encoding='u8'))
    # 旧 room 里有, 新 room 里没有的话, 说明被删了
    new_rooms = {room['room_id']: room for room in rooms}
    has_new_room = new_rooms.keys() - old_keys
    ss.rooms = new_rooms
    if has_new_room:
        print('新房间', has_new_room)
        alert()
    else:
        print('没有新房间')


class RequestErrorForRetry(Exception):
    pass


def loop():
    try:
        refresh_proxy()
        while 1:
            try:
                main()
                countdown(CHECK_INTERVAL)
            except RequestErrorForRetry:
                print('更换代理重试')
                refresh_proxy()
    except Exception:
        import traceback
        traceback.print_exc()
        showerror('Error', traceback.format_exc())


if __name__ == "__main__":
    loop()
