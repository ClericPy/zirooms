#! python3
import json
import re
import time
import traceback
from collections import namedtuple

from lxml.html import fromstring
from torequests.dummy import Requests as tPool
from torequests.main import tPool
from torequests.utils import UA, Counts, Saver, ttime, unique

# 121.8.98.197:80
# 121.58.17.52:80
# 61.136.163.246:3128
# 61.136.163.246:8103
# 61.136.163.245:3128
# 119.254.11.50:80
# 123.57.76.102:80
# 120.92.88.202:10000
# 140.205.222.3:80
# 61.136.163.245:8103
# 119.28.138.104:3128
# 113.214.13.1:8000
# 178.62.117.231:3128
# 101.37.79.125:3128
PROXY = None
# rid, name, url, price, floor, room, area, orient, female, subway, station, distance, neighbor, create_time, uptime
req = tPool()
total = 0
counter = Counts()
next_pages = []
interval = 300


def list_cb(r):
    result = []
    if not r.x:
        return result
    scode = r.text
    if not scode or 'class="nomsg area"' in scode:
        print(counter.x, '/', total, r.url_string)
        return result
    rooms = fromstring(scode).cssselect('#houseList > li')
    if not rooms:
        return result
    next_page = [
        re.sub('^//', 'http://', i.get('href'))
        for i in fromstring(scode).cssselect('#page>a:not([class])')
    ]
    if next_page:
        next_pages.extend(next_page)
    for i in rooms:
        url = re.sub('^//', 'http://', i.cssselect('.t1')[0].get('href'))
        subway_info = i.cssselect('.detail > p:nth-child(2) > span')[0].text
        subway_info = re.search(r'(\d+)号线(.*?)站(\d+)米', subway_info)
        subway = subway_info.group(1)
        station = subway_info.group(2)
        distance = subway_info.group(3)
        rid = re.search(r'/(\d+)\.html', url).group(1)
        meta = dict(url=url,
                    subway=subway,
                    station=station,
                    distance=distance,
                    rid=rid)
        result.append(meta)
    print(counter.x, '/', total, r.url_string, len(result))
    return result


def fetch_list(urls):
    result = []
    for _ in range(2):
        global total
        counter.current = counter.start
        total = len(urls)
        tasks = [
            req.get(url,
                    callback=list_cb,
                    retry=8,
                    timeout=5,
                    proxies={'http': PROXY},
                    headers={'User-agent': UA.Chrome}) for url in urls
        ]
        req.x
        task_result = [i.cx for i in tasks if i.x]
        detail_urls = sum(task_result, [])
        result.extend(detail_urls)
        if next_pages:
            urls = next_pages
        else:
            break
    next_pages.clear()
    return result


def detail_cb(r):
    try:
        meta = {}
        if not r.x:
            print(counter.x, '/', total, r.x.error)
            return meta
        r = r.x
        scode = r.text
        if not scode or 'class="nopage-pic"' in scode:
            print(counter.x, '/', total, 'nopage-pic')
            return meta
        tree = fromstring(scode)
        if not tree.cssselect('.room_name>h2'):
            print(r.url_string)
        try:
            button = tree.cssselect('#zreserve')[0].text_content().strip()
        except:
            traceback.print_exc()
            button = 'error'
        if button in ('已下定', '已出租'):
            print(counter.x, '/', total, button)
            return meta
        name = tree.cssselect('.room_name>h2')[0].text.strip().replace(',', ' ')
        price = re.sub('\D', '', tree.cssselect('#room_price')[0].text)
        if len(price) < 4:
            # price = str(int(price) * 365 // 12)
            return meta
        room_info = tree.cssselect('.detail_room')[0].text_content()
        area = re.search('([\d\.]+)\s*㎡', room_info).group(1)
        rooms = re.search('户型.\s*(\d+)\s*室', room_info).group(1)
        floor, max_floor = re.search('楼层.\s*([\d\w/]+)\s*层',
                                     room_info).group(1).split('/')
        floor = re.search('(\d+)', floor).group(1)
        orient = re.search('朝向.\s*(\S+)', room_info).group(1)
        neighbor = (''.join(
            (i.get('class').strip() or 'X'
             for i in tree.cssselect('.greatRoommate>ul>li')))).replace(
                 'current',
                 '空').replace('woman',
                              '女').replace('man',
                                           '男').replace('last',
                                                        '').replace(' ', '')
        female = neighbor.count('女')
        if '空' not in neighbor:
            print(counter.x, '/', total, '无空房')
            return meta
        new_meta = dict(name=name,
                        price=price,
                        area=area,
                        rooms=rooms,
                        floor=floor,
                        max_floor=max_floor,
                        orient=orient,
                        neighbor=neighbor,
                        button=button,
                        female=female)
        meta.update(new_meta)
        print(counter.x, '/', total, 'ok')
        return meta
    except:
        traceback.print_exc()
        print(r.url_string)
        return {}


def fetch_detail(detail_metas):
    global total
    counter.current = counter.start
    total = len(detail_metas)
    result = []
    tasks = [[
        req.get(meta['url'],
                callback=detail_cb,
                retry=8,
                timeout=5,
                proxies={'http': PROXY},
                headers={'User-agent': UA.Chrome}), meta
    ] for meta in detail_metas]
    req.x
    for i in tasks:
        task, meta = i
        new_meta = task.cx
        if task.x:
            if new_meta:
                meta.update(new_meta)
                result.append(meta)
    return result


def alarm():
    import os
    os.system(r'explorer.exe .')
    import winsound
    for _ in range(3):
        winsound.Beep(900, 300)


def work():

    with open('list_urls.txt', 'r', encoding='u8') as f:
        list_urls = f.read()
        list_urls = [i.strip() for i in list_urls.splitlines()]
        list_urls = set([i for i in list_urls if i])
    try:
        with open('ziru_old_metas_dict.txt') as f:
            old_metas_dict = json.load(f)
    except FileNotFoundError:
        old_metas_dict = {}

    detail_metas = fetch_list(list_urls) + list(old_metas_dict.values())
    # print(fetch_list(list_urls))
    # return
    detail_metas_unique = {}
    for meta in detail_metas:
        rid = meta['rid']
        if rid not in detail_metas_unique:
            detail_metas_unique[rid] = meta
        else:
            if int(meta['distance']) < int(
                    detail_metas_unique[rid]['distance']):
                detail_metas_unique[rid] = meta
    detail_metas = list(detail_metas_unique.values())
    # print(len(details), 'rooms')
    metas = fetch_detail(detail_metas)
    now = ttime()
    for meta in metas:
        score = 0
        score -= int(meta['female']) * 0.5
        if int(meta['floor']) <= 6:
            score += 0
        elif int(meta['floor']) < 12:
            score += 0.5
        else:
            score += 1
        score += 3 - int(meta['rooms'])
        score += (float(meta['area']) - 10) * 0.1
        distance = int(meta['distance'])
        price = int(meta['price'])
        score += round((2500 - price) / 100) * 0.2
        if re.search('0[34567]卧', meta['name']):
            score -= 0.5
        if meta['floor'] == meta['max_floor']:
            score -= 1
        if distance < 500:
            score += 1
        elif distance < 1000:
            score += 0.5
        elif distance > 1500:
            score -= 0.5
        meta['score'] = round(score, 2)
        if meta['rid'] in old_metas_dict:
            meta['create_time'] = old_metas_dict[meta['rid']].get(
                'create_time') or now
        else:
            meta['create_time'] = now

    metas.sort(key=lambda x: x['score'], reverse=1)
    keys = 'rid name subway station distance price area rooms floor max_floor orient neighbor female score create_time button url'.split(
    )
    has_new = 0
    with open('ziru_now.txt', 'w', encoding='u8') as f:
        with open('ziru_new.txt', 'a', encoding='u8') as ff:
            print(*keys, sep='\t', file=f)
            for i in metas:
                print(*[re.sub('\s+', ' ', str(i[key])) for key in keys],
                      sep='\t',
                      file=f)
                if i['create_time'] == now:
                    print(*[re.sub('\s+', ' ', str(i[key])) for key in keys],
                          sep='\t',
                          file=ff)
                    print('new!')
                    has_new = 1

    # save
    metas_dict = {i['rid']: i for i in metas}
    with open('ziru_old_metas_dict.txt', 'w') as f:
        json.dump(metas_dict, f)
    if has_new:
        alarm()


def main():
    # work()
    while 1:
        work()
        print(ttime())
        tick = 10
        for _ in range(interval // tick):
            print(_, '.', end='', flush=1)
            time.sleep(tick)
        print()


if __name__ == '__main__':
    main()
