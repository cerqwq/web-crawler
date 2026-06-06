"""
爬虫Web监控界面 - 美化版
"""

from flask import Flask, render_template_string, jsonify
from datetime import datetime

app = Flask(__name__)

# 全局爬虫实例
crawler = None

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🕷️ 爬虫监控中心</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        /* 头部 */
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }

        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }

        /* 统计卡片 */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.2);
        }

        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }

        .stat-icon {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }

        .stat-label {
            color: #666;
            font-size: 0.95em;
        }

        /* 分类卡片 */
        .categories-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .category-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }

        .category-card:hover {
            transform: translateY(-3px);
        }

        .category-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }

        .category-icon {
            font-size: 2em;
            margin-right: 15px;
        }

        .category-title {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
        }

        .category-count {
            margin-left: auto;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        }

        .category-items {
            max-height: 200px;
            overflow-y: auto;
        }

        .category-item {
            padding: 10px;
            border-bottom: 1px solid #f5f5f5;
            display: flex;
            align-items: center;
        }

        .category-item:last-child {
            border-bottom: none;
        }

        .category-item a {
            color: #667eea;
            text-decoration: none;
            word-break: break-all;
            flex: 1;
        }

        .category-item a:hover {
            text-decoration: underline;
        }

        /* 表格 */
        .table-container {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }

        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .table-title {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
        }

        .refresh-btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .refresh-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 500;
        }

        th:first-child {
            border-radius: 10px 0 0 0;
        }

        th:last-child {
            border-radius: 0 10px 0 0;
        }

        td {
            padding: 12px 15px;
            border-bottom: 1px solid #f0f0f0;
        }

        tr:hover {
            background: #f8f9ff;
        }

        tr:last-child td:first-child {
            border-radius: 0 0 0 10px;
        }

        tr:last-child td:last-child {
            border-radius: 0 0 10px 0;
        }

        .url-cell {
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .url-cell a {
            color: #667eea;
            text-decoration: none;
        }

        .url-cell a:hover {
            text-decoration: underline;
        }

        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
        }

        .status-200 {
            background: #d4edda;
            color: #155724;
        }

        .status-error {
            background: #f8d7da;
            color: #721c24;
        }

        /* 进度条 */
        .progress-container {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }

        .progress-bar {
            height: 20px;
            background: #f0f0f0;
            border-radius: 10px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 10px;
            transition: width 0.5s ease;
            position: relative;
        }

        .progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(
                90deg,
                transparent,
                rgba(255,255,255,0.3),
                transparent
            );
            animation: shimmer 2s infinite;
        }

        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        /* 加载动画 */
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }

        .loading.active {
            display: block;
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* 响应式 */
        @media (max-width: 768px) {
            .header h1 {
                font-size: 1.8em;
            }

            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .categories-grid {
                grid-template-columns: 1fr;
            }

            table {
                font-size: 0.9em;
            }

            th, td {
                padding: 10px;
            }
        }

        /* 空状态 */
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }

        .empty-state-icon {
            font-size: 3em;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <h1>🕷️ 爬虫监控中心</h1>
            <p id="last-update">实时监控爬虫状态</p>
        </div>

        <!-- 统计卡片 -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">📄</div>
                <div class="stat-value" id="pages-crawled">0</div>
                <div class="stat-label">已爬取页面</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">❌</div>
                <div class="stat-value" id="pages-failed">0</div>
                <div class="stat-label">失败页面</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔗</div>
                <div class="stat-value" id="total-links">0</div>
                <div class="stat-label">总链接数</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🖼️</div>
                <div class="stat-value" id="total-images">0</div>
                <div class="stat-label">总图片数</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📥</div>
                <div class="stat-value" id="queue-size">0</div>
                <div class="stat-label">队列大小</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">✅</div>
                <div class="stat-value" id="visited-count">0</div>
                <div class="stat-label">已访问</div>
            </div>
        </div>

        <!-- 进度条 -->
        <div class="progress-container">
            <div class="progress-header">
                <span>爬取进度</span>
                <span id="progress-text">0%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
            </div>
        </div>

        <!-- 分类统计 -->
        <div class="categories-grid">
            <div class="category-card">
                <div class="category-header">
                    <div class="category-icon">🎬</div>
                    <div class="category-title">视频</div>
                    <div class="category-count" id="video-count">0</div>
                </div>
                <div class="category-items" id="video-list">
                    <div class="empty-state">
                        <div class="empty-state-icon">🎬</div>
                        <div>暂无视频</div>
                    </div>
                </div>
            </div>

            <div class="category-card">
                <div class="category-header">
                    <div class="category-icon">🎵</div>
                    <div class="category-title">音频</div>
                    <div class="category-count" id="audio-count">0</div>
                </div>
                <div class="category-items" id="audio-list">
                    <div class="empty-state">
                        <div class="empty-state-icon">🎵</div>
                        <div>暂无音频</div>
                    </div>
                </div>
            </div>

            <div class="category-card">
                <div class="category-header">
                    <div class="category-icon">🖼️</div>
                    <div class="category-title">图片</div>
                    <div class="category-count" id="image-count">0</div>
                </div>
                <div class="category-items" id="image-list">
                    <div class="empty-state">
                        <div class="empty-state-icon">🖼️</div>
                        <div>暂无图片</div>
                    </div>
                </div>
            </div>

            <div class="category-card">
                <div class="category-header">
                    <div class="category-icon">📄</div>
                    <div class="category-title">文档</div>
                    <div class="category-count" id="doc-count">0</div>
                </div>
                <div class="category-items" id="doc-list">
                    <div class="empty-state">
                        <div class="empty-state-icon">📄</div>
                        <div>暂无文档</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 最近爬取的页面 -->
        <div class="table-container">
            <div class="table-header">
                <div class="table-title">📊 最近爬取的页面</div>
                <button class="refresh-btn" onclick="refreshData()">🔄 刷新</button>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>URL</th>
                        <th>标题</th>
                        <th>状态</th>
                        <th>深度</th>
                        <th>链接数</th>
                        <th>图片数</th>
                    </tr>
                </thead>
                <tbody id="pages-table">
                    <tr>
                        <td colspan="6">
                            <div class="empty-state">
                                <div class="empty-state-icon">📊</div>
                                <div>等待爬取...</div>
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- 加载提示 -->
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div>正在更新数据...</div>
        </div>
    </div>

    <script>
        // 刷新数据
        function refreshData() {
            const loading = document.getElementById('loading');
            loading.classList.add('active');

            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    updateStats(data);
                    loading.classList.remove('active');
                    document.getElementById('last-update').textContent =
                        '最后更新: ' + new Date().toLocaleTimeString();
                })
                .catch(error => {
                    console.error('Error:', error);
                    loading.classList.remove('active');
                });
        }

        // 更新统计数据
        function updateStats(data) {
            const stats = data.stats;

            // 更新统计卡片
            document.getElementById('pages-crawled').textContent = stats['已爬取'] || 0;
            document.getElementById('pages-failed').textContent = stats['失败'] || 0;
            document.getElementById('total-links').textContent = stats['总链接'] || 0;
            document.getElementById('total-images').textContent = stats['总图片'] || 0;
            document.getElementById('queue-size').textContent = data.queue_size || 0;
            document.getElementById('visited-count').textContent = data.visited_count || 0;

            // 更新进度条
            const maxPages = data.max_pages || 200;
            const progress = Math.min(100, ((stats['已爬取'] || 0) / maxPages) * 100);
            document.getElementById('progress-fill').style.width = progress + '%';
            document.getElementById('progress-text').textContent = Math.round(progress) + '%';

            // 更新分类统计
            const categories = ['视频', '音频', '图片', '文档'];
            const categoryIds = ['video', 'audio', 'image', 'doc'];

            categories.forEach((cat, index) => {
                const items = stats[cat] || [];
                const id = categoryIds[index];

                document.getElementById(id + '-count').textContent = items.length;

                const listEl = document.getElementById(id + '-list');
                if (items.length > 0) {
                    listEl.innerHTML = items.slice(-10).reverse().map(item => `
                        <div class="category-item">
                            <a href="${item.url}" target="_blank" title="${item.url}">
                                ${item.url.substring(0, 50)}${item.url.length > 50 ? '...' : ''}
                            </a>
                        </div>
                    `).join('');
                }
            });

            // 更新表格
            const pages = stats['最近页面'] || [];
            const tableBody = document.getElementById('pages-table');

            if (pages.length > 0) {
                tableBody.innerHTML = pages.slice(-20).reverse().map(page => `
                    <tr>
                        <td class="url-cell">
                            <a href="${page.url}" target="_blank" title="${page.url}">
                                ${page.url.substring(0, 40)}${page.url.length > 40 ? '...' : ''}
                            </a>
                        </td>
                        <td>${(page.title || '').substring(0, 30)}</td>
                        <td>
                            <span class="status-badge status-${page.status === 200 ? '200' : 'error'}">
                                ${page.status}
                            </span>
                        </td>
                        <td>${page.depth || 0}</td>
                        <td>${page.links || 0}</td>
                        <td>${page.images || 0}</td>
                    </tr>
                `).join('');
            }
        }

        // 自动刷新（每5秒）
        setInterval(refreshData, 5000);

        // 初始加载
        refreshData();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def api_stats():
    if crawler:
        return jsonify({
            'stats': crawler.stats,
            'queue_size': crawler.url_manager.queue_size if hasattr(crawler, 'url_manager') else 0,
            'visited_count': len(crawler.visited) if hasattr(crawler, 'visited') else 0,
            'max_pages': crawler.config.max_pages if hasattr(crawler, 'config') else 200
        })
    return jsonify({'stats': {}, 'queue_size': 0, 'visited_count': 0})

def start_web_ui(crawler_instance, port=8088):
    """启动Web UI"""
    global crawler
    crawler = crawler_instance
    print(f"🌐 Web监控界面启动在: http://localhost:{port}")
    app.run(port=port, debug=False, threaded=True)
