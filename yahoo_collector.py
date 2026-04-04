#!/usr/bin/env python3
"""
Yahoo Finance Taiwan Stock Collector
- Uses Yahoo Finance API (free, no key needed)
- Batch collecting with rate limiting
- Incremental updates (only fetches missing dates)
"""

import requests
import sqlite3
import json
import time
from datetime import datetime, timedelta
import sys

DB_PATH = "/home/terry/.openclaw/workspace/stock-tracker/stocks.db"
YQL_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}?range=1y&interval=1d"

def get_stocks_from_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT code FROM stock_list")
    stocks = [row[0] for row in c.fetchall()]
    conn.close()
    return stocks

def get_existing_dates(code):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT date FROM daily_prices WHERE code = ?", (code,))
    dates = set(row[0] for row in c.fetchall())
    conn.close()
    return dates

def fetch_stock_data(code):
    """Fetch 1 year of data for a single stock"""
    try:
        url = YQL_URL.format(code + ".TW")
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }, timeout=15)
        
        data = resp.json()
        if "chart" not in data or not data["chart"].get("result"):
            return None
            
        result = data["chart"]["result"][0]
        ts = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        
        records = []
        for i, timestamp in enumerate(ts):
            date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            record = {
                "date": date_str,
                "open": quote["open"][i],
                "high": quote["high"][i],
                "low": quote["low"][i],
                "close": quote["close"][i],
                "volume": quote["volume"][i]
            }
            if all(v is not None for v in record.values()):
                records.append(record)
        
        return records
    except Exception as e:
        print(f"Error fetching {code}: {e}")
        return None

def save_to_db(code, records):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for r in records:
        c.execute("""INSERT OR IGNORE INTO daily_prices 
                     (code, date, open_price, high_price, low_price, close_price, volume) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (code, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"]))
    conn.commit()
    conn.close()
    return len(records)

def collect_batch(stocks, start_idx, batch_size):
    """Collect a batch of stocks"""
    end_idx = min(start_idx + batch_size, len(stocks))
    batch = stocks[start_idx:end_idx]
    
    print(f"Processing {start_idx+1}-{end_idx} of {len(stocks)}...")
    
    total_saved = 0
    for i, code in enumerate(batch):
        existing = get_existing_dates(code)
        
        # If we have data, just get the latest day
        if len(existing) > 0:
            # For incremental: only fetch latest day
            records = fetch_stock_data(code)
            if records and records[-1]["date"] not in existing:
                saved = save_to_db(code, [records[-1]])
                total_saved += saved
        else:
            # Full historical fetch for new stocks
            records = fetch_stock_data(code)
            if records:
                saved = save_to_db(code, records)
                total_saved += saved
        
        # Rate limit: 1 request per second to avoid rate limiting
        time.sleep(1.1)
        
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(batch)}")
    
    return total_saved

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    
    stocks = get_stocks_from_db()
    print(f"Total stocks to process: {len(stocks)}")
    
    if mode == "batch1":
        # First 200 (2:00 PM)
        collect_batch(stocks, 0, 200)
    elif mode == "batch2":
        # Next 200 (3:00 PM)
        collect_batch(stocks, 200, 200)
    elif mode == "batch3":
        # Last batch (4:00 PM)
        collect_batch(stocks, 400, 200)
    elif mode == "incremental":
        # Just today's update
        collect_batch(stocks, 0, len(stocks))
    else:
        # Full collection
        collect_batch(stocks, 0, len(stocks))
    
    print("Done!")
