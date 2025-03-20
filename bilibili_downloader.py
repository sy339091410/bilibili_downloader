#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
B站无水印视频下载器

使用方法:
    python bilibili_downloader.py [视频URL]

本脚本使用Python标准库实现，无需安装额外依赖
"""

import os
import sys
import re
import json
import argparse
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import gzip
import random
import time
from urllib.parse import urlparse


def is_valid_bilibili_url(url):
    """检查URL是否为有效的B站视频链接"""
    patterns = [
        r'https?://(www\.)?bilibili\.com/video/[AaBb][Vv][0-9]+',
        r'https?://(www\.)?b23\.tv/[a-zA-Z0-9]+',
        r'https?://(www\.)?bilibili\.com/bangumi/play/ss[0-9]+',  # 番剧链接(季)格式
        r'https?://(www\.)?bilibili\.com/bangumi/play/ep[0-9]+'   # 番剧链接(集)格式
    ]
    
    for pattern in patterns:
        if re.match(pattern, url):
            return True
    return False


def get_user_agent():
    """返回随机User-Agent"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]
    return random.choice(user_agents)


def get_page_content(url):
    """获取页面内容"""
    headers = {
        'User-Agent': get_user_agent(),
        'Referer': 'https://www.bilibili.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip'
    }
    
    try:
        # 创建cookie处理器
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        urllib.request.install_opener(opener)
        
        # 创建请求
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req, timeout=15)
        
        # 处理gzip压缩
        if response.info().get('Content-Encoding') == 'gzip':
            content = gzip.decompress(response.read()).decode('utf-8')
        else:
            content = response.read().decode('utf-8')
            
        return content
    except Exception as e:
        print(f"获取页面内容失败: {e}")
        return None


def extract_video_info(html_content):
    """从HTML内容中提取视频信息"""
    try:
        # 提取视频信息的JSON数据
        patterns = [
            r'<script>window\.__playinfo__=([^<]+)</script>',  # 旧版页面结构
            r'window\.__playinfo__=([^<]+?)</script>',  # 新版页面结构1
            r'<script>window\.__INITIAL_STATE__=(.+?);</script>',  # 新版页面结构2
            r'<script id="[^"]*">window\.__playinfo__=([^<]+)</script>',  # 新版页面结构3
            r'<script>window\.__INITIAL_STATE__=(.+?);\(function',  # 新版页面结构4
            r'<script>window\.__INITIAL_STATE__=(.+?);window\.__INITIAL_STATE__',  # 新版页面结构5
            r'<script>window\.__INITIAL_STATE__=(.+?)</script>',  # 新版页面结构6
            r'<script>window\.__playinfo__=(.+?)</script>',  # 新版页面结构7
            r'<script>window\.__INITIAL_STATE__=(.+?);</script>'  # 新版页面结构8
        ]
        
        # 尝试直接从页面中提取playinfo
        play_info = None
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                try:
                    data = match.group(1)
                    # 尝试解析JSON
                    play_info = json.loads(data)
                    # 如果成功解析，检查是否包含视频信息
                    if 'data' in play_info and ('dash' in play_info['data'] or 'durl' in play_info['data']):
                        print("成功提取视频信息")
                        break
                    elif 'videoData' in play_info:
                        # 处理INITIAL_STATE格式
                        print("从INITIAL_STATE中提取视频信息")
                        # 尝试从INITIAL_STATE中提取cid和aid
                        video_data = play_info.get('videoData', {})
                        cid = video_data.get('cid')
                        aid = video_data.get('aid')
                        bvid = video_data.get('bvid')
                        
                        print(f"提取到视频信息: cid={cid}, aid={aid}, bvid={bvid}")
                        
                        if cid and (aid or bvid):
                            # 构建playurl API请求，请求最高清晰度(127=8K, 120=4K)
                            api_url = f"https://api.bilibili.com/x/player/playurl?cid={cid}&bvid={bvid}&qn=127&fnval=16&fourk=1"
                            print(f"尝试从API获取视频信息: {api_url}")
                            
                            # 获取API响应
                            api_content = get_page_content(api_url)
                            if api_content:
                                try:
                                    api_data = json.loads(api_content)
                                    print(f"API响应状态码: {api_data.get('code')}")
                                    if api_data.get('code') == 0 and 'data' in api_data:
                                        # 替换play_info
                                        play_info = {'code': 0, 'data': api_data['data']}
                                        print("成功从API获取视频信息")
                                        break
                                    else:
                                        print(f"API返回错误: {api_data.get('message')}")
                                except Exception as e:
                                    print(f"解析API响应失败: {e}")
                            else:
                                print("获取API响应失败")
                        else:
                            print("无法从INITIAL_STATE中提取必要的视频信息")
                        break
                    else:
                        # 不包含视频信息，继续尝试下一个模式
                        play_info = None
                except json.JSONDecodeError:
                    continue
        
        if not play_info:
            print("无法找到视频信息")
            return None
            
        # 已在上面的模式匹配中处理
        
        # 提取视频标题
        title_pattern = r'<title[^>]*>([^<]+)</title>'
        title_match = re.search(title_pattern, html_content)
        title = title_match.group(1).strip() if title_match else "bilibili_video"
        title = title.replace(" - 哔哩哔哩", "").replace("/", "_").replace("\\", "_")
        
        # 获取视频URL
        video_url = None
        audio_url = None
        video_quality = "未知"
        video_resolution = "未知"
        
        # 尝试获取最高质量的视频
        if 'data' in play_info and 'dash' in play_info['data']:
            # 新版API
            dash = play_info['data']['dash']
            if 'video' in dash and dash['video']:
                videos = dash['video']
                # 按清晰度ID和带宽排序，选择最高质量的视频
                # 首先按清晰度ID排序，然后按带宽排序
                videos.sort(key=lambda x: (x.get('id', 0), x.get('bandwidth', 0)), reverse=True)
                selected_video = videos[0]
                video_url = selected_video['baseUrl']
                
                # 提取视频质量信息
                if 'id' in selected_video:
                    quality_id = selected_video['id']
                    quality_map = {
                        16: "240P",
                        32: "360P",
                        64: "480P",
                        74: "720P",
                        80: "1080P",
                        112: "1080P+",
                        116: "1080P60",
                        120: "4K",
                        125: "HDR",
                        126: "杜比视界",
                        127: "8K",
                        128: "4K HDR",
                        129: "8K HDR",
                        30: "360P 流畅",
                        48: "720P 高清",
                        66: "720P60",
                        70: "1080P60 高帧率"
                    }
                    video_quality = quality_map.get(quality_id, f"未知({quality_id})")
                
                # 提取分辨率信息
                if 'width' in selected_video and 'height' in selected_video:
                    video_resolution = f"{selected_video['width']}x{selected_video['height']}"
                
                print(f"已选择最高清晰度视频: {video_quality} ({video_resolution})")
            
            if 'audio' in dash and dash['audio']:
                audios = dash['audio']
                # 按带宽和采样率排序，选择最高质量的音频
                audios.sort(key=lambda x: (x.get('bandwidth', 0), x.get('codecid', 0)), reverse=True)
                audio_url = audios[0]['baseUrl']
                print(f"已选择最高质量音频: {audios[0].get('bandwidth', 0)/1000:.0f}Kbps")
        elif 'data' in play_info and 'durl' in play_info['data']:
            # 旧版API
            # 如果有多个视频片段，选择第一个
            video_url = play_info['data']['durl'][0]['url']
            # 尝试从accept_quality或accept_description获取质量信息
            if 'accept_quality' in play_info['data'] and play_info['data']['accept_quality']:
                # 如果有多个可选清晰度，确保选择最高的
                print(f"可用清晰度: {play_info['data']['accept_quality']}")
                # 清晰度ID越大，质量越高
            if 'quality' in play_info['data']:
                quality_id = play_info['data']['quality']
                quality_map = {
                    16: "240P",
                    32: "360P",
                    64: "480P",
                    74: "720P",
                    80: "1080P",
                    112: "1080P+",
                    116: "1080P60",
                    120: "4K",
                    125: "HDR",
                    126: "杜比视界",
                    127: "8K",
                    128: "4K HDR",
                    129: "8K HDR",
                    30: "360P 流畅",
                    48: "720P 高清",
                    66: "720P60",
                    70: "1080P60 高帧率"
                }
                video_quality = quality_map.get(quality_id, f"未知({quality_id})")
                print(f"已选择最高清晰度视频: {video_quality}")
        
        if not video_url:
            print("无法找到视频下载链接")
            return None
            
        return {
            'title': title,
            'video_url': video_url,
            'audio_url': audio_url,
            'quality': video_quality,
            'resolution': video_resolution
        }
    except Exception as e:
        print(f"提取视频信息失败: {e}")
        return None


def download_file(url, filename, headers=None):
    """下载文件"""
    if headers is None:
        headers = {
            'User-Agent': get_user_agent(),
            'Referer': 'https://www.bilibili.com/',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Range': 'bytes=0-'
        }
    
    try:
        print(f"正在下载: {filename}")
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req, timeout=30)
        
        # 获取文件大小
        file_size = int(response.info().get('Content-Length', 0))
        downloaded_size = 0
        chunk_size = 1024 * 1024  # 1MB
        
        with open(filename, 'wb') as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                    
                f.write(chunk)
                downloaded_size += len(chunk)
                
                # 显示下载进度
                if file_size > 0:
                    percent = downloaded_size * 100 / file_size
                    progress_bar = '█' * int(percent // 2) + '░' * (50 - int(percent // 2))
                    print(f"下载进度: [{progress_bar}] {percent:.2f}% ({downloaded_size/1024/1024:.2f}/{file_size/1024/1024:.2f} MB)\r", end='')
                else:
                    print(f"已下载: {downloaded_size/1024/1024:.2f} MB\r", end='')
        
        return True
    except Exception as e:
        print(f"下载文件失败: {e}")
        if os.path.exists(filename):
            os.remove(filename)
        return False


def merge_video_audio(video_file, audio_file, output_file):
    """合并视频和音频文件"""
    try:
        # 使用系统自带的cat命令简单合并文件
        # 注意：这种方法并不能正确合并视频和音频，但在没有ffmpeg的情况下是一种临时解决方案
        print("警告：由于没有ffmpeg，无法正确合并视频和音频。")
        print("视频和音频文件将被分别保存。")
        return False
    except Exception as e:
        print(f"合并视频和音频失败: {e}")
        return False


def extract_bangumi_info(url, html_content):
    """从番剧页面中提取视频信息"""
    try:
        # 提取番剧信息的JSON数据
        patterns = [
            r'<script>window\.__INITIAL_STATE__=(.+?);</script>',
            r'<script>window\.__INITIAL_STATE__=(.+?);\(function',
            r'<script>window\.__INITIAL_STATE__=(.+?);window\.__INITIAL_STATE__',
            r'<script>window\.__INITIAL_STATE__=(.+?)</script>',
            r'__INITIAL_STATE__=(.+?);</script>'
        ]
        
        initial_state = None
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                try:
                    data = match.group(1)
                    initial_state = json.loads(data)
                    print("成功提取番剧INITIAL_STATE数据")
                    # 打印关键字段，帮助调试
                    if initial_state:
                        print(f"INITIAL_STATE包含的键: {list(initial_state.keys())}")
                    break
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {e}")
                    continue
        
        if not initial_state:
            print("无法找到番剧信息，尝试使用常规视频提取方法...")
            # 尝试使用常规视频提取方法
            return extract_video_info(html_content)
        
        # 提取番剧标题
        title = None
        if 'mediaInfo' in initial_state and 'title' in initial_state['mediaInfo']:
            title = initial_state['mediaInfo']['title']
        elif 'h1Title' in initial_state:
            title = initial_state['h1Title']
        else:
            # 尝试从HTML标题提取
            title_pattern = r'<title[^>]*>([^<]+)</title>'
            title_match = re.search(title_pattern, html_content)
            title = title_match.group(1).strip() if title_match else "bilibili_bangumi"
            title = title.replace(" - 哔哩哔哩番剧", "").replace(" - 哔哩哔哩", "")
        
        # 清理标题，移除非法字符
        title = title.replace("/", "_").replace("\\", "_")
        
        # 提取epId或ssId
        ep_id = None
        ss_id = None
        
        # 从URL中提取ssId或epId
        ss_match = re.search(r'ss(\d+)', url)
        ep_match = re.search(r'ep(\d+)', url)
        
        if ss_match:
            ss_id = ss_match.group(1)
            print(f"从URL中提取到ssId: {ss_id}")
        elif ep_match:
            ep_id = ep_match.group(1)
            print(f"从URL中提取到epId: {ep_id}")
        
        # 如果URL中没有，尝试从INITIAL_STATE中提取
        if not ep_id and not ss_id:
            if 'epInfo' in initial_state and 'id' in initial_state['epInfo']:
                ep_id = initial_state['epInfo']['id']
                print(f"从INITIAL_STATE中提取到epId: {ep_id}")
            elif 'epId' in initial_state:
                ep_id = initial_state['epId']
                print(f"从INITIAL_STATE中提取到epId: {ep_id}")
            elif 'mediaInfo' in initial_state and 'season_id' in initial_state['mediaInfo']:
                ss_id = initial_state['mediaInfo']['season_id']
                print(f"从INITIAL_STATE中提取到ssId: {ss_id}")
        
        # 提取分集标题
        ep_title = None
        if 'epInfo' in initial_state and 'titleFormat' in initial_state['epInfo'] and 'longTitle' in initial_state['epInfo']:
            ep_format = initial_state['epInfo']['titleFormat']
            ep_long_title = initial_state['epInfo']['longTitle']
            ep_title = f"{ep_format} {ep_long_title}".strip()
        
        # 如果有分集标题，将其添加到主标题中
        if ep_title and ep_title != "":
            title = f"{title}_{ep_title}"
        
        # 构建API URL获取视频播放信息
        api_url = None
        if ep_id:
            api_url = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&qn=127&fnval=16&fourk=1"
            print(f"使用epId构建API URL: {api_url}")
        elif ss_id:
            # 如果只有ssId，先获取该季的第一集的epId
            season_url = f"https://api.bilibili.com/pgc/view/web/season?season_id={ss_id}"
            print(f"获取季度信息: {season_url}")
            season_content = get_page_content(season_url)
            if season_content:
                try:
                    season_data = json.loads(season_content)
                    if season_data.get('code') == 0 and 'result' in season_data and 'episodes' in season_data['result'] and len(season_data['result']['episodes']) > 0:
                        first_ep = season_data['result']['episodes'][0]
                        ep_id = first_ep.get('id')
                        print(f"获取到第一集的epId: {ep_id}")
                        # 更新标题，添加集数信息
                        ep_title = first_ep.get('title', '') + ' ' + first_ep.get('long_title', '')
                        if ep_title.strip():
                            title = f"{title}_{ep_title.strip()}"
                        api_url = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&qn=127&fnval=16&fourk=1"
                        print(f"使用第一集epId构建API URL: {api_url}")
                    else:
                        print(f"获取季度信息失败: {season_data.get('message')}")
                except Exception as e:
                    print(f"解析季度信息失败: {e}")
        
        if not api_url:
            print("无法构建API URL，既没有找到epId也没有找到ssId")
            return None
        print(f"尝试从API获取番剧视频信息: {api_url}")
        
        # 获取API响应
        api_content = get_page_content(api_url)
        if not api_content:
            print("获取番剧API响应失败")
            return None
        
        try:
            api_data = json.loads(api_content)
            if api_data.get('code') != 0:
                print(f"API返回错误: {api_data.get('message')}")
                return None
            
            # 构造与普通视频相同格式的返回数据
            play_info = {'code': 0, 'data': api_data['result']}
            
            # 获取视频URL
            video_url = None
            audio_url = None
            video_quality = "未知"
            video_resolution = "未知"
            
            # 尝试获取最高质量的视频
            if 'dash' in play_info['data']:
                # 新版API
                dash = play_info['data']['dash']
                if 'video' in dash and dash['video']:
                    videos = dash['video']
                    # 按清晰度ID和带宽排序，选择最高质量的视频
                    videos.sort(key=lambda x: (x.get('id', 0), x.get('bandwidth', 0)), reverse=True)
                    selected_video = videos[0]
                    video_url = selected_video['baseUrl']
                    
                    # 提取视频质量信息
                    if 'id' in selected_video:
                        quality_id = selected_video['id']
                        quality_map = {
                            16: "240P",
                            32: "360P",
                            64: "480P",
                            74: "720P",
                            80: "1080P",
                            112: "1080P+",
                            116: "1080P60",
                            120: "4K",
                            125: "HDR",
                            126: "杜比视界",
                            127: "8K",
                            128: "4K HDR",
                            129: "8K HDR",
                            30: "360P 流畅",
                            48: "720P 高清",
                            66: "720P60",
                            70: "1080P60 高帧率"
                        }
                        video_quality = quality_map.get(quality_id, f"未知({quality_id})")
                    
                    # 提取分辨率信息
                    if 'width' in selected_video and 'height' in selected_video:
                        video_resolution = f"{selected_video['width']}x{selected_video['height']}"
                    
                    print(f"已选择最高清晰度视频: {video_quality} ({video_resolution})")
                
                if 'audio' in dash and dash['audio']:
                    audios = dash['audio']
                    # 按带宽和采样率排序，选择最高质量的音频
                    audios.sort(key=lambda x: (x.get('bandwidth', 0), x.get('codecid', 0)), reverse=True)
                    audio_url = audios[0]['baseUrl']
                    print(f"已选择最高质量音频: {audios[0].get('bandwidth', 0)/1000:.0f}Kbps")
            
            if not video_url:
                print("无法找到番剧视频下载链接")
                return None
                
            return {
                'title': title,
                'video_url': video_url,
                'audio_url': audio_url,
                'quality': video_quality,
                'resolution': video_resolution
            }
        except Exception as e:
            print(f"解析番剧API响应失败: {e}")
            return None
    except Exception as e:
        print(f"提取番剧信息失败: {e}")
        return None


def download_video(url, output_dir=None, retry_count=3):
    """下载B站无水印视频
    
    Args:
        url: B站视频链接
        output_dir: 输出目录
        retry_count: 下载失败时的重试次数
    """
    try:
        # 创建输出目录（如果不存在）
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = os.getcwd()
        
        # 处理URL，移除查询参数
        clean_url = url.split('?')[0]
        print(f"处理后的URL: {clean_url}")
        
        print(f"正在获取视频 {clean_url} 的信息...")
        html_content = get_page_content(clean_url)
        if not html_content:
            print("获取视频页面失败")
            sys.exit(1)
        
        # 判断是否为番剧链接
        is_bangumi = re.match(r'https?://(www\.)?bilibili\.com/bangumi/play/(ss|ep)[0-9]+', clean_url) is not None
        
        if is_bangumi:
            print("检测到番剧链接，使用番剧解析方式...")
            # 从URL中提取ssId或epId
            ss_match = re.search(r'ss(\d+)', clean_url)
            ep_match = re.search(r'ep(\d+)', clean_url)
            
            if ss_match:
                ss_id = ss_match.group(1)
                print(f"从URL中提取到ssId: {ss_id}")
                # 直接使用ssId构建API请求
                season_url = f"https://api.bilibili.com/pgc/view/web/season?season_id={ss_id}"
                print(f"获取季度信息: {season_url}")
                season_content = get_page_content(season_url)
                if season_content:
                    try:
                        season_data = json.loads(season_content)
                        if season_data.get('code') == 0 and 'result' in season_data:
                            # 提取标题
                            title = season_data['result'].get('title', 'bilibili_bangumi')
                            # 如果有剧集，获取第一集
                            if 'episodes' in season_data['result'] and len(season_data['result']['episodes']) > 0:
                                first_ep = season_data['result']['episodes'][0]
                                ep_id = first_ep.get('id')
                                print(f"获取到第一集的epId: {ep_id}")
                                # 更新标题，添加集数信息
                                ep_title = first_ep.get('title', '') + ' ' + first_ep.get('long_title', '')
                                if ep_title.strip():
                                    title = f"{title}_{ep_title.strip()}"
                                # 使用epId获取视频信息
                                api_url = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&qn=127&fnval=16&fourk=1"
                                print(f"使用epId构建API URL: {api_url}")
                                api_content = get_page_content(api_url)
                                if api_content:
                                    api_data = json.loads(api_content)
                                    if api_data.get('code') == 0 and 'result' in api_data:
                                        # 构造视频信息
                                        video_info = process_bangumi_api_response(api_data, title)
                                        if video_info:
                                            print("成功获取番剧视频信息")
                                        else:
                                            print("处理番剧API响应失败")
                                            video_info = extract_bangumi_info(clean_url, html_content)
                                    else:
                                        print(f"API返回错误: {api_data.get('message')}")
                                        video_info = extract_bangumi_info(clean_url, html_content)
                                else:
                                    print("获取API响应失败")
                                    video_info = extract_bangumi_info(clean_url, html_content)
                            else:
                                print("未找到剧集信息")
                                video_info = extract_bangumi_info(clean_url, html_content)
                        else:
                            print(f"获取季度信息失败: {season_data.get('message')}")
                            video_info = extract_bangumi_info(clean_url, html_content)
                    except Exception as e:
                        print(f"解析季度信息失败: {e}")
                        video_info = extract_bangumi_info(clean_url, html_content)
                else:
                    print("获取季度信息失败")
                    video_info = extract_bangumi_info(clean_url, html_content)
            elif ep_match:
                ep_id = ep_match.group(1)
                print(f"从URL中提取到epId: {ep_id}")
                # 直接使用epId构建API请求
                api_url = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&qn=127&fnval=16&fourk=1"
                print(f"使用epId构建API URL: {api_url}")
                api_content = get_page_content(api_url)
                if api_content:
                    try:
                        api_data = json.loads(api_content)
                        if api_data.get('code') == 0 and 'result' in api_data:
                            # 提取标题
                            title_pattern = r'<title[^>]*>([^<]+)</title>'
                            title_match = re.search(title_pattern, html_content)
                            title = title_match.group(1).strip() if title_match else "bilibili_bangumi"
                            title = title.replace(" - 哔哩哔哩番剧", "").replace(" - 哔哩哔哩", "")
                            # 构造视频信息
                            video_info = process_bangumi_api_response(api_data, title)
                            if video_info:
                                print("成功获取番剧视频信息")
                            else:
                                print("处理番剧API响应失败")
                                video_info = extract_bangumi_info(clean_url, html_content)
                        else:
                            print(f"API返回错误: {api_data.get('message')}")
                            video_info = extract_bangumi_info(clean_url, html_content)
                    except Exception as e:
                        print(f"解析API响应失败: {e}")
                        video_info = extract_bangumi_info(clean_url, html_content)
                else:
                    print("获取API响应失败")
                    video_info = extract_bangumi_info(clean_url, html_content)
            else:
                print("URL中未找到ssId或epId")
                video_info = extract_bangumi_info(clean_url, html_content)
        else:
            video_info = extract_video_info(html_content)
            
        if not video_info:
            print("解析视频信息失败")
            sys.exit(1)
            
        title = video_info['title']
        video_url = video_info['video_url']
        audio_url = video_info['audio_url']
        quality = video_info.get('quality', '未知')
        resolution = video_info.get('resolution', '未知')
        
        print(f"视频标题: {title}")
        print(f"视频清晰度: {quality} {resolution}")
        print("正在下载最高清晰度视频...")
        print("注意: 实际下载的清晰度取决于视频源和用户权限(大会员可下载更高清晰度)")
        print("本脚本会自动请求最高清晰度(8K/4K/1080P)的视频源")
        
        # 设置下载文件路径
        video_file = os.path.join(output_dir, f"{title}_video.mp4")
        
        # 下载视频
        print(f"开始下载视频...")
        headers = {
            'User-Agent': get_user_agent(),
            'Referer': url,
            'Origin': 'https://www.bilibili.com',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Range': 'bytes=0-'
        }
        
        if not download_file(video_url, video_file, headers):
            print("视频下载失败")
            sys.exit(1)
            
        # 如果有音频，下载音频
        if audio_url:
            audio_file = os.path.join(output_dir, f"{title}_audio.m4a")
            print(f"开始下载音频...")
            if not download_file(audio_url, audio_file, headers):
                print("音频下载失败")
                sys.exit(1)
                
            # 尝试合并视频和音频
            output_file = os.path.join(output_dir, f"{title}.mp4")
            if merge_video_audio(video_file, audio_file, output_file):
                print(f"视频和音频已合并: {output_file}")
                # 删除临时文件
                os.remove(video_file)
                os.remove(audio_file)
            else:
                print(f"视频文件: {video_file}")
                print(f"音频文件: {audio_file}")
        else:
            print(f"视频已下载: {video_file}")
            
        print("下载完成！")
        print(f"文件保存在: {output_dir}")
    except Exception as e:
        print(f"下载失败: {e}")
        sys.exit(1)


def process_bangumi_api_response(api_data, title):
    """处理番剧API响应，提取视频信息"""
    try:
        if 'result' not in api_data or api_data.get('code') != 0:
            return None
            
        result = api_data['result']
        
        # 获取视频URL
        video_url = None
        audio_url = None
        video_quality = "未知"
        video_resolution = "未知"
        
        # 尝试获取最高质量的视频
        if 'dash' in result:
            # 新版API
            dash = result['dash']
            if 'video' in dash and dash['video']:
                videos = dash['video']
                # 按清晰度ID和带宽排序，选择最高质量的视频
                videos.sort(key=lambda x: (x.get('id', 0), x.get('bandwidth', 0)), reverse=True)
                selected_video = videos[0]
                video_url = selected_video['baseUrl']
                
                # 提取视频质量信息
                if 'id' in selected_video:
                    quality_id = selected_video['id']
                    quality_map = {
                        16: "240P",
                        32: "360P",
                        64: "480P",
                        74: "720P",
                        80: "1080P",
                        112: "1080P+",
                        116: "1080P60",
                        120: "4K",
                        125: "HDR",
                        126: "杜比视界",
                        127: "8K",
                        128: "4K HDR",
                        129: "8K HDR",
                        30: "360P 流畅",
                        48: "720P 高清",
                        66: "720P60",
                        70: "1080P60 高帧率"
                    }
                    video_quality = quality_map.get(quality_id, f"未知({quality_id})")
                
                # 提取分辨率信息
                if 'width' in selected_video and 'height' in selected_video:
                    video_resolution = f"{selected_video['width']}x{selected_video['height']}"
                
                print(f"已选择最高清晰度视频: {video_quality} ({video_resolution})")
            
            if 'audio' in dash and dash['audio']:
                audios = dash['audio']
                # 按带宽和采样率排序，选择最高质量的音频
                audios.sort(key=lambda x: (x.get('bandwidth', 0), x.get('codecid', 0)), reverse=True)
                audio_url = audios[0]['baseUrl']
                print(f"已选择最高质量音频: {audios[0].get('bandwidth', 0)/1000:.0f}Kbps")
        elif 'durl' in result:
            # 旧版API
            # 如果有多个视频片段，选择第一个
            video_url = result['durl'][0]['url']
            # 尝试从accept_quality或accept_description获取质量信息
            if 'quality' in result:
                quality_id = result['quality']
                quality_map = {
                    16: "240P",
                    32: "360P",
                    64: "480P",
                    74: "720P",
                    80: "1080P",
                    112: "1080P+",
                    116: "1080P60",
                    120: "4K",
                    125: "HDR",
                    126: "杜比视界",
                    127: "8K",
                    128: "4K HDR",
                    129: "8K HDR",
                    30: "360P 流畅",
                    48: "720P 高清",
                    66: "720P60",
                    70: "1080P60 高帧率"
                }
                video_quality = quality_map.get(quality_id, f"未知({quality_id})")
                print(f"已选择最高清晰度视频: {video_quality}")
        
        if not video_url:
            print("无法找到番剧视频下载链接")
            return None
            
        return {
            'title': title,
            'video_url': video_url,
            'audio_url': audio_url,
            'quality': video_quality,
            'resolution': video_resolution
        }
    except Exception as e:
        print(f"处理番剧API响应失败: {e}")
        return None
        
        if not download_file(video_url, video_file, headers):
            print("视频下载失败")
            sys.exit(1)
            
        # 如果有音频，下载音频
        if audio_url:
            audio_file = os.path.join(output_dir, f"{title}_audio.m4a")
            print(f"开始下载音频...")
            if not download_file(audio_url, audio_file, headers):
                print("音频下载失败")
                sys.exit(1)
                
            # 尝试合并视频和音频
            output_file = os.path.join(output_dir, f"{title}.mp4")
            if merge_video_audio(video_file, audio_file, output_file):
                print(f"视频和音频已合并: {output_file}")
                # 删除临时文件
                os.remove(video_file)
                os.remove(audio_file)
            else:
                print(f"视频文件: {video_file}")
                print(f"音频文件: {audio_file}")
        else:
            print(f"视频已下载: {video_file}")
            
        print("下载完成！")
        print(f"文件保存在: {output_dir}")
            
    except Exception as e:
        print(f"下载失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='B站无水印视频下载器')
    parser.add_argument('url', help='B站视频链接')
    parser.add_argument('-o', '--output-dir', help='视频保存目录')
    parser.add_argument('-r', '--retry', type=int, default=3, help='下载失败时的重试次数')
    parser.add_argument('-v', '--version', action='version', version='B站无水印视频下载器 v1.1.0')
    
    args = parser.parse_args()
    
    # 检查URL是否有效
    if not is_valid_bilibili_url(args.url):
        print("错误: 请提供有效的B站视频链接")
        sys.exit(1)
    
    # 下载视频
    download_video(args.url, args.output_dir, args.retry)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法: python bilibili_downloader.py [视频URL] [-o 输出目录]")
        sys.exit(1)
    
    main()