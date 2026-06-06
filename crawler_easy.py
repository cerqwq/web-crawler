"""
一键爬虫 - 小白版
自动分类：视频、图片、文本、文档、音频
双击 start_easy.bat 直接用
"""

import os
import re
import json
import csv
import time
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# ============================================================
#   AI 配置（Ollama 本地模型）
# ============================================================

# Ollama 服务地址
OLLAMA_URL = "http://localhost:11434/api/generate"
# 使用的模型
OLLAMA_MODEL = "qwen3.5:2b"
# AI 功能开关（设为 False 可关闭AI功能）
AI_ENABLED = True

# ============================================================
#   配置区（可修改）
# ============================================================

# 爬取设置
MAX_PAGES = 200        # 最多爬多少页
MAX_DEPTH = 3          # 最多爬几层
THREADS = 5            # 同时几个线程爬
DELAY = 0.5            # 每次请求间隔（秒）

# 输出目录
OUTPUT_DIR = "./output"

# 文件类型分类（自动识别）
FILE_TYPES = {
    "视频": [".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".webm", ".m4v"],
    "音频": [".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma", ".m4a"],
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "文档": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"],
    "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
}

# ============================================================
#   核心代码（不需要修改）
# ============================================================

class EasyCrawler:
    """一键爬虫 - 自动分类版"""

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
        self.stats = {
            "已爬取": 0,
            "失败": 0,
            "视频": [],
            "音频": [],
            "图片": [],
            "文档": [],
            "压缩包": [],
            "网页": [],
            "其他": [],
            "AI分析": [],  # 存储AI分析结果
        }

        # 会话
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        })

    def start(self):
        """开始爬取"""
        print("=" * 50)
        print("🕷️  一键爬虫启动")
        print(f"📍 目标: {self.start_url}")
        print(f"📁 输出: {self.output_dir.absolute()}")
        print("=" * 50)
        print()

        # 添加起始URL
        self.queue.append((self.start_url, 0, ""))

        # 爬取循环
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = []

            while self.queue and self.stats["已爬取"] < MAX_PAGES:
                url, depth, parent = self.queue.popleft()

                # 跳过已访问
                if self._url_hash(url) in self.visited:
                    continue

                # 检查深度
                if depth > MAX_DEPTH:
                    continue

                # 标记已访问
                self.visited.add(self._url_hash(url))

                # 提交爬取任务
                future = executor.submit(self._crawl_one, url, depth)
                futures.append(future)

                # 处理完成的任务
                if len(futures) >= THREADS:
                    for f in as_completed(futures):
                        try:
                            result = f.result()
                            if result:
                                self._process_result(result)
                        except Exception as e:
                            print(f"  ❌ 错误: {e}")
                    futures = []

                # 延迟
                time.sleep(DELAY)

            # 处理剩余任务
            for f in as_completed(futures):
                try:
                    result = f.result()
                    if result:
                        self._process_result(result)
                except:
                    pass

        # 保存结果
        self._save_results()
        self._print_summary()

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
        """处理爬取结果 - 自动分类"""
        url = result["url"]
        html = result["html"]
        depth = result["depth"]

        # 解析页面
        soup = BeautifulSoup(html, "html.parser")
        title = self._get_title(soup)
        text = self._get_text(soup)
        links = self._get_links(soup, url)
        images = self._get_images(soup, url)

        # 分类链接
        for link in links:
            category = self._classify_url(link)
            if category == "网页":
                # 添加到爬取队列
                url_hash = self._url_hash(link)
                if url_hash not in self.visited:
                    self.queue.append((link, depth + 1, url))
            else:
                # 记录资源
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

        # AI 分析（智能分类、摘要、关键词）
        ai_result = self._ai_analyze(title, text)

        # 保存AI分析结果到统计
        if ai_result and ai_result.get("分类"):
            self.stats["AI分析"].append({
                "url": url,
                "标题": title,
                "分类": ai_result["分类"],
                "摘要": ai_result["摘要"],
                "关键词": ai_result["关键词"],
            })

        # 保存网页
        self._save_page(url, title, text, html, ai_result)

        self.stats["已爬取"] += 1
        print(f"  📄 [{title[:30]}] {len(links)}链接, {len(images)}图片")
        if ai_result["分类"]:
            print(f"     AI分类: {ai_result['分类']} | 关键词: {ai_result['关键词']}")

    def _classify_url(self, url):
        """自动分类URL"""
        url_lower = url.lower()

        # 检查文件类型
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
        # 删除不需要的标签
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

    def _save_page(self, url, title, text, html, ai_result=None):
        """保存网页（含AI分析结果）"""
        # 生成文件名
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
            # 写入AI分析结果
            if ai_result and ai_result.get("分类"):
                f.write(f"AI分类: {ai_result['分类']}\n")
            if ai_result and ai_result.get("摘要"):
                f.write(f"AI摘要: {ai_result['摘要']}\n")
            if ai_result and ai_result.get("关键词"):
                f.write(f"AI关键词: {ai_result['关键词']}\n")
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

        # 保存CSV（每个分类一个）
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

        # 创建表
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

        # AI分析结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AI分析 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                URL TEXT,
                标题 TEXT,
                内容分类 TEXT,
                摘要 TEXT,
                关键词 TEXT,
                分析时间 TEXT
            )
        """)

        # 插入资源数据
        for category in ["视频", "音频", "图片", "文档", "压缩包"]:
            for item in self.stats[category]:
                cursor.execute(
                    "INSERT INTO 资源 (类型, URL, 来源, 标题, 爬取时间) VALUES (?, ?, ?, ?, ?)",
                    (category, item["url"], item["来源"], item["标题"], datetime.now().isoformat())
                )

        # 插入AI分析数据
        for item in self.stats["AI分析"]:
            cursor.execute(
                "INSERT INTO AI分析 (URL, 标题, 内容分类, 摘要, 关键词, 分析时间) VALUES (?, ?, ?, ?, ?, ?)",
                (item["url"], item["标题"], item["分类"], item["摘要"], item["关键词"], datetime.now().isoformat())
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
        print(f"   🤖 AI分析: {len(self.stats['AI分析'])} 个")
        print()
        print(f"📁 输出目录: {self.output_dir.absolute()}")
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
        print()
        print("💡 提示:")
        print("   - 每个分类目录下有 列表.csv 可用Excel打开")
        print("   - 爬取结果.db 可用SQLite浏览器查看")
        print("   - 网页目录下有HTML和文本两种格式")
        print("=" * 50)

    def _url_hash(self, url):
        """URL哈希"""
        return hashlib.md5(url.encode()).hexdigest()

    # ============================================================
    #   AI 分析功能（Ollama 本地模型）
    # ============================================================

    def _ask_ollama(self, prompt, max_tokens=300):
        """调用 Ollama 本地模型"""
        if not AI_ENABLED:
            return ""
        try:
            resp = requests.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.3,
                }
            }, timeout=60)
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
        except Exception as e:
            print(f"  ⚠️ AI调用失败: {e}")
        return ""

    def _ai_classify(self, title, text):
        """智能分类：用LLM判断网页内容类型"""
        # 截取正文前500字，节省token
        snippet = text[:500]
        prompt = f"""请判断以下网页属于什么类型，只回答一个词：
类型选项：新闻、商品、论坛、博客、文档、教程、视频、社交、下载、其他

标题：{title}
内容：{snippet}

类型："""
        result = self._ask_ollama(prompt, max_tokens=20)
        # 清理结果，只保留有效类型
        valid_types = ["新闻", "商品", "论坛", "博客", "文档", "教程", "视频", "社交", "下载", "其他"]
        for t in valid_types:
            if t in result:
                return t
        return "其他"

    def _ai_summarize(self, title, text):
        """自动总结：用LLM生成网页摘要"""
        snippet = text[:800]
        prompt = f"""请用一句简洁的中文总结以下网页内容（不超过50字）：

标题：{title}
内容：{snippet}

摘要："""
        result = self._ask_ollama(prompt, max_tokens=80)
        return result[:100] if result else ""

    def _ai_keywords(self, title, text):
        """关键词提取：提取网页关键词"""
        snippet = text[:500]
        prompt = f"""请从以下网页中提取3-5个关键词，用逗号分隔，只输出关键词：

标题：{title}
内容：{snippet}

关键词："""
        result = self._ask_ollama(prompt, max_tokens=50)
        return result if result else ""

    def _ai_analyze(self, title, text):
        """AI 综合分析：分类 + 摘要 + 关键词"""
        if not AI_ENABLED:
            return {"分类": "", "摘要": "", "关键词": ""}
        print(f"  🤖 AI分析中...")
        category = self._ai_classify(title, text)
        summary = self._ai_summarize(title, text)
        keywords = self._ai_keywords(title, text)
        return {
            "分类": category,
            "摘要": summary,
            "关键词": keywords,
        }


# ============================================================
#   主函数
# ============================================================

def main():
    """主函数"""
    print()
    print("🕷️  一键爬虫 - 自动分类版")
    if AI_ENABLED:
        print(f"🤖 AI功能已开启 (模型: {OLLAMA_MODEL})")
    print()

    # 获取URL
    url = input("请输入要爬取的网址: ").strip()
    if not url:
        print("❌ 网址不能为空！")
        input("按回车退出...")
        return

    # 添加协议
    if not url.startswith("http"):
        url = "https://" + url

    # 选择模式
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

    # 开始爬取
    crawler = EasyCrawler(url)
    crawler.start()

    print()
    input("按回车退出...")


if __name__ == "__main__":
    main()
