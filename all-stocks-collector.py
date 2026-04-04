#!/usr/bin/env python3
"""
台灣上市股票收集器 - 使用 TWSE API
更新: 2026-04-03
"""

import requests
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

TWSE_API = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
DB_PATH = Path(__file__).parent / "all_stocks.db"


# 主要上市股票清單
ALL_STOCKS = [
    # 半導體
    ("2330", "台積電"), ("2303", "聯電"), ("2454", "聯發科"),
    ("3034", "聯詠"), ("6488", "晶星河"), ("6756", "威鋒電子"),
    ("3529", "力旺"), ("5269", "祥碩"), ("6147", "頎邦"),
    ("6525", "嘉澤"), ("8016", "矽創"),
    
    # 電子權值
    ("2317", "鴻海"), ("2412", "中華電"), ("4906", "正文"),
    ("2382", "廣達"), ("2327", "國巨"), ("2328", "漫步"),
    ("2371", "大同"), ("2498", "宏達電"),
    
    # AI/Server
    ("1519", "華城"), ("2357", "華碩"), ("2376", "技嘉"),
    ("6265", "勤誠"), ("5274", "緯穎"),
    
    # 航運
    ("2603", "長榮"), ("2609", "陽明"), ("2615", "萬海"),
    ("2618", "長榮航"), ("2915", "裕民"),
    
    # 金融
    ("2881", "富邦金"), ("2882", "國泰金"), ("2891", "中信金"),
    ("2892", "第一金"), ("5871", "中租-KY"), ("6005", "群益證"),
    ("2884", "玉山金"), ("2885", "元大金"), ("2801", "彰銀"),
    ("2809", "京城銀"),
    
    # ETF
    ("0050", "元大台灣50"), ("0056", "元大高股息"),
    ("0052", "富邦科技"), ("006208", "富邦台50"),
    
    # 傳產
    ("1101", "台泥"), ("1102", "亞泥"), ("1301", "台塑"),
    ("1303", "南亞"), ("2002", "台玻"), ("2105", "正新"),
    ("2204", "中華車"), ("2103", "冠德"), ("2501", "國建"),
    ("2542", "興富發"), ("2607", "欣巴巴"),
    
    # 運動休閒
    ("1432", "大魯閣"), ("9904", "寶成"), ("9907", "新光捏"),
    
    # 其他權值
    ("2329", "華卡"), ("2471", "系統"), ("3217", "愛普"),
    ("3533", "嘉義",), ("3552", "同致"),
]


def init_db():
    """初始化資料庫"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS stocks (
        code TEXT PRIMARY KEY,
        name TEXT,
        industry TEXT,
        list_date TEXT,
        updated TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS daily_prices (
        date TEXT,
        code TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        amount INTEGER,
        change REAL,
        change_pct REAL,
        prev_close REAL,
        PRIMARY KEY (date, code)
    )''')
    
    conn.commit()
    return conn


def get_price(stock_no, date):
    """取得個股收盤價"""
    url = f"{TWSE_API}?date={date}&stockNo={stock_no}&response=json"
    
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if data.get("data"):
            row = data["data"][0]
            
            # 解析價格
            price_data = {
                "date": row[0],
                "volume": int(row[1].replace(",", "")),
                "amount": int(row[2].replace(",", "")),
                "open": float(row[3].replace(",", "")),
                "high": float(row[4].replace(",", "")),
                "low": float(row[5].replace(",", "")),
                "close": float(row[6].replace(",", "")),
                "change": float(row[7].replace(",", "")),
            }
            
            # 計算漲跌幅
            if price_data["open"] > 0:
                price_data["change_pct"] = (price_data["change"] / (price_data["close"] - price_data["change"])) * 100
            
            return price_data
            
    except Exception as e:
        pass
    
    return None


def collect_date(conn, date):
    """收集指定日期"""
    c = conn.cursor()
    success = 0
    
    print(f"=== 收集 {date} ===\n")
    
    for code, name in ALL_STOCKS:
        print(f"收集 {code} {name}...", end=" ", flush=True)
        
        data = get_price(code, date)
        
        if data:
            print(f"{data['close']} {data['change']:+.2f}")
            
            # 儲存基本資料
            c.execute("INSERT OR IGNORE INTO stocks (code, name, updated) VALUES (?, ?, ?)",
                    (code, name, date))
            
            # 計算漲跌幅
            prev = data['close'] - data['change']
            change_pct = (data['change'] / prev * 100) if prev > 0 else 0
            
            # 儲存行情
            c.execute('''INSERT OR REPLACE INTO daily_prices 
                (date, code, open, high, low, close, volume, amount, change, change_pct, prev_close)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (date, code, data['open'], data['high'], data['low'],
                 data['close'], data['volume'], data['amount'],
                 data['change'], change_pct, prev))
            
            success += 1
        else:
            print("無資料")
    
    conn.commit()
    return success


def show_summary(conn, date):
    """顯示摘要"""
    c = conn.cursor()
    
    # 總數
    c.execute("SELECT COUNT(*) FROM stocks")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM daily_prices WHERE date = ?", (date,))
    today = c.fetchone()[0]
    
    print(f"\n=== 資料庫統計 ===")
    print(f"總股票數: {total}")
    print(f"今日收集: {today} 檔")
    
    # 漲幅前10
    c.execute(f'''SELECT s.name, p.close, p.change, p.change_pct 
                FROM daily_prices p JOIN stocks s ON p.code = s.code
                WHERE p.date = "{date}" AND p.change_pct > 0
                ORDER BY p.change_pct DESC LIMIT 10''')
    rows = c.fetchall()
    
    if rows:
        print(f"\n=== 漲幅前10 ({date}) ===")
        for name, close, change, pct in rows:
            print(f"  {name}: {close} {pct:+.2f}%")
    
    # 跌幅前10
    c.execute(f'''SELECT s.name, p.close, p.change, p.change_pct 
                FROM daily_prices p JOIN stocks s ON p.code = s.code
                WHERE p.date = "{date}" AND p.change_pct < 0
                ORDER BY p.change_pct ASC LIMIT 10''')
    rows = c.fetchall()
    
    if rows:
        print(f"\n=== 跌幅前10 ({date}) ===")
        for name, close, change, pct in rows:
            print(f"  {name}: {close} {pct:+.2f}%")


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    
    # 確認日期格式
    if len(date) != 8:
        date = datetime.now().strftime("%Y%m%d")
    
    conn = init_db()
    
    success = collect_date(conn, date)
    show_summary(conn, date)
    
    conn.close()
    print(f"\n完成！收集 {success}/{len(ALL_STOCKS)} 檔")