#!/usr/bin/env python
# coding=utf-8

from urllib.parse import urlencode
from requests.exceptions import ConnectionError
from bs4 import BeautifulSoup
from json.decoder import JSONDecodeError
from hashlib import md5
from config import *
from multiprocessing import Pool
import requests
import json
import re
import os
import pymongo

client = pymongo.MongoClient(MONGO_URL, connect=False)
db = client[MONGO_DB]

def get_page_index(url, headers):
    """
        作用：返回页面源码
        url:请求地址
        headers：请求头信息
    """
    try:
        response = requests.get(url, headers=headers)
        # 判断是否访问成功
        if response.status_code == 200:
            return response.text
    except ConnectionError:
        print('Erroe occured')
        return None

def parse_page_index(html):
    """
        作用：解析出标题URL地址
        html：网页源码
    """
    try:
        # 将数据转为json格式
        data = json.loads(html)
        # print(data)

        # 判断data是否为空，以及data字典中是否有data这个键
        if data and 'data' in data.keys():
            for item in data.get('data'):
                if item.get('article_url'):
                    yield item.get('article_url')
    except JSONDecodeError:
        pass

def get_page_detail(url, headers):
    """
        作用：返回标题URL网页源码
        url：标题URL地址
        headers：请求头信息
    """
    try:
        response = requests.get(url, headers=headers)
        # 判断是否访问成功
        if response.status_code == 200:
            return response.text
    except ConnectionError:
        print('Error occured')
        return None

def parse_page_detail(html, url):
    """
        作用：解析标题URL地址的每个图片链接
        html：标题URL网页源码
        url：标题URL地址
    """
    # 利用BeautifulSoup找到title的文本
    soup = BeautifulSoup(html, 'lxml') 
    title = soup.title.text
    # 利用正则找到每个下载图片的地址
    images_pattern = re.compile('gallery: JSON.parse\("(.*)"\)', re.S)
    result = images_pattern.search(html)
    # print(result)
    if result:
        data = json.loads(result.group(1).replace('\\', ''))
        # 提取出sub_images键的键值
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            # 使用列表生成式拿到每个图片URL
            images = [item.get('url') for item in sub_images]
            for image in images: 
                # 下载图片
                download_image(image)
                # 将return的结果保存至MongoDB中
                return {
                    'title': title,
                    'url': url,
                    'images': images
                }

def download_image(url):
    """
        作用：返回图片URL源码
        url：图片URL地址
    """
    print('Downloading', url)
    try:
        response = requests.get(url)
        # 判断是否访问成功
        if response.status_code == 200:
            save_image(response.content)
            return None
    except ConnectionError:
        return None

def save_image(content):
    """
        作用：保存图像文件
        content：图像二进制数据
    """
    # 使用md5加密内容，生成图像名称
    file_path = '{0}/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    print(file_path)
    # 判断该文件名是否存在
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()

def save_to_mongo(result):
    """
        作用：保存数据至MongoDB数据库
        result：包括图片标题，请求地址，图像地址
    """
    if db[MONGO_TABLE].insert(result):
        print('Successfully Saved to Mongo', result)
        return True
    return False

def jiepai_Spider(offset):
    """
        作用：整个爬虫调度器
        offset：位置参数
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.62 Safari/537.36'
    }

    data = {
        "offset": offset,
        "format": "json",
        "keyword": "街拍",
        "autoload": "true",
        "count": "20",
        "cur_tab": "1",
        "from": "search_tab"
    }
    # 通过urlencode构造请求URL
    url = 'https://www.toutiao.com/search_content/' + '?' + urlencode(data)

    # 测试url
    # print(url)

    # 获取页面源码
    html = get_page_index(url, headers)

    # 解析HTML，获得链接地址
    for url in parse_page_index(html):
        # print(url)
        # 获得每个链接地址的HTML
        html = get_page_detail(url, headers)
        result = parse_page_detail(html, url)

        # 判断result是否为空，保存至MongoDB数据库中
        if result: 
            save_to_mongo(result)

    

if __name__ == "__main__":
    # 创建进程池
    pool = Pool()
    groups = ([x * 20 for x in range(GROUP_START, GROUP_END + 1)])
    pool.map(jiepai_Spider, groups)
    pool.close()
    # 等待pool中所有子进程执行完成，必须放在close语句之后
    pool.join()
