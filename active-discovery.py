#!/usr/bin/env python3
"""
科技趨勢主動發現系統 - 有目的性地發掘新技術
定期、主動搜尋並分析新興技術趨勢與投資機會
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import os
import json
from datetime import datetime
from collections import defaultdict
import re

DB_PATH = os.path.expanduser("~/.openclaw/workspace/stock-tracker/active-discovery.db")

# ===== 有目的性的發掘目標 =====

# 1. 搜尋引擎 - 主动搜索新技术关键词
SEARCH_TARGETS = [
    # 新兴技术
    {"keyword": "CPO 矽光子", "category": "矽光子/CPO", "purpose": "找出供应链接和台股"},
    {"keyword": "HBM memory Taiwan", "category": "HBM记忆体", "purpose": "找出相关IC设计/封测"},
    {"keyword": "CoWoS 先进封装", "category": "先进封装", "purpose": "找出设备/材料供应商"},
    {"keyword": "量子电脑 台积电", "category": "量子运算", "purpose": "找出台湾供应链"},
    {"keyword": "AI晶片 ASIC 设计", "category": "AI晶片", "purpose": "找出IP/设计公司"},
    {"keyword": "固态电池 电动车", "category": "新能源车", "purpose": "找出电池/材料"},
    {"keyword": "液冷 浸没式散热", "category": "散热技术", "purpose": "找出散热供应商"},
    {"keyword": "低轨卫星 台厂", "category": "卫星通讯", "purpose": "找出地面设备商"},
]

# 2. 监控的新闻来源 - 有目的性地抓取
NEWS_SOURCES = [
    {"name": "TechNews", "url": "https://technews.tw/", "type": "科技媒体"},
    {"name": "DIGITIMES", "url": "https://digitimes.com.tw/", "type": "产业新闻"},
    {"name": "经济日报", "url": "https://money.udn.com/money/cate/1104", "type": "财经"},
    {"name": "工商时报", "url": "https://ctee.com.tw/", "type": "财经"},
]

# 3. 台湾相关股票代码库
TAIWAN_STOCKS = {
    # 矽光子/CPO
    "聯詠": "3034", "联咏": "3034", "光谱": "3035", "上詮": "3085",
    "华星光": "4976", "波若威": "5425", "众达": "4976",
    # HBM/记忆体
    "南亚科": "2408", "华邦电": "2344", "创意": "3443", "联发科": "2454",
    # 先进封装
    "欣兴": "3037", "景硕": "3189", "南电": "8046", "矽格": "6257",
    "台积电": "2330", "日月光": "3711", "京元电": "2449",
    # AI晶片
    "世芯": "3661", "威锋": "6756", "力旺": "3529", "晶心科": "6533",
    # 散热
    "奇鋐": "3017", "同泰": "3321", "双鸿": "3324", "泰硕": "6155",
    # 电动车
    "为升": "2231", "百达": "2236", "宇隆": "2233", "致伸": "4915",
    # 储能
    "AES-KY": "6817", "泓德能源": "6873", "上纬": "3708", "华城": "1519",
}

def init_db():
    """初始化发现数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 技术发现记录
    c.execute('''CREATE TABLE IF NOT EXISTS discoveries (
        id INTEGER PRIMARY KEY, date TEXT, keyword TEXT,
        category TEXT, source TEXT, title TEXT,
        summary TEXT, found_stocks TEXT, status TEXT
    )''')
    
    # 主动搜索任务
    c.execute('''CREATE TABLE IF NOT EXISTS search_tasks (
        id INTEGER PRIMARY KEY, keyword TEXT, category TEXT,
        purpose TEXT, last_searched TEXT, results_count INTEGER
    )''')
    
    # 发现追踪
    c.execute('''CREATE TABLE IF NOT EXISTS tech_tracking (
        tech_name TEXT PRIMARY KEY, category TEXT,
        discovery_date TEXT, relevance_score INTEGER,
        stocks_found TEXT, status TEXT
    )''')
    
    conn.commit()
    conn.close()
    print(f"✅ 主动发现系统初始化: {DB_PATH}")

def active_search(query, category, purpose):
    """有目的性的搜索"""
    results = []
    
    # 搜索关键词组合
    search_queries = [
        f"{query} 台湾",
        f"{query} 供应链",
        f"{query} 台积电",
        f"{query} 供应商",
    ]
    
    for sq in search_queries:
        try:
            # 使用 DuckDuckGo (无需API key)
            url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(sq)}"
            resp = requests.get(url, timeout=10, 
                              headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            
            for item in soup.select("a.result__a")[:5]:
                title = item.text.strip()
                href = item.get("href", "")
                
                # 提取关键资讯
                if any(kw in title for kw in ["台", "供应", "产", "公司", "晶片", "技术"]):
                    # 找出相关股票
                    found_stocks = []
                    for name, code in TAIWAN_STOCKS.items():
                        if name in title:
                            found_stocks.append(f"{name}({code})")
                    
                    results.append({
                        "keyword": query,
                        "category": category,
                        "purpose": purpose,
                        "title": title[:80],
                        "source": "search",
                        "stocks": ",".join(found_stocks) if found_stocks else "待查"
                    })
        except Exception as e:
            print(f"   ⚠️ 搜索 {sq}: {str(e)[:30]}")
            continue
    
    return results

def scan_tech_news():
    """扫描科技新闻来源"""
    discoveries = []
    
    for source in NEWS_SOURCES:
        try:
            resp = requests.get(source["url"], timeout=12,
                               headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 提取文章标题
            for item in soup.select("article h3, .title, h2")[:15]:
                title = item.text.strip()
                if len(title) > 10:
                    # 匹配关键词
                    for kw, cat, purpose in SEARCH_TARGETS:
                        if any(w in title for w in kw.split()):
                            # 找出股票
                            stocks = []
                            for name, code in TAIWAN_STOCKS.items():
                                if name in title:
                                    stocks.append(f"{name}({code})")
                            
                            discoveries.append({
                                "keyword": kw,
                                "category": cat,
                                "source": source["name"],
                                "title": title[:80],
                                "stocks": ",".join(stocks) if stocks else "待查"
                            })
        except Exception as e:
            print(f"   ⚠️ {source['name']}: {str(e)[:30]}")
    
    return discoveries

def save_discoveries(all_results):
    """保存发现结果"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    count = 0
    for r in all_results:
        c.execute('''INSERT INTO discoveries 
                    (date, keyword, category, source, title, summary, found_stocks, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (today, r.get("keyword", ""), r.get("category", ""),
                   r.get("source", ""), r.get("title", ""), 
                   r.get("purpose", ""), r.get("stocks", ""), "new"))
        count += 1
    
    conn.commit()
    conn.close()
    return count

def generate_discovery_report():
    """产生发现报告"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 最新发现
    c.execute('''SELECT keyword, category, source, title, found_stocks 
                 FROM discoveries ORDER BY date DESC, id DESC LIMIT 20''')
    
    discoveries = c.fetchall()
    
    # 按类别统计
    c.execute('''SELECT category, COUNT(*) as cnt FROM discoveries 
                 GROUP BY category ORDER BY cnt DESC''')
    
    categories = c.fetchall()
    conn.close()
    
    report = f"""
# 🔍 科技趋势主动发现报告
更新: {datetime.now().strftime("%Y-%m-%d %H:%M")}

## 发现概况
- 总发现数: {len(discoveries)}
- 类别分布:
"""
    for cat, cnt in categories:
        report += f"  - {cat}: {cnt} 项\n"
    
    report += "\n## 最新发现\n"
    
    for d in discoveries[:10]:
        stocks = d[4] if d[4] else "待查"
        report += f"""### [{d[1]}] {d[3]}
- 来源: {d[2]}
- 股票: {stocks}

"""
    
    return report

def generate_dashboard():
    """产生仪表板"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''SELECT category, COUNT(*) as cnt FROM discoveries 
                 GROUP BY category ORDER BY cnt DESC''')
    categories = c.fetchall()
    
    c.execute('''SELECT title, category, found_stocks FROM discoveries 
                 ORDER BY id DESC LIMIT 12''')
    items = c.fetchall()
    conn.close()
    
    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>科技趋势主动发现系统</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 25px;
            background: linear-gradient(90deg, #6366f1, #8b5cf6);
            border-radius: 15px;
            margin-bottom: 25px;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 20px 0;
        }}
        .stat-item {{
            text-align: center;
            padding: 15px 25px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }}
        .stat-num {{ font-size: 2rem; font-weight: bold; color: #8b5cf6; }}
        .stat-label {{ font-size: 0.9rem; opacity: 0.7; }}
        
        .category-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 25px;
            justify-content: center;
        }}
        .cat-badge {{
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            background: rgba(139, 92, 246, 0.3);
        }}
        
        .discovery-list {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 15px;
        }}
        .discovery-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 15px;
            border-left: 3px solid #8b5cf6;
        }}
        .discovery-title {{ font-size: 1rem; margin-bottom: 8px; }}
        .discovery-meta {{
            font-size: 0.8rem;
            opacity: 0.6;
            display: flex;
            justify-content: space-between;
        }}
        .stock-tag {{
            display: inline-block;
            padding: 3px 8px;
            background: #6366f1;
            border-radius: 4px;
            font-size: 0.75rem;
            margin: 5px 3px 0 0;
        }}
        
        .footer {{ text-align: center; opacity: 0.5; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 科技趋势主动发现系统</h1>
        <p>有目的性地发掘新技术与投资机会</p>
    </div>
    
    <div class="stats">
        <div class="stat-item">
            <div class="stat-num">{len(categories)}</div>
            <div class="stat-label">技术类别</div>
        </div>
        <div class="stat-item">
            <div class="stat-num">{sum([c[1] for c in categories])}</div>
            <div class="stat-label">总发现数</div>
        </div>
    </div>
    
    <div class="category-bar">
'''
    
    for cat, cnt in categories:
        html += f'        <span class="cat-badge">{cat} ({cnt})</span>\n'
    
    html += '''    </div>
    
    <div class="discovery-list">
'''
    
    for item in items:
        title = item[0][:50] + "..." if len(item[0]) > 50 else item[0]
        stocks = item[2] if item[2] else ""
        stock_tags = ""
        if stocks and stocks != "待查":
            for s in stocks.split(","):
                stock_tags += f'<span class="stock-tag">{s.strip()}</span>'
        
        html += f'''        <div class="discovery-card">
            <div class="discovery-title">{title}</div>
            <div class="discovery-meta">
                <span>{item[1]}</span>
            </div>
            {stock_tags}
        </div>
'''
    
    html += f'''    </div>
    <div class="footer">更新: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
</body>
</html>'''
    
    output = os.path.expanduser("~/.openclaw/workspace/stock-tracker/active-discovery.html")
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
    
    return output

if __name__ == "__main__":
    print("🚀 启动科技趋势主动发现系统...\n")
    
    init_db()
    
    print("\n📡 有目的地搜索目标:")
    for t in SEARCH_TARGETS[:5]:
        print(f"   • [{t['category']}] {t['keyword']} - {t['purpose']}")
    
    print("\n🔍 主动搜索中...")
    all_results = []
    
    # 1. 主动搜索关键术语
    for target in SEARCH_TARGETS[:6]:
        results = active_search(target["keyword"], target["category"], target["purpose"])
        if results:
            all_results.extend(results)
            print(f"   ✓ {target['category']}: {len(results)} 项")
    
    # 2. 扫描科技新闻
    print("\n📰 扫描科技新闻来源...")
    news_results = scan_tech_news()
    if news_results:
        all_results.extend(news_results)
        print(f"   ✓ 新闻发现: {len(news_results)} 项")
    
    # 3. 保存并产生报告
    if all_results:
        count = save_discoveries(all_results)
        print(f"\n✅ 共发现 {count} 项新技术趋势")
        
        report = generate_discovery_report()
        print(report)
        
        dashboard = generate_dashboard()
        print(f"\n📊 仪表板: {dashboard}")
    else:
        print("\n⚠️ 今日暂无新发现")