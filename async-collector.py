#!/usr/bin/env python3
"""
台灣上市股票全收集器 - 快速非同步版
更新: 2026-04-04
"""

import asyncio
import aiohttp
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
        name TEXT, industry TEXT, updated TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS daily_prices (
        date TEXT, code TEXT,
        open REAL, high REAL, low REAL, close REAL,
        volume INTEGER, amount INTEGER, change REAL,
        change_pct REAL, prev_close REAL,
        PRIMARY KEY (date, code)
    )''')
    
    conn.commit()
    return conn


def generate_stock_list():
    """生成股票代碼"""
    stocks = []
    for prefix in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
        for i in range(100, 2000):
            stocks.append(f"{prefix}{i:03d}")
    for i in range(0, 100):
        stocks.append(f"00{i:02d}")
    return stocks


async def fetch_price(session, code, date):
    """非同步取得股價"""
    url = f"{TWSE_API}?date={date}&stockNo={code}&response=json"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("data") and len(data["data"]) > 0:
                    row = data["data"][0]
                    close = float(row[6].replace(",", ""))
                    if close > 0:
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


async def collect_batch(session, date, codes, results):
    """批次收集"""
    tasks = []
    for code in codes:
        task = asyncio.create_task(fetch_price(session, code, date))
        tasks.append(task)
    
    # 並行執行
    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result:
            results.append(result)


async def collect_all(date):
    """收集所有股票"""
    codes = generate_stock_list()
    total = len(codes)
    
    print(f"=== 開始收集 {date} ({total} 檔) ===")
    
    conn = init_db()
    c = conn.cursor()
    
    results = []
    batch_size = 100
    
    # 分批並行
    for i in range(0, total, batch_size):
        batch = codes[i:i+batch_size]
        
        async with aiohttp.ClientSession() as session:
            await collect_batch(session, date, batch, results)
        
        print(f"進度: {min(i+batch_size, total)}/{total} (成功: {len(results)})")
        await asyncio.sleep(0.5)
    
    # 儲存結果
    print(f"\n儲存 {len(results)} ��資料...")
    
    for data in results:
        prev = data['close'] - data['change']
        change_pct = (data['change'] / prev * 100) if prev > 0 else 0
        
        c.execute('''INSERT OR REPLACE INTO daily_prices 
            (date, code, open, high, low, close, volume, amount, change, change_pct, prev_close)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (date, data['code'], data['open'], data['high'], data['low'],
             data['close'], data['volume'], data['amount'],
             data['change'], change_pct, prev))
    
    conn.commit()
    
    # 統計
    print(f"\n=== 完成 ===")
    print(f"成功: {len(results)} 檔")
    
    # 漲幅前10
    c.execute(f'''SELECT code, close, change, change_pct FROM daily_prices 
                WHERE date = "{date}" AND change_pct > 0
                ORDER BY change_pct DESC LIMIT 10''')
    
    print(f"\n=== 漲幅前10 ===")
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]} {row[3]:+.2f}%")
    
    conn.close()
    return len(results)


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    asyncio.run(collect_all(date))