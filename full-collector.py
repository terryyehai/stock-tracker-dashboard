#!/usr/bin/env python3
"""
台灣上市股票全收集器 - 優化版
只收集有交易的股票
更新: 2026-04-04
"""

import requests
import sqlite3
import time
from datetime import datetime
from pathlib import Path

TWSE_API = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
DB_PATH = Path(__file__).parent / "all_stocks.db"


def init_db():
    """初始化資料庫"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS stocks (
        code TEXT PRIMARY KEY,
        name TEXT,
        industry TEXT,
        updated TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS daily_prices (
        date TEXT,
        code TEXT,
        open REAL, high REAL, low REAL, close REAL,
        volume INTEGER, amount INTEGER, change REAL,
        change_pct REAL, prev_close REAL,
        PRIMARY KEY (date, code)
    )''')
    
    conn.commit()
    return conn


def get_price(code, date):
    """取得單檔股價"""
    url = f"{TWSE_API}?date={date}&stockNo={code}&response=json"
    
    try:
        resp = requests.get(url, timeout=3)
        data = resp.json()
        
        if data.get("data") and len(data["data"]) > 0:
            row = data["data"][0]
            
            # 檢查是否有效數據
            close = float(row[6].replace(",", ""))
            if close <= 0:
                return None
            
            return {
                "code": code,
                "volume": int(row[1].replace(",", "")),
                "amount": int(row[2].replace(",", "")),
                "open": float(row[3].replace(",", "")),
                "high": float(row[4].replace(",", "")),
                "low": float(row[5].replace(",", "")),
                "close": close,
                "change": float(row[7].replace(",", "")),
            }
    except:
        pass
    
    return None


def generate_stock_list():
    """生成股票代碼列表"""
    stocks = set()
    
    # 1xxx-9xxx 範圍
    for prefix in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
        for i in range(100, 2000):
            code = f"{prefix}{i:03d}"
            stocks.add(code)
    
    # ETF 00xx
    for i in range(0, 100):
        code = f"00{i:02d}"
        stocks.add(code)
    
    return sorted(stocks)


def collect_date(date):
    """收集指定日期"""
    conn = init_db()
    c = conn.cursor()
    
    codes = generate_stock_list()
    total = len(codes)
    
    print(f"=== 開始收集 {date} ({total} 檔) ===\n")
    
    success = 0
    failed = 0
    
    # 每100檔報告一次
    for i, code in enumerate(codes):
        data = get_price(code, date)
        
        if data:
            prev = data['close'] - data['change']
            change_pct = (data['change'] / prev * 100) if prev > 0 else 0
            
            c.execute('''INSERT OR REPLACE INTO daily_prices 
                (date, code, open, high, low, close, volume, amount, change, change_pct, prev_close)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (date, code, data['open'], data['high'], data['low'],
                 data['close'], data['volume'], data['amount'],
                 data['change'], change_pct, prev))
            
            success += 1
        else:
            failed += 1
        
        # 進度報告
        if (i + 1) % 200 == 0:
            print(f"進度: {i+1}/{total} (成功: {success})")
        
        # 避免請求太快
        if i % 10 == 0:
            time.sleep(0.1)
    
    conn.commit()
    
    # 統計
    print(f"\n=== 完成 ===")
    print(f"成功: {success} 檔")
    print(f"無資料: {failed} 檔")
    
    # 漲幅前10
    c.execute(f'''SELECT code, close, change, change_pct FROM daily_prices 
                WHERE date = "{date}" AND change_pct > 0
                ORDER BY change_pct DESC LIMIT 10''')
    rows = c.fetchall()
    
    if rows:
        print(f"\n=== 漲幅前10 ===")
        for code, close, change, pct in rows:
            print(f"  {code}: {close} {pct:+.2f}%")
    
    # 跌幅前10
    c.execute(f'''SELECT code, close, change, change_pct FROM daily_prices 
                WHERE date = "{date}" AND change_pct < 0
                ORDER BY change_pct ASC LIMIT 10''')
    rows = c.fetchall()
    
    if rows:
        print(f"\n=== 跌幅前10 ===")
        for code, close, change, pct in rows:
            print(f"  {code}: {close} {pct:+.2f}%")
    
    conn.close()
    return success


if __name__ == "__main__":
    from sys import argv
    
    date = argv[1] if len(argv) > 1 else datetime.now().strftime("%Y%m%d")
    
    collect_date(date)