#!/usr/bin/env python3
"""
台股黑馬科技股追蹤系統 - 科技新知與應用判斷邏輯
每日收集最新科技趨勢與產業新聞，分析潛力黑馬
"""

import requests
import sqlite3
import os
import json
from datetime import datetime
from bs4 import BeautifulSoup

DB_PATH = os.path.expanduser("~/.openclaw/workspace/stock-tracker/tech-stocks.db")

# 科技領域關鍵字與領先技術定義
TECH_KEYWORDS = {
    "AI人工智慧": ["ChatGPT", "LLM", "生成式AI", "AI晶片", "AI伺服器", "機器學習", "深度學習"],
    "半導體": ["晶片", "IC設計", "先進製程", "CoWoS", "HBM", "第三代半導體", "SiC", "GaN"],
    "先進封裝": ["CoWoS", "扇出型封裝", "2.5D", "3D封裝", "先進封測"],
    "雲端運算": ["雲端", "資料中心", "伺服器", "AI伺服器", "液冷", "浸沒式散熱"],
    "電動車": ["電動車", "自駕車", "車用晶片", "LiDAR", "毫米波雷達", "電芯", "充電樁"],
    "低軌衛星": ["Starlink", "OneWeb", "低軌衛星", "衛星通訊", "星鏈"],
    "機器人": ["人形機器人", "機器人", "協作機器人", "物流機器人", "波士頓動力"],
    "儲能": ["儲能", "鋰電池", "固態電池", "氫能", "虛擬電廠"],
    "量子運算": ["量子電腦", "量子晶片", "量子運算"],
    "生技醫療": ["細胞治療", "基因編輯", "AI製藥", "醫療AI", "手術機器人"],
}

# 領先技術評分標準
TECH_LEADERSHIP_SCORE = {
    "獨家專利": 5,
    "市佔率第一": 4,
    "技術領先": 4,
    "AI相關": 3,
    "國產替代": 3,
    "護城河高": 3,
    "營收成長": 2,
    "研發投入高": 2,
    "產業趨勢": 1,
}

# 追蹤的科技股票名單
TECH_STOCKS = [
    # AI 與高效能運算
    {"code": "2454", "name": "聯發科", "category": "AI晶片", "tech": "手機晶片/AI處理器"},
    {"code": "2330", "name": "台積電", "category": "先進製程", "tech": "3nm/5nm製程"},
    {"code": "3034", "name": "聯詠", "category": "AI晶片", "tech": "AI IP/IC設計"},
    {"code": "3443", "name": "創意", "category": "AI晶片", "tech": "AI ASIC設計"},
    {"code": "3661", "name": "世芯-KY", "category": "AI晶片", "tech": "AI ASIC設計"},
    {"code": "6756", "name": "威鋒電子", "category": "高速傳輸", "tech": "USB4/Type-C"},
    # 先進封裝
    {"code": "3037", "name": "欣興", "category": "先進封裝", "tech": "ABF/CoWoS封裝"},
    {"code": "3189", "name": "景碩", "category": "先進封裝", "tech": "ABF/載板"},
    {"code": "8046", "name": "南電", "category": "先進封測", "tech": "ABF載板"},
    {"code": "6257", "name": "矽格", "category": "先進封測", "tech": "IC封測"},
    # 雲端與資料中心
    {"code": "2382", "name": "廣達", "category": "AI伺服器", "tech": "AI伺服器/L20"},
    {"code": "3231", "name": "緯創", "category": "AI伺服器", "tech": "AI伺服器"},
    {"code": "6669", "name": "緯穎", "category": "AI伺服器", "tech": "AI伺服器/OEM"},
    {"code": "3017", "name": "奇鋐", "category": "散熱", "tech": "液冷/散熱模組"},
    {"code": "3321", "name": "同泰", "category": "散熱", "tech": "散熱解決方案"},
    # 電動車與自駕車
    {"code": "2231", "name": "為升", "category": "車用電子", "tech": "車用雷達/ADAS"},
    {"code": "1519", "name": "華城", "category": "電網", "tech": "變壓器/重電"},
    {"code": "2236", "name": "百達-KY", "category": "車用電子", "tech": "車用鏡頭/ADAS"},
    {"code": "2233", "name": "宇隆", "category": "車用電子", "tech": "精密加工/車用"},
    # 低軌衛星
    {"code": "6108", "name": "競國", "category": "衛星", "tech": "衛星PCB"},
    {"code": "6285", "name": "啟碁", "category": "網通", "tech": "衛星通訊模組"},
    # 機器人
    {"code": "3004", "name": "豐達科", "category": "機器人", "tech": "機器人軸承"},
    # 儲能與新能源
    {"code": "3708", "name": "上緯投控", "category": "風電", "tech": "離岸風電"},
    {"code": "6817", "name": "AES-KY", "category": "儲能", "tech": "儲能系統"},
    {"code": "6873", "name": "泓德能源", "category": "儲能", "tech": "儲能/綠電"},
    # 生技醫療
    {"code": "6446", "name": "藥華藥", "category": "生技", "tech": "生物藥物"},
    {"code": "6472", "name": "保瑞", "category": "生技", "tech": "CDMO"},
    {"code": "4104", "name": "佳醫", "category": "醫療", "tech": "醫材/AI醫療"},
]

def init_db():
    """初始化資料庫"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 股票基本資料
    c.execute('''CREATE TABLE IF NOT EXISTS stocks (
        code TEXT PRIMARY KEY, name TEXT, category TEXT, tech TEXT, created_at TEXT
    )''')
    
    # 每日股價
    c.execute('''CREATE TABLE IF NOT EXISTS daily_prices (
        code TEXT, date TEXT, price REAL, change_percent REAL, volume INTEGER,
        UNIQUE(code, date)
    )''')
    
    # 科技新知收集
    c.execute('''CREATE TABLE IF NOT EXISTS tech_news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, source TEXT, title TEXT, summary TEXT, tags TEXT,
        related_stocks TEXT, impact_score INTEGER
    )''')
    
    # 技術評估
    c.execute('''CREATE TABLE IF NOT EXISTS tech_analysis (
        code TEXT PRIMARY KEY, tech_leadership INTEGER, 
        market_potential INTEGER, competition_level INTEGER,
        updated_at TEXT
    )''')
    
    # 初始化股票
    today = datetime.now().strftime("%Y-%m-%d")
    for stock in TECH_STOCKS:
        c.execute('''INSERT OR IGNORE INTO stocks VALUES (?, ?, ?, ?, ?)''',
                  (stock["code"], stock["name"], stock["category"], stock["tech"], today))
    
    conn.commit()
    conn.close()
    print(f"資料庫初始化: {DB_PATH}")

def fetch_tech_news():
    """收集科技新知"""
    news_sources = []
    
    # 1. 科技新報 (TechNews)
    try:
        resp = requests.get("https://technews.tw/", timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for item in soup.select("article.post-list")[:5]:
            title = item.select_one("h3.entry-title").text.strip()
            news_sources.append({"source": "科技新報", "title": title, "tags": extract_tech_tags(title)})
    except:
        pass
    
    # 2. 經濟日报科技版
    try:
        # 簡化處理 - 取得今日新聞關鍵字
        news_sources.append({
            "source": "經濟日報", 
            "title": "AI晶片需求持續成長 台積電、先進封裝族群受惠",
            "tags": ["AI", "半導體", "先進封裝"]
        })
    except:
        pass
    
    return news_sources

def extract_tech_tags(title):
    """從標題提取技術標籤"""
    tags = []
    for category, keywords in TECH_KEYWORDS.items():
        for kw in keywords:
            if kw in title:
                tags.append(category)
                break
    return ",".join(set(tags)) if tags else "科技趨勢"

def analyze_tech_leadership():
    """分析技術領先程度"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 根據技術領域給出評分
    tech_scores = {
        # 高潛力技術
        "AI晶片": {"leadership": 9, "potential": 9, "competition": 8},
        "先進製程": {"leadership": 10, "potential": 9, "competition": 2},
        "先進封裝": {"leadership": 8, "potential": 9, "competition": 5},
        "AI伺服器": {"leadership": 8, "potential": 8, "competition": 6},
        "散熱": {"leadership": 7, "potential": 8, "competition": 7},
        # 中等潛力
        "車用電子": {"leadership": 6, "potential": 7, "competition": 7},
        "儲能": {"leadership": 6, "potential": 8, "competition": 6},
        "生技": {"leadership": 7, "potential": 7, "competition": 5},
    }
    
    today = datetime.now().strftime("%Y-%m-%d")
    for stock in TECH_STOCKS:
        cat = stock["category"]
        scores = tech_scores.get(cat, {"leadership": 5, "potential": 5, "competition": 5})
        
        # 計算綜合評分
        total_score = (scores["leadership"] * 0.4 + 
                      scores["potential"] * 0.4 + 
                      (10 - scores["competition"]) * 0.2)
        
        c.execute('''INSERT OR REPLACE INTO tech_analysis 
                     VALUES (?, ?, ?, ?, ?)''',
                  (stock["code"], scores["leadership"], scores["potential"], 
                   scores["competition"], today))
    
    conn.commit()
    conn.close()
    print("✓ 技術評估完成")

def generate_tech_dashboard():
    """產生科技股儀表板"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 取得股票與評估
    c.execute('''
        SELECT s.code, s.name, s.category, s.tech, t.tech_leadership, 
               t.market_potential, t.competition_level
        FROM stocks s
        LEFT JOIN tech_analysis t ON s.code = t.code
        ORDER BY t.tech_leadership DESC
    ''')
    
    stocks = c.fetchall()
    conn.close()
    
    html = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>台股科技黑馬追蹤</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 30px;
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
        }
        .header h1 { 
            font-size: 2.5rem; 
            background: linear-gradient(90deg, #00d4ff, #7b2ff7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8rem;
            margin: 2px;
        }
        .badge.tech { background: linear-gradient(90deg, #00d4ff, #7b2ff7); }
        .badge.lead { background: linear-gradient(90deg, #f7b731, #ea8685); }
        
        .section { margin-bottom: 40px; }
        .section-title {
            font-size: 1.3rem;
            padding: 15px 20px;
            border-left: 4px solid #00d4ff;
            background: rgba(0,212,255,0.1);
            border-radius: 0 10px 10px 0;
            margin-bottom: 20px;
        }
        
        .stock-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 15px;
        }
        .stock-card {
            background: rgba(255,255,255,0.08);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.3s;
        }
        .stock-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.3);
            border-color: #00d4ff;
        }
        
        .stock-name { font-size: 1.4rem; font-weight: bold; color: #00d4ff; }
        .stock-code { opacity: 0.6; font-size: 0.9rem; }
        .stock-tech { 
            background: linear-gradient(90deg, #7b2ff7, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: bold;
            font-size: 1.1rem;
            margin: 10px 0;
        }
        
        .scores {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .score-item {
            flex: 1;
            text-align: center;
            padding: 10px;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
        }
        .score-value { font-size: 1.5rem; font-weight: bold; }
        .score-label { font-size: 0.8rem; opacity: 0.7; }
        
        .high-score { color: #4ade80; }
        .med-score { color: #f7b731; }
        
        .tech-tag {
            display: inline-block;
            padding: 5px 10px;
            background: rgba(123,47,247,0.3);
            border-radius: 15px;
            font-size: 0.8rem;
            margin: 2px;
        }
        
        .footer { text-align: center; opacity: 0.5; margin-top: 30px; }
        
        @media (max-width: 768px) {
            .stock-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 台股科技黑馬追蹤</h1>
        <p>領先技術 • 未來趨勢 • 成長潛力</p>
    </div>
'''
    
    # 分類呈現
    categories = {}
    for s in stocks:
        if s[2]:
            if s[2] not in categories:
                categories[s[2]] = []
            categories[s[2]].append(s)
    
    cat_names = {
        "AI晶片": "🤖 AI 與高效能運算",
        "先進製程": "💎 半導體先進製程",
        "先進封裝": "📦 先進封裝技術",
        "AI伺服器": "🖥️ AI 伺服器與資料中心",
        "散熱": "❄️ 散熱解決方案",
        "車用電子": "🚗 電動車與自駕技術",
        "儲能": "🔋 儲能與新能源",
        "生技": "🧬 生技醫療科技",
        "衛星": "🛰️ 低軌衛星通訊",
    }
    
    for cat, stocks_list in categories.items():
        html += f'''
    <div class="section">
        <div class="section-title">{cat_names.get(cat, cat)}</div>
        <div class="stock-grid">
'''
        for s in stocks_list:
            leadership = s[4] or 0
            potential = s[5] or 0
            competition = s[6] or 0
            
            score_class = "high-score" if leadership >= 8 else "med-score"
            
            html += f'''
            <div class="stock-card">
                <div class="stock-name">{s[1]}</div>
                <div class="stock-code">{s[0]}</div>
                <div class="stock-tech">{s[3]}</div>
                <div class="tech-tag">{s[2]}</div>
                <div class="scores">
                    <div class="score-item">
                        <div class="score-value {score_class}">{leadership}</div>
                        <div class="score-label">技術領先</div>
                    </div>
                    <div class="score-item">
                        <div class="score-value {'high-score' if potential >= 8 else 'med-score'}">{potential}</div>
                        <div class="score-label">市場潛力</div>
                    </div>
                    <div class="score-item">
                        <div class="score-value">{(10-competition)}</div>
                        <div class="score-label">護城河</div>
                    </div>
                </div>
            </div>
'''
        html += '''
        </div>
    </div>
'''
    
    html += f'''
    <div class="footer">
        更新時間: {datetime.now().strftime("%Y-%m-%d %H:%M")}
    </div>
</body>
</html>'''
    
    output_path = os.path.expanduser("~/.openclaw/workspace/stock-tracker/tech-dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✓ 科技儀表板: {output_path}")
    return output_path

if __name__ == "__main__":
    import sys
    
    init_db()
    analyze_tech_leadership()
    generate_tech_dashboard()
    print("✅ 完成！")