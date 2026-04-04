#!/usr/bin/env python3
"""
台股 Yahoo Finance 收集器 (改良版)
使用 web_fetch 或直接解析
更新: 2026-04-03
"""

import requests
import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "all_stocks.db"

# 股票清單
STOCKS = [
    ("2330", "台積電"), ("2317", "鴻海"), ("2603", "長榮"),
    ("2371", "大同"), ("1519", "華城"), ("2609", "陽明"),
    ("2615", "萬海"), ("2303", "聯電"), ("2454", "聯發科"),
    ("2412", "中華電"), ("2881", "富邦金"), ("2882", "國泰金"),
    ("2891", "中信金"), ("0050", "元大台灣50"), ("0056", "元大高股息"),
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
        amount REAL,
        change REAL,
        change_pct REAL,
        prev_close REAL,
        PRIMARY KEY (date, code)
    )''')
    
    conn.commit()
    return conn


def parse_yahoo_html(code, html):
    """解析 Yahoo HTML"""
    data = {}
    
    # 找收盤價 - 多種模式
    patterns = [
        r'">(?:成交|收盤)[^<]*?(\d{1,4}),(\d{3})',
        r'([0-9]{1,3}),([0-9]{3})(?:</span>)?\s*(?:成交|收盤)',
    ]
    
    for row in html.split('\n'):
        # 成交價
        m = re.search(r'成交.*?(\d{1,3}),(\d{3})', row)
        if m:
            data['close'] = float(m.group(1) + m.group(2))
        
        # 開盤
        m = re.search(r'開盤.*?(\d{1,3}),(\d{3})', row)
        if m:
            data['open'] = float(m.group(1) + m.group(2))
        
        # 最高
        m = re.search(r'最高.*?(\d{1,3}),(\d{3})', row)
        if m:
            data['high'] = float(m.group(1) + m.group(2))
        
        # 最低
        m = re.search(r'最低.*?(\d{1,3}),(\d{3})', row)
        if m:
            data['low'] = float(m.group(1) + m.group(2))
        
        # 昨收
        m = re.search(r'昨收.*?(\d{1,3}),(\d{3})', row)
        if m:
            data['prev_close'] = float(m.group(1) + m.group(2))
        
        # 漲跌
        m = re.search(r'漲跌([+-]?\d+\.?\d*)', row)
        if m:
            data['change'] = float(m.group(1))
        
        # 漲跌幅
        m = re.search(r'漲跌幅([+-]?\d+\.?\d*)%', row)
        if m:
            data['change_pct'] = float(m.group(1))
        
        # 總量
        m = re.search(r'總量(\d{1,3}),(\d{3})', row)
        if m:
            data['volume'] = int(m.group(1) + m.group(2))
    
    return data


def collect_all(conn):
    """收集所有股票"""
    today = datetime.now().strftime("%Y%m%d")
    c = conn.cursor()
    
    success = 0
    for code, name in STOCKS:
        print(f"收集 {code} {name}...", end=" ", flush=True)
        
        url = f"https://tw.stock.yahoo.com/quote/{code}.TW"
        
        try:
            resp = requests.get(url, timeout=20)
            data = parse_yahoo_html(code, resp.text)
            
            if data and 'close' in data:
                print(f"{data.get('close')} {data.get('change', 0):+.2f}")
                
                c.execute("INSERT OR IGNORE INTO stocks (code, name, updated) VALUES (?, ?, ?)",
                        (code, name, today))
                
                c.execute('''INSERT OR REPLACE INTO daily_prices 
                    (date, code, open, high, low, close, volume, change, change_pct, prev_close)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (today, code, data.get('open'), data.get('high'), data.get('low'),
                     data.get('close'), data.get('volume'), data.get('change'),
                     data.get('change_pct'), data.get('prev_close')))
                
                success += 1
            else:
                print("解析失敗")
                
        except Exception as e:
            print(f"錯誤: {e}")
    
    conn.commit()
    return success


def show_summary(conn):
    """顯示摘要"""
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM stocks")
    total = c.fetchone()[0]
    
    today = datetime.now().strftime("%Y%m%d")
    c.execute("SELECT COUNT(*) FROM daily_prices WHERE date = ?", (today,))
    today_count = c.fetchone()[0]
    
    print(f"\n=== 資料庫統計 ===")
    print(f"總股票數: {total}")
    print(f"今日收集: {today_count} 檔")
    
    # 漲幅前10
    c.execute(f'''SELECT code, close, change, change_pct FROM daily_prices 
                WHERE date = "{today}" ORDER BY change_pct DESC LIMIT 10''')
    rows = c.fetchall()
    
    if rows:
        print(f"\n=== 漲幅前10 ===")
        for code, close, change, pct in rows:
            if pct:
                print(f"  {code}: {close} {pct:+.2f}%")


if __name__ == "__main__":
    conn = init_db()
    
    print("=== Yahoo Finance 台股收集 ===")
    print(f"股票數: {len(STOCKS)}")
    
    success = collect_all(conn)
    show_summary(conn)
    
    conn.close()
    print(f"\n完成！收集 {success}/{len(STOCKS)} 檔")