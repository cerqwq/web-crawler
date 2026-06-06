"""
一键爬虫 - 专业版（带美化Web界面）
"""

import os
import re
import json
import csv
import time
import hashlib
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# ============================================================
#   配置区
# ============================================================

MAX_PAGES = 200
MAX_DEPTH = 3
THREADS = 5
DELAY = 0.5
OUTPUT_DIR = "./output"
WEB_PORT = 8088

FILE_TYPES = {
    "视频": [".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".webm", ".m4v"],
    "音频": [".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma", ".m4a"],
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "文档": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"],
    "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
}


class ProCrawler:
    """专业爬虫 - 带Web界面"""

    def __init__(self, url, output_dir=OUTPUT_DIR):
        self.start_url = url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 分类目录
        for category in ["视频", "音频", "图片", "文档", "压缩包", "网页", "其他"]:
            (self.output_dir / category).mkdir(exist_ok=True)

        # 状态
        self.visited = set()
        self.queue = deque()
        self.is_running = False
        self.start_time = None

        # 统计（Web UI读取）
        self.stats = {
            "已爬取": 0,
            "失败": 0,
            "总链接": 0,
            "总图片": 0,
            "视频": [],
            "音频": [],
            "图片": [],
            "文档": [],
            "压缩包": [],
            "网页": [],
            "其他": [],
            "最近页面": [],
        }

        # 会话
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        })

    def start(self, enable_web=True):
        """开始爬取"""
        self.is_running = True
        self.start_time = datetime.now()

        print("=" * 50)
        print("🕷️  一键爬虫 - 专业版")
        print(f"📍 目标: {self.start_url}")
        print(f"📁 输出: {self.output_dir.absolute()}")
        print("=" * 50)
        print()

        # 启动Web UI
        if enable_web:
            from web_ui import start_web_ui
            web_thread = threading.Thread(
                target=start_web_ui,
                args=(self, WEB_PORT),
                daemon=True
            )
            web_thread.start()
            print(f"🌐 Web监控: http://localhost:{WEB_PORT}")
            print()

        # 添加起始URL
        self.queue.append((self.start_url, 0, ""))

        # 爬取循环
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = []

            while self.queue and self.stats["已爬取"] < MAX_PAGES and self.is_running:
                url, depth, parent = self.queue.popleft()

                if self._url_hash(url) in self.visited:
                    continue
                if depth > MAX_DEPTH:
                    continue

                self.visited.add(self._url_hash(url))

                future = executor.submit(self._crawl_one, url, depth)
                futures.append(future)

                if len(futures) >= THREADS:
                    for f in as_completed(futures):
                        try:
                            result = f.result()
                            if result:
                                self._process_result(result)
                        except Exception as e:
                            print(f"  ❌ 错误: {e}")
                    futures = []

                time.sleep(DELAY)

            # 处理剩余
            for f in as_completed(futures):
                try:
                    result = f.result()
                    if result:
                        self._process_result(result)
                except:
                    pass

        self.is_running = False
        self._save_results()
        self._print_summary()

    def stop(self):
        """停止爬取"""
        self.is_running = False

    def _crawl_one(self, url, depth):
        """爬取单个页面"""
        try:
            print(f"  🔄 爬取: {url[:60]}...")
            resp = self.session.get(url, timeout=15, allow_redirects=True)
            resp.encoding = resp.apparent_encoding or "utf-8"

            if resp.status_code == 200:
                print(f"  ✅ 成功: {url[:60]}")
                return {
                    "url": url,
                    "depth": depth,
                    "status": resp.status_code,
                    "content_type": resp.headers.get("Content-Type", ""),
                    "html": resp.text,
                }
            else:
                print(f"  ⚠️ 状态码 {resp.status_code}: {url[:60]}")
                self.stats["失败"] += 1
                return None

        except Exception as e:
            print(f"  ❌ 失败: {url[:60]} - {e}")
            self.stats["失败"] += 1
            return None

    def _process_result(self, result):
        """处理爬取结果"""
        url = result["url"]
        html = result["html"]
        depth = result["depth"]

        soup = BeautifulSoup(html, "html.parser")
        title = self._get_title(soup)
        text = self._get_text(soup)
        links = self._get_links(soup, url)
        images = self._get_images(soup, url)

        # 分类链接
        for link in links:
            category = self._classify_url(link)
            if category == "网页":
                url_hash = self._url_hash(link)
                if url_hash not in self.visited:
                    self.queue.append((link, depth + 1, url))
            else:
                self.stats[category].append({
                    "url": link,
                    "来源": url,
                    "标题": title,
                })

        # 分类图片
        for img in images:
            self.stats["图片"].append({
                "url": img,
                "来源": url,
                "标题": title,
            })

        # 保存网页
        self._save_page(url, title, text, html)

        # 更新统计
        self.stats["已爬取"] += 1
        self.stats["总链接"] += len(links)
        self.stats["总图片"] += len(images)

        # 记录最近页面
        self.stats["最近页面"].append({
            "url": url,
            "title": title,
            "status": result["status"],
            "depth": depth,
            "links": len(links),
            "images": len(images),
        })

        # 只保留最近50个
        if len(self.stats["最近页面"]) > 50:
            self.stats["最近页面"] = self.stats["最近页面"][-50:]

        print(f"  📄 [{title[:30]}] {len(links)}链接, {len(images)}图片")

    def _classify_url(self, url):
        """自动分类URL"""
        url_lower = url.lower()
        for category, extensions in FILE_TYPES.items():
            for ext in extensions:
                if url_lower.endswith(ext):
                    return category
        return "网页"

    def _get_title(self, soup):
        """获取标题"""
        title = soup.find("title")
        if title:
            return title.get_text(strip=True)
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return "无标题"

    def _get_text(self, soup):
        """获取正文"""
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    def _get_links(self, soup, base_url):
        """获取所有链接"""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            absolute = urljoin(base_url, href)
            if absolute.startswith("http"):
                links.append(absolute)
        return list(set(links))

    def _get_images(self, soup, base_url):
        """获取所有图片"""
        images = []
        for img in soup.find_all("img", src=True):
            src = img["src"]
            absolute = urljoin(base_url, src)
            if absolute.startswith("http"):
                images.append(absolute)
        return list(set(images))

    def _save_page(self, url, title, text, html):
        """保存网页"""
        parsed = urlparse(url)
        filename = parsed.netloc.replace(".", "_") + parsed.path.replace("/", "_").strip("_")
        if not filename:
            filename = "index"
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)[:100]

        # 保存文本
        text_path = self.output_dir / "网页" / f"{filename}.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(f"URL: {url}\n")
            f.write(f"标题: {title}\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            f.write(text)

        # 保存HTML
        html_path = self.output_dir / "网页" / f"{filename}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _save_results(self):
        """保存分类结果"""
        # 保存JSON
        json_path = self.output_dir / "爬取结果.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)

        # 保存CSV
        for category in ["视频", "音频", "图片", "文档", "压缩包"]:
            items = self.stats[category]
            if items:
                csv_path = self.output_dir / category / "列表.csv"
                with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["URL", "来源", "标题"])
                    for item in items:
                        writer.writerow([item["url"], item["来源"], item["标题"]])

        # 保存SQLite
        db_path = self.output_dir / "爬取结果.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS 资源 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                类型 TEXT,
                URL TEXT,
                来源 TEXT,
                标题 TEXT,
                爬取时间 TEXT
            )
        """)

        for category in ["视频", "音频", "图片", "文档", "压缩包"]:
            for item in self.stats[category]:
                cursor.execute(
                    "INSERT INTO 资源 (类型, URL, 来源, 标题, 爬取时间) VALUES (?, ?, ?, ?, ?)",
                    (category, item["url"], item["来源"], item["标题"], datetime.now().isoformat())
                )

        conn.commit()
        conn.close()

    def _print_summary(self):
        """打印总结"""
        print()
        print("=" * 50)
        print("🎉 爬取完成！")
        print("=" * 50)
        print(f"📊 统计:")
        print(f"   已爬取页面: {self.stats['已爬取']}")
        print(f"   失败页面: {self.stats['失败']}")
        print()
        print(f"📁 分类结果:")
        print(f"   🎬 视频: {len(self.stats['视频'])} 个")
        print(f"   🎵 音频: {len(self.stats['音频'])} 个")
        print(f"   🖼️  图片: {len(self.stats['图片'])} 个")
        print(f"   📄 文档: {len(self.stats['文档'])} 个")
        print(f"   📦 压缩包: {len(self.stats['压缩包'])} 个")
        print(f"   🌐 网页: {self.stats['已爬取']} 个")
        print()
        print(f"📁 输出目录: {self.output_dir.absolute()}")
        print(f"🌐 Web监控: http://localhost:{WEB_PORT}")
        print()
        print("📂 目录结构:")
        print(f"   {self.output_dir}/")
        print(f"   ├── 视频/     (自动分类)")
        print(f"   ├── 音频/     (自动分类)")
        print(f"   ├── 图片/     (自动分类)")
        print(f"   ├── 文档/     (自动分类)")
        print(f"   ├── 压缩包/   (自动分类)")
        print(f"   ├── 网页/     (HTML+文本)")
        print(f"   ├── 爬取结果.json")
        print(f"   └── 爬取结果.db")
        print("=" * 50)

    def _url_hash(self, url):
        """URL哈希"""
        return hashlib.md5(url.encode()).hexdigest()


# ============================================================
#   主函数
# ============================================================

def main():
    """主函数"""
    print()
    print("🕷️  一键爬虫 - 专业版（带Web界面）")
    print()

    url = input("请输入要爬取的网址: ").strip()
    if not url:
        print("❌ 网址不能为空！")
        input("按回车退出...")
        return

    if not url.startswith("http"):
        url = "https://" + url

    print()
    print("选择爬取模式:")
    print("  1. 快速模式 (50页, 深度2)")
    print("  2. 标准模式 (200页, 深度3)")
    print("  3. 完整模式 (500页, 深度4)")
    print()

    choice = input("请选择 (1/2/3, 默认2): ").strip()

    global MAX_PAGES, MAX_DEPTH
    if choice == "1":
        MAX_PAGES = 50
        MAX_DEPTH = 2
    elif choice == "3":
        MAX_PAGES = 500
        MAX_DEPTH = 4
    else:
        MAX_PAGES = 200
        MAX_DEPTH = 3

    print()
    print(f"设置: 最多{MAX_PAGES}页, 深度{MAX_DEPTH}层")
    print()
    print("🌐 Web监控界面将在爬取启动后自动打开")
    print(f"   地址: http://localhost:{WEB_PORT}")
    print()

    crawler = ProCrawler(url)
    crawler.start(enable_web=True)

    print()
    input("按回车退出...")


if __name__ == "__main__":
    main()
