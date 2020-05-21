# -*- coding: utf-8 -*-

import re

from bs4 import BeautifulSoup
from torequests import threads, tPool
from torequests.utils import Counts, Saver, countdown, find_one, ttime
'''
https://ip.ihuan.me/address/5YyX5Lqs.html
PROXY = '111.202.247.50:8080'
PROXY = '218.60.8.99:3129'
'''


def check_proxy():
    req = tPool()
    local_text = req.get('http://myip.ipip.net/', retry=1, timeout=3).text
    proxy_r = req.get('http://myip.ipip.net/',
                      retry=1,
                      timeout=3,
                      proxies={
                          'http': PROXY,
                          'https': PROXY
                      }).x
    if not proxy_r or proxy_r.text == local_text:
        print(f'{PROXY} 代理故障, 请更换代理地址. {proxy_r}: {proxy_r.text}')
        quit()
    print('代理地址 OK, 开始抓取')


CHECK_INTERVAL = 300
PROXY = '116.196.85.150:3128'
MAX_DISTANCE = 1000
check_proxy()
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
    'retry': 3,
    'proxies': {
        'http': PROXY,
        'https': PROXY
    },
    'timeout': 3
}
keys = 'room_id, title, location, distance, price, area, rooms, floor, max_floor, target, other_rooms, girls, score, time, status, url'.split(
    ', ')
cc = Counts()
total_rooms_count = 0
ss = Saver('./data.json')
if not ss.rooms:
    ss.rooms = {}


def fetch_list(url):
    scode = ''
    for _ in range(5):
        if '已为您找到符合条件' in scode and 'page' in scode:
            break
        r = req.get(url, **kwargs)
        scode = r.text
    else:
        print(scode)
        print('程序崩溃, fetch_list 重试次数过多')
        quit()
    result = {'items': []}
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
                    'url': href,
                    'title': title,
                    'area': float(area),
                    'floor': int(floor),
                    'max_floor': int(max_floor),
                    'distance': int(distance),
                    'location': location,
                    'status': tag,
                })
    print(f'采集到 {len(items)} 个房间, 在第 {page} 页 {title}')
    return result


def get_score(item):
    score = 0
    target_score = ['朝南', '朝东南', '朝东', '朝西南', '朝北', '朝东北', '朝西北', '朝西']
    # 朝向加分
    if item['target'] in target_score:
        score += (10 - target_score.index(item['target'])) / 10
    else:
        score += 0
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
    return round(score, 2)


@threads(3)
def fetch_detail(item):
    item['room_id'] = find_one(r'/x/(\d+)\.html', item['url'])[1]
    if item['room_id'] in ss.rooms:
        item.update(ss.rooms[item['room_id']])
        return item
    print(cc.x,
          '/',
          total_rooms_count,
          '采集房间',
          item['title'],
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
        print('程序崩溃, fetch_detail 重试次数过多')
        quit()
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
    item['status'] = '可预约:' + item['status'] if html.select_one(
        '[class="Z_prelook active"]') else '不可预约:' + item['status']
    item['target'] = html.select_one(
        '.Z_home_info>.Z_home_b>dl:nth-of-type(2)>dd').text
    item['girls'] = item['other_rooms'].count('女')
    item['score'] = get_score(item)
    item['price'] = '-'
    item['time'] = ttime()
    string = '\t'.join([str(item[i]) for i in keys])
    print(string, flush=1)
    item['string'] = string
    return item


def fetch_rooms(url):
    rooms = []
    result = fetch_list(url)
    items = result.get('items')
    if items:
        rooms.extend(items)
    next_pages = result.get('next_pages')
    if next_pages:
        print('loading next_pages:', next_pages)
        for new_url in next_pages:
            result = fetch_list(new_url)
            items = result.get('items') or []
            rooms.extend(items)
    return rooms


def alert():
    import os
    os.system(r'explorer.exe .')
    import winsound
    for _ in range(5):
        winsound.Beep(900, 300)


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
        quit()
    for url in SEARCH_URLS:
        rooms += fetch_rooms(url)
        # print(rooms)
    rooms = [i for i in rooms if i['distance'] <= MAX_DISTANCE]
    total_rooms_count = len(rooms)
    tasks = [fetch_detail(room) for room in rooms]
    rooms = [i.x for i in tasks]
    result = [room['string'] if room else room.text for room in rooms]
    print('\n'.join(result), file=open('data.txt', 'w', encoding='u8'))
    # 旧 room 里有, 新 room 里没有的话, 说明被删了, 清理掉
    # 每次存储只存新的
    new_rooms = {room['room_id']: room for room in rooms}
    has_new_room = new_rooms.keys() - ss.rooms.keys()
    room_changed = ss.rooms.keys() - new_rooms.keys()
    if room_changed:
        print('=' * 50)
        print('房间发生变化')
        for key in room_changed:
            print(ss.rooms[key])
        print('=' * 50)
        alert()
    ss.rooms = new_rooms
    if has_new_room:
        print('新房间')
        alert()
    else:
        print('没有新房间')


def loop():
    while 1:
        main()
        countdown(CHECK_INTERVAL)


if __name__ == "__main__":
    loop()
