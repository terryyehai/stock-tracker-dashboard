#!/usr/bin/env python3
"""
台股黑馬追蹤系統 - 每日數據收集與資料庫管理
"""

import sqlite3
import requests
import json
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/.openclaw/workspace/stock-tracker/stocks.db")
STOCKS_TO_TRACK = [
    # 黑馬級別
    {"code": "2603", "name": "長榮", "category": "黑馬"},
    {"code": "1519", "name": "華城", "category": "黑馬"},
    {"code": "2371", "name": "大同", "category": "黑馬"},
    # 成長型
    {"code": "2630", "name": "亞航", "category": "成長"},
    {"code": "2498", "name": "宏達電", "category": "成長"},
    {"code": "6756", "name": "威鋒電子", "category": "成長"},
    # 高息型
    {"code": "1432", "name": "大魯閣", "category": "高息"},
    {"code": "2615", "name": "萬海", "category": "高息"},
    {"code": "2609", "name": "陽明", "category": "高息"},
    # 價值型
    {"code": "3708", "name": "上緯投控", "category": "價值"},
    {"code": "6488", "name": "帝寶", "category": "價值"},
]

def init_db():
    """初始化資料庫"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 建立股票基本資料表
    c.execute('''CREATE TABLE IF NOT EXISTS stocks (
        code TEXT PRIMARY KEY,
        name TEXT,
        category TEXT,
        created_at TEXT
    )''')
    
    # 建立每日股價資料表
    c.execute('''CREATE TABLE IF NOT EXISTS daily_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        date TEXT,
        price REAL,
        yield REAL,
        pe REAL,
        pb REAL,
        change_percent REAL,
        volume INTEGER,
        UNIQUE(code, date)
    )''')
    
    # 建立歷史記錄追蹤表
    c.execute('''CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        date TEXT,
        price REAL,
        change_1d REAL,
        change_5d REAL,
        change_20d REAL,
        UNIQUE(code, date)
    )''')
    
    # 初始化股票資料
    today = datetime.now().strftime("%Y-%m-%d")
    for stock in STOCKS_TO_TRACK:
        c.execute('''INSERT OR IGNORE INTO stocks (code, name, category, created_at) 
                     VALUES (?, ?, ?, ?)''', 
                  (stock["code"], stock["name"], stock["category"], today))
    
    conn.commit()
    conn.close()
    print(f"資料庫初始化完成: {DB_PATH}")

def fetch_twse_price(code):
    """從台灣證券交易所取得股價"""
    try:
        # 嘗試從TWSE取得最新報價
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={datetime.now().strftime('%Y%m%d')}&stockNo={code}&response=json"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        
        if data.get("stat") == "OK" and data.get("data"):
            for row in data["data"]:
                if row[0] == code:
                    return {
                        "code": code,
                        "price": float(row[2]) if row[2] != "-" else None,
                        "yield": float(row[3]) if row[3] != "-" else None,
                        "pe": float(row[5]) if row[5] != "-" else None,
                        "pb": float(row[6]) if row[6] != "-" else None,
                    }
        return None
    except Exception as e:
        print(f"取得 {code} 價格失敗: {e}")
        return None

def fetch_wantgoo_price(code):
    """從.wantgoo.com取得股價（備用）"""
    try:
        url = f"https://www.wantgoo.com/stock/quote/{code}"
        # 簡化處理
        return None
    except:
        return None

def collect_daily_data():
    """收集每日數據"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print(f"\n📊 開始收集 {today} 股價數據...")
    
    for stock in STOCKS_TO_TRACK:
        code = stock["code"]
        print(f"  取得 {code} {stock['name']}...", end=" ")
        
        data = fetch_twse_price(code)
        
        if data and data.get("price"):
            # 計算變動百分比（從資料庫取昨日資料計算）
            c.execute("SELECT price FROM daily_prices WHERE code = ? ORDER BY date DESC LIMIT 1", (code,))
            prev = c.fetchone()
            change = 0
            if prev and prev[0]:
                change = ((data["price"] - prev[0]) / prev[0]) * 100
            
            # 寫入資料庫
            c.execute('''INSERT OR REPLACE INTO daily_prices 
                         (code, date, price, yield, pe, pb, change_percent, volume)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                      (code, today, data["price"], data["yield"], data["pe"], data["pb"], change, 0))
            
            # 更新歷史記錄（計算多日變化）
            c.execute("SELECT price FROM daily_prices WHERE code = ? AND date < ? ORDER BY date DESC LIMIT 20", (code, today))
            prices = [row[0] for row in c.fetchall() if row[0]]
            
            change_1d = prices[0] - prices[0] if len(prices) > 0 else 0
            change_5d = ((prices[0] - prices[4]) / prices[4] * 100) if len(prices) > 4 else 0
            change_20d = ((prices[0] - prices[19]) / prices[19] * 100) if len(prices) > 19 else 0
            
            c.execute('''INSERT OR REPLACE INTO price_history
                         (code, date, price, change_1d, change_5d, change_20d)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (code, today, data["price"], 
                       ((data["price"] - prices[0]) / prices[0] * 100) if len(prices) > 0 else 0,
                       change_5d, change_20d))
            
            print(f"${data['price']} ✓")
        else:
            print("無法取得數據")
    
    conn.commit()
    conn.close()
    print("\n✅ 每日數據收集完成！")

def generate_html_dashboard():
    """產生互動式 HTML 儀表板"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 取得最新數據
    c.execute('''
        SELECT s.code, s.name, s.category, d.price, d.yield, d.pe, d.pb, d.change_percent,
               h.change_1d, h.change_5d, h.change_20d
        FROM stocks s
        LEFT JOIN daily_prices d ON s.code = d.code
        LEFT JOIN (
            SELECT code, MAX(date) as max_date FROM daily_prices GROUP BY code
        ) latest ON s.code = latest.code AND d.date = latest.max_date
        LEFT JOIN price_history h ON s.code = h.code AND d.date = h.date
        ORDER BY s.category, s.name
    ''')
    
    stocks_data = c.fetchall()
    conn.close()
    
    # 產生 HTML
    html = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>台股黑馬追蹤系統</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
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
        .header h1 { font-size: 2.5rem; margin-bottom: 10px; }
        .header p { opacity: 0.7; }
        .stats-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
        }
        .stat-card .value { font-size: 2rem; font-weight: bold; }
        .stat-card .label { opacity: 0.7; margin-top: 5px; }
        .category-section {
            margin-bottom: 40px;
        }
        .category-title {
            font-size: 1.5rem;
            margin-bottom: 20px;
            padding: 10px 20px;
            border-left: 4px solid;
            border-radius: 0 10px 10px 0;
        }
        .category-title.black-horse { border-color: #ffd700; background: rgba(255,215,0,0.1); }
        .category-title.growth { border-color: #00d4ff; background: rgba(0,212,255,0.1); }
        .category-title.dividend { border-color: #ff6b6b; background: rgba(255,107,107,0.1); }
        .category-title.value { border-color: #4ecdc4; background: rgba(78,205,196,0.1); }
        
        .stock-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }
        .stock-card {
            background: rgba(255,255,255,0.08);
            border-radius: 15px;
            padding: 20px;
            transition: transform 0.3s, box-shadow 0.3s;
            cursor: pointer;
        }
        .stock-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }
        .stock-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .stock-name { font-size: 1.3rem; font-weight: bold; }
        .stock-code { opacity: 0.6; font-size: 0.9rem; }
        .stock-price { font-size: 2rem; font-weight: bold; margin: 10px 0; }
        .price-up { color: #4ade80; }
        .price-down { color: #f87171; }
        .stock-metrics {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            font-size: 0.9rem;
        }
        .metric { display: flex; justify-content: space-between; }
        .metric-label { opacity: 0.6; }
        .changes {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .change-tag {
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
        }
        .change-1d.positive { background: rgba(74,222,128,0.2); color: #4ade80; }
        .change-1d.negative { background: rgba(248,113,113,0.2); color: #f87171; }
        
        .chart-container {
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 30px;
        }
        
        @media (max-width: 768px) {
            .header h1 { font-size: 1.8rem; }
            .stock-grid { grid-template-columns: 1fr; }
        }
        
        .last-update {
            text-align: center;
            opacity: 0.5;
            margin-top: 30px;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 台股黑馬追蹤系統</h1>
        <p>每日更新 • 互動式儀表板</p>
    </div>
    
    <div class="stats-row">
        <div class="stat-card">
            <div class="value">''' + str(len([s for s in stocks_data if s[3]])) + '''</div>
            <div class="label">追蹤中股票</div>
        </div>
        <div class="stat-card">
            <div class="value">''' + str(len([s for s in stocks_data if s[8] and s[8] > 0])) + '''</div>
            <div class="label">今日上漲</div>
        </div>
        <div class="stat-card">
            <div class="value">''' + str(len([s for s in stocks_data if s[8] and s[8] < 0])) + '''</div>
            <div class="label">今日下跌</div>
        </div>
        <div class="stat-card">
            <div class="value">''' + f"{sum([s[4] or 0 for s in stocks_data if s[4]]):.1f}%" + '''</div>
            <div class="label">平均殖利率</div>
        </div>
    </div>
'''
    
    # 按類別分組
    categories = {"黑馬": [], "成長": [], "高息": [], "價值": []}
    for s in stocks_data:
        if s[2] in categories:
            categories[s[2]].append(s)
    
    category_colors = {"黑馬": "black-horse", "成長": "growth", "高息": "dividend", "價值": "value"}
    
    for cat, stocks in categories.items():
        if stocks:
            html += f'''
    <div class="category-section">
        <div class="category-title {category_colors[cat]}">🎯 {cat}</div>
        <div class="stock-grid">
'''
            for s in stocks:
                price = s[3] if s[3] else "-"
                yield_val = f"{s[4]:.2f}%" if s[4] else "-"
                pe_val = f"{s[5]:.1f}" if s[5] and s[5] > 0 else "N/A"
                pb_val = f"{s[6]:.2f}" if s[6] else "-"
                change_class = "price-up" if s[7] and s[7] > 0 else "price-down" if s[7] and s[7] < 0 else ""
                change_val = f"{s[7]:+.2f}%" if s[7] else "-"
                
                html += f'''
            <div class="stock-card">
                <div class="stock-header">
                    <div>
                        <div class="stock-name">{s[1]}</div>
                        <div class="stock-code">{s[0]}</div>
                    </div>
                </div>
                <div class="stock-price {change_class}">${price}</div>
                <div class="stock-metrics">
                    <div class="metric"><span class="metric-label">殖利率</span><span>{yield_val}</span></div>
                    <div class="metric"><span class="metric-label">本益比</span><span>{pe_val}</span></div>
                    <div class="metric"><span class="metric-label">淨值比</span><span>{pb_val}</span></div>
                    <div class="metric"><span class="metric-label">今日</span><span class="{change_class}">{change_val}</span></div>
                </div>
            </div>
'''
            html += '''
        </div>
    </div>
'''
    
    html += f'''
    <div class="last-update">最後更新: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
</body>
</html>'''
    
    output_path = os.path.expanduser("~/.openclaw/workspace/stock-tracker/dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ 儀表板已生成: {output_path}")
    return output_path

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "collect":
        init_db()
        collect_daily_data()
    elif len(sys.argv) > 1 and sys.argv[1] == "dashboard":
        generate_html_dashboard()
    else:
        init_db()
        collect_daily_data()
        generate_html_dashboard()