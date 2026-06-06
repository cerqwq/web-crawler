"""
一键爬虫 - 完整功能版
支持：多线程、代理、去重、存储、Web监控、自动重试
"""

import os
import re
import json
import csv
import time
import hashlib
import logging
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
from collections import deque
from typing import Set, Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# ============================================================
# 配置
# ============================================================

@dataclass
class CrawlerConfig:
    """爬虫配置"""
    # 基础配置
    start_urls: List[str] = field(default_factory=list)
    max_depth: int = 3
    max_pages: int = 1000
    max_workers: int = 5
    request_timeout: int = 30
    delay_between_requests: float = 0.5

    # 过滤配置
    allowed_domains: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=list)
    allowed_extensions: List[str] = field(default_factory=lambda: [
        '.html', '.htm', '.php', '.asp', '.aspx', '.jsp', '.cgi'
    ])
    blocked_extensions: List[str] = field(default_factory=lambda: [
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.zip', '.rar', '.7z', '.tar', '.gz',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico',
        '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv',
        '.css', '.js', '.xml', '.json'
    ])

    # 请求配置
    user_agents: List[str] = field(default_factory=lambda: [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ])
    proxies: List[str] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=lambda: {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })

    # 存储配置
    output_dir: str = './output'
    save_html: bool = False
    save_text: bool = True
    save_links: bool = True
    save_images: bool = True
    save_to_json: bool = True
    save_to_csv: bool = True
    save_to_db: bool = True

    # 重试配置
    max_retries: int = 3
    retry_delay: float = 2.0

    # 日志配置
    log_level: str = 'INFO'
    log_file: str = 'crawler.log'


# ============================================================
# 数据模型
# ============================================================

@dataclass
class PageInfo:
    """页面信息"""
    url: str
    title: str = ''
    description: str = ''
    keywords: str = ''
    text_content: str = ''
    html_content: str = ''
    links: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    depth: int = 0
    status_code: int = 0
    content_type: str = ''
    content_length: int = 0
    crawl_time: str = ''
    parent_url: str = ''
    error: str = ''


# ============================================================
# URL 管理器
# ============================================================

class URLManager:
    """URL管理器 - 去重、过滤、优先级"""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.visited: Set[str] = set()
        self.queue: deque = deque()
        self.url_hashes: Set[str] = set()

    def add_url(self, url: str, depth: int = 0, parent: str = ''):
        """添加URL到队列"""
        # 标准化URL
        url = self._normalize_url(url)
        if not url:
            return False

        # 检查是否已访问
        url_hash = self._hash_url(url)
        if url_hash in self.url_hashes:
            return False

        # 检查域名过滤
        if not self._check_domain(url):
            return False

        # 检查扩展名过滤
        if not self._check_extension(url):
            return False

        # 检查深度
        if depth > self.config.max_depth:
            return False

        self.url_hashes.add(url_hash)
        self.queue.append((url, depth, parent))
        return True

    def get_url(self) -> Optional[tuple]:
        """从队列获取URL"""
        if self.queue:
            return self.queue.popleft()
        return None

    def mark_visited(self, url: str):
        """标记URL已访问"""
        self.visited.add(self._normalize_url(url))

    def is_visited(self, url: str) -> bool:
        """检查URL是否已访问"""
        return self._normalize_url(url) in self.visited

    def _normalize_url(self, url: str) -> str:
        """标准化URL"""
        if not url:
            return ''
        # 去除fragment
        parsed = urlparse(url)
        # 重建URL（不含fragment）
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        # 去除尾部斜杠（除非是根路径）
        if normalized.endswith('/') and len(parsed.path) > 1:
            normalized = normalized.rstrip('/')
        return normalized

    def _hash_url(self, url: str) -> str:
        """生成URL哈希"""
        return hashlib.md5(url.encode()).hexdigest()

    def _check_domain(self, url: str) -> bool:
        """检查域名是否允许"""
        parsed = urlparse(url)
        domain = parsed.netloc

        # 检查黑名单
        if self.config.blocked_domains:
            for blocked in self.config.blocked_domains:
                if blocked in domain:
                    return False

        # 检查白名单
        if self.config.allowed_domains:
            for allowed in self.config.allowed_domains:
                if allowed in domain:
                    return True
            return False

        return True

    def _check_extension(self, url: str) -> bool:
        """检查文件扩展名是否允许"""
        parsed = urlparse(url)
        path = parsed.path.lower()

        # 检查黑名单
        for ext in self.config.blocked_extensions:
            if path.endswith(ext):
                return False

        # 如果有白名单，检查白名单
        if self.config.allowed_extensions:
            for ext in self.config.allowed_extensions:
                if path.endswith(ext):
                    return True
            # 如果没有扩展名，也允许（可能是目录页面）
            if '.' not in path.split('/')[-1]:
                return True
            return False

        return True

    @property
    def queue_size(self) -> int:
        return len(self.queue)

    @property
    def visited_count(self) -> int:
        return len(self.visited)


# ============================================================
# 页面解析器
# ============================================================

class PageParser:
    """页面解析器 - 提取标题、链接、图片、文本"""

    def __init__(self):
        self.logger = logging.getLogger('PageParser')

    def parse(self, url: str, html: str, status_code: int, content_type: str) -> PageInfo:
        """解析页面"""
        page = PageInfo(
            url=url,
            html_content=html,
            status_code=status_code,
            content_type=content_type,
            content_length=len(html),
            crawl_time=datetime.now().isoformat()
        )

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # 提取标题
            page.title = self._extract_title(soup)

            # 提取描述
            page.description = self._extract_meta(soup, 'description')

            # 提取关键词
            page.keywords = self._extract_meta(soup, 'keywords')

            # 提取文本内容
            page.text_content = self._extract_text(soup)

            # 提取链接
            page.links = self._extract_links(soup, url)

            # 提取图片
            page.images = self._extract_images(soup, url)

        except Exception as e:
            self.logger.error(f"解析页面失败 {url}: {e}")
            page.error = str(e)

        return page

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取标题"""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)
        # 尝试h1
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text(strip=True)
        return ''

    def _extract_meta(self, soup: BeautifulSoup, name: str) -> str:
        """提取meta标签"""
        meta = soup.find('meta', attrs={'name': name})
        if meta:
            return meta.get('content', '')
        # 也检查property属性
        meta = soup.find('meta', attrs={'property': f'og:{name}'})
        if meta:
            return meta.get('content', '')
        return ''

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """提取正文文本"""
        # 移除script和style
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()

        # 获取文本
        text = soup.get_text(separator='\n', strip=True)

        # 清理多余空行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """提取链接"""
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # 转换相对URL为绝对URL
            absolute_url = urljoin(base_url, href)
            # 过滤非HTTP链接
            if absolute_url.startswith('http://') or absolute_url.startswith('https://'):
                links.append(absolute_url)
        return list(set(links))

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """提取图片"""
        images = []
        for img_tag in soup.find_all('img', src=True):
            src = img_tag['src']
            absolute_url = urljoin(base_url, src)
            if absolute_url.startswith('http://') or absolute_url.startswith('https://'):
                images.append(absolute_url)
        return list(set(images))


# ============================================================
# 数据存储器
# ============================================================

class DataStorage:
    """数据存储器 - JSON、CSV、SQLite"""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger('DataStorage')

        # 初始化SQLite
        if config.save_to_db:
            self.db_path = self.output_dir / 'crawler.db'
            self._init_db()

        # 初始化CSV
        if config.save_to_csv:
            self.csv_path = self.output_dir / 'pages.csv'
            self.csv_file = open(self.csv_path, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow([
                'url', 'title', 'description', 'keywords', 'depth',
                'status_code', 'content_length', 'links_count', 'images_count', 'crawl_time'
            ])

        # JSON数据
        self.json_data: List[Dict] = []

    def _init_db(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                description TEXT,
                keywords TEXT,
                text_content TEXT,
                depth INTEGER,
                status_code INTEGER,
                content_type TEXT,
                content_length INTEGER,
                links_count INTEGER,
                images_count INTEGER,
                crawl_time TEXT,
                parent_url TEXT,
                error TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                target_url TEXT,
                crawl_time TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_url TEXT,
                image_url TEXT,
                crawl_time TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def save_page(self, page: PageInfo):
        """保存页面数据"""
        # 保存到JSON
        if self.config.save_to_json:
            self.json_data.append(asdict(page))

        # 保存到CSV
        if self.config.save_to_csv:
            self.csv_writer.writerow([
                page.url, page.title, page.description, page.keywords,
                page.depth, page.status_code, page.content_length,
                len(page.links), len(page.images), page.crawl_time
            ])
            self.csv_file.flush()

        # 保存到SQLite
        if self.config.save_to_db:
            self._save_to_db(page)

        # 保存HTML文件
        if self.config.save_html and page.html_content:
            self._save_html_file(page)

        # 保存文本文件
        if self.config.save_text and page.text_content:
            self._save_text_file(page)

    def _save_to_db(self, page: PageInfo):
        """保存到SQLite"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 保存页面
            cursor.execute('''
                INSERT OR REPLACE INTO pages
                (url, title, description, keywords, text_content, depth,
                 status_code, content_type, content_length, links_count,
                 images_count, crawl_time, parent_url, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                page.url, page.title, page.description, page.keywords,
                page.text_content, page.depth, page.status_code,
                page.content_type, page.content_length, len(page.links),
                len(page.images), page.crawl_time, page.parent_url, page.error
            ))

            # 保存链接
            for link in page.links:
                cursor.execute('''
                    INSERT INTO links (source_url, target_url, crawl_time)
                    VALUES (?, ?, ?)
                ''', (page.url, link, page.crawl_time))

            # 保存图片
            for image in page.images:
                cursor.execute('''
                    INSERT INTO images (page_url, image_url, crawl_time)
                    VALUES (?, ?, ?)
                ''', (page.url, image, page.crawl_time))

            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"保存到数据库失败: {e}")

    def _save_html_file(self, page: PageInfo):
        """保存HTML文件"""
        try:
            # 生成文件名
            parsed = urlparse(page.url)
            domain = parsed.netloc.replace('.', '_')
            path = parsed.path.replace('/', '_').strip('_')
            if not path:
                path = 'index'
            filename = f"{domain}_{path}.html"
            filepath = self.output_dir / 'html' / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(page.html_content)
        except Exception as e:
            self.logger.error(f"保存HTML文件失败: {e}")

    def _save_text_file(self, page: PageInfo):
        """保存文本文件"""
        try:
            parsed = urlparse(page.url)
            domain = parsed.netloc.replace('.', '_')
            path = parsed.path.replace('/', '_').strip('_')
            if not path:
                path = 'index'
            filename = f"{domain}_{path}.txt"
            filepath = self.output_dir / 'text' / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"URL: {page.url}\n")
                f.write(f"标题: {page.title}\n")
                f.write(f"描述: {page.description}\n")
                f.write(f"爬取时间: {page.crawl_time}\n")
                f.write(f"{'='*50}\n\n")
                f.write(page.text_content)
        except Exception as e:
            self.logger.error(f"保存文本文件失败: {e}")

    def save_json(self):
        """保存JSON文件"""
        if self.config.save_to_json and self.json_data:
            json_path = self.output_dir / 'pages.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self.json_data, f, ensure_ascii=False, indent=2)

    def close(self):
        """关闭存储"""
        if self.config.save_to_csv:
            self.csv_file.close()
        if self.config.save_to_json:
            self.save_json()


# ============================================================
# 爬虫核心
# ============================================================

class WebCrawler:
    """Web爬虫核心"""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.url_manager = URLManager(config)
        self.parser = PageParser()
        self.storage = DataStorage(config)
        self.logger = logging.getLogger('WebCrawler')
        self.session = requests.Session()

        # 统计
        self.stats = {
            'pages_crawled': 0,
            'pages_failed': 0,
            'total_links': 0,
            'total_images': 0,
            'start_time': None,
            'end_time': None
        }

        # 配置session
        self.session.headers.update(config.headers)

    def start(self):
        """开始爬取"""
        self.stats['start_time'] = datetime.now().isoformat()
        self.logger.info(f"开始爬取，起始URL: {self.config.start_urls}")

        # 添加起始URL
        for url in self.config.start_urls:
            self.url_manager.add_url(url, depth=0)

        # 使用线程池
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = []

            while self.url_manager.queue_size > 0:
                # 检查是否达到最大页面数
                if self.stats['pages_crawled'] >= self.config.max_pages:
                    self.logger.info(f"已达到最大页面数 {self.config.max_pages}")
                    break

                # 获取URL
                url_info = self.url_manager.get_url()
                if not url_info:
                    break

                url, depth, parent = url_info

                # 跳过已访问的URL
                if self.url_manager.is_visited(url):
                    continue

                # 提交任务
                future = executor.submit(self._crawl_page, url, depth, parent)
                futures.append(future)

                # 等待并处理结果
                if len(futures) >= self.config.max_workers:
                    for future in as_completed(futures):
                        try:
                            page = future.result()
                            if page:
                                self._process_page(page)
                        except Exception as e:
                            self.logger.error(f"处理结果失败: {e}")
                    futures = []

                # 延迟
                time.sleep(self.config.delay_between_requests)

            # 处理剩余的futures
            for future in as_completed(futures):
                try:
                    page = future.result()
                    if page:
                        self._process_page(page)
                except Exception as e:
                    self.logger.error(f"处理结果失败: {e}")

        self.stats['end_time'] = datetime.now().isoformat()
        self._print_stats()
        self.storage.close()

    def _crawl_page(self, url: str, depth: int, parent: str) -> Optional[PageInfo]:
        """爬取单个页面"""
        for retry in range(self.config.max_retries):
            try:
                # 随机User-Agent
                user_agent = self.config.user_agents[retry % len(self.config.user_agents)]
                headers = {'User-Agent': user_agent}

                # 随机代理
                proxies = None
                if self.config.proxies:
                    proxy = self.config.proxies[retry % len(self.config.proxies)]
                    proxies = {'http': proxy, 'https': proxy}

                # 发送请求
                response = self.session.get(
                    url,
                    headers=headers,
                    proxies=proxies,
                    timeout=self.config.request_timeout,
                    allow_redirects=True
                )

                # 检查内容类型
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                    self.logger.debug(f"跳过非HTML内容: {url} ({content_type})")
                    return None

                # 解析页面
                page = self.parser.parse(
                    url, response.text, response.status_code, content_type
                )
                page.depth = depth
                page.parent_url = parent

                self.logger.info(f"爬取成功: {url} (深度={depth}, 状态={response.status_code})")
                return page

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"请求失败 (重试 {retry+1}/{self.config.max_retries}): {url} - {e}")
                if retry < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (retry + 1))
            except Exception as e:
                self.logger.error(f"爬取异常: {url} - {e}")
                break

        self.stats['pages_failed'] += 1
        return None

    def _process_page(self, page: PageInfo):
        """处理爬取的页面"""
        # 标记已访问
        self.url_manager.mark_visited(page.url)

        # 保存数据
        self.storage.save_page(page)

        # 更新统计
        self.stats['pages_crawled'] += 1
        self.stats['total_links'] += len(page.links)
        self.stats['total_images'] += len(page.images)

        # 添加新链接到队列
        for link in page.links:
            self.url_manager.add_url(link, depth=page.depth + 1, parent=page.url)

    def _print_stats(self):
        """打印统计信息"""
        self.logger.info("=" * 50)
        self.logger.info("爬取完成！统计信息：")
        self.logger.info(f"  爬取页面数: {self.stats['pages_crawled']}")
        self.logger.info(f"  失败页面数: {self.stats['pages_failed']}")
        self.logger.info(f"  总链接数: {self.stats['total_links']}")
        self.logger.info(f"  总图片数: {self.stats['total_images']}")
        self.logger.info(f"  开始时间: {self.stats['start_time']}")
        self.logger.info(f"  结束时间: {self.stats['end_time']}")
        self.logger.info("=" * 50)


# ============================================================
# Web UI
# ============================================================

class CrawlerWebUI:
    """爬虫Web监控界面"""

    def __init__(self, crawler: WebCrawler, port: int = 8088):
        self.crawler = crawler
        self.port = port
        self.logger = logging.getLogger('WebUI')

    def start(self):
        """启动Web UI"""
        try:
            from flask import Flask, render_template_string, jsonify
            app = Flask(__name__)

            HTML_TEMPLATE = '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>爬虫监控</title>
                <meta charset="utf-8">
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
                    .container { max-width: 1200px; margin: 0 auto; }
                    .card { background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
                    .stat-item { text-align: center; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px; }
                    .stat-value { font-size: 2em; font-weight: bold; }
                    .stat-label { font-size: 0.9em; opacity: 0.9; }
                    table { width: 100%; border-collapse: collapse; }
                    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
                    th { background: #667eea; color: white; }
                    tr:hover { background: #f5f5f5; }
                    .refresh-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
                    .refresh-btn:hover { background: #5568d3; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🕷️ 爬虫实时监控</h1>
                    <div class="card">
                        <div class="stats">
                            <div class="stat-item">
                                <div class="stat-value" id="pages-crawled">{{ stats.pages_crawled }}</div>
                                <div class="stat-label">已爬取页面</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value" id="pages-failed">{{ stats.pages_failed }}</div>
                                <div class="stat-label">失败页面</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value" id="total-links">{{ stats.total_links }}</div>
                                <div class="stat-label">总链接数</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value" id="queue-size">{{ queue_size }}</div>
                                <div class="stat-label">队列大小</div>
                            </div>
                        </div>
                    </div>
                    <div class="card">
                        <h2>最近爬取的页面</h2>
                        <button class="refresh-btn" onclick="refresh()">刷新</button>
                        <table>
                            <thead>
                                <tr>
                                    <th>URL</th>
                                    <th>标题</th>
                                    <th>状态</th>
                                    <th>深度</th>
                                    <th>链接数</th>
                                </tr>
                            </thead>
                            <tbody id="pages-table">
                                {% for page in recent_pages %}
                                <tr>
                                    <td><a href="{{ page.url }}" target="_blank">{{ page.url[:50] }}...</a></td>
                                    <td>{{ page.title[:30] }}</td>
                                    <td>{{ page.status_code }}</td>
                                    <td>{{ page.depth }}</td>
                                    <td>{{ page.links|length }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
                <script>
                    function refresh() {
                        fetch('/api/stats')
                            .then(response => response.json())
                            .then(data => {
                                document.getElementById('pages-crawled').textContent = data.stats.pages_crawled;
                                document.getElementById('pages-failed').textContent = data.stats.pages_failed;
                                document.getElementById('total-links').textContent = data.stats.total_links;
                                document.getElementById('queue-size').textContent = data.queue_size;
                            });
                    }
                    setInterval(refresh, 5000);
                </script>
            </body>
            </html>
            '''

            @app.route('/')
            def index():
                recent_pages = self.crawler.storage.json_data[-20:] if self.crawler.storage.json_data else []
                return render_template_string(
                    HTML_TEMPLATE,
                    stats=self.crawler.stats,
                    queue_size=self.crawler.url_manager.queue_size,
                    recent_pages=recent_pages
                )

            @app.route('/api/stats')
            def api_stats():
                return jsonify({
                    'stats': self.crawler.stats,
                    'queue_size': self.crawler.url_manager.queue_size,
                    'visited_count': self.crawler.url_manager.visited_count
                })

            self.logger.info(f"Web UI 启动在 http://localhost:{self.port}")
            app.run(port=self.port, debug=False, threaded=True)

        except ImportError:
            self.logger.warning("Flask未安装，Web UI不可用。运行: pip install flask")


# ============================================================
# 主函数
# ============================================================

def setup_logging(config: CrawlerConfig):
    """配置日志"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format=log_format,
        handlers=[
            logging.FileHandler(config.log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def load_config(config_file: str = None) -> CrawlerConfig:
    """加载配置"""
    config = CrawlerConfig()

    if config_file and os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)

    return config

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='一键爬虫')
    parser.add_argument('urls', nargs='*', help='起始URL')
    parser.add_argument('-c', '--config', help='配置文件')
    parser.add_argument('-d', '--depth', type=int, default=3, help='最大深度')
    parser.add_argument('-p', '--pages', type=int, default=1000, help='最大页面数')
    parser.add_argument('-w', '--workers', type=int, default=5, help='线程数')
    parser.add_argument('-o', '--output', default='./output', help='输出目录')
    parser.add_argument('--web', action='store_true', help='启动Web UI')
    parser.add_argument('--port', type=int, default=8088, help='Web UI端口')
    parser.add_argument('--json', action='store_true', help='保存JSON')
    parser.add_argument('--csv', action='store_true', help='保存CSV')
    parser.add_argument('--db', action='store_true', help='保存SQLite')
    parser.add_argument('--html', action='store_true', help='保存HTML文件')

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 命令行参数覆盖
    if args.urls:
        config.start_urls = args.urls
    if args.depth:
        config.max_depth = args.depth
    if args.pages:
        config.max_pages = args.pages
    if args.workers:
        config.max_workers = args.workers
    if args.output:
        config.output_dir = args.output
    if args.json:
        config.save_to_json = True
    if args.csv:
        config.save_to_csv = True
    if args.db:
        config.save_to_db = True
    if args.html:
        config.save_html = True

    # 检查URL
    if not config.start_urls:
        print("错误：请提供至少一个起始URL")
        print("用法：python crawler.py https://example.com")
        return

    # 配置日志
    setup_logging(config)

    # 创建爬虫
    crawler = WebCrawler(config)

    # 启动Web UI（如果需要）
    if args.web:
        web_ui = CrawlerWebUI(crawler, args.port)
        import threading
        web_thread = threading.Thread(target=web_ui.start, daemon=True)
        web_thread.start()

    # 开始爬取
    crawler.start()


if __name__ == '__main__':
    main()
