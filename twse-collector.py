#!/usr/bin/env python3
"""
Taiwan Stock Collector - 使用 TWSE API
更新時間: 2026-03-31
"""

import requests
import json
import sys
import os
from datetime import datetime

TWSE_API = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"

def get_price(stock_no, date="20260331"):
    """取得個股收盤價"""
    url = f"{TWSE_API}?date={date}&stockNo={stock_no}&response=json"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("data"):
            return data["data"][0]
    except Exception as e:
        print(f"Error: {e}")
    return None

def format_price(price_data):
    """格式化價格數據"""
    if not price_data:
        return "N/A"
    return {
        "date": price_data[0],
        "volume": price_data[1],
        "amount": price_data[2],
        "open": price_data[3],
        "high": price_data[4],
        "low": price_data[5],
        "close": price_data[6],
        "change": price_data[7]
    }

if __name__ == "__main__":
    # 追蹤的股票列表
    stocks = {
        "2330": "台積電",
        "2317": "鴻海",
        "2603": "長榮",
        "2371": "大同",
        "1519": "華城",
        "2609": "陽明",
        "2615": "萬海",
        "1432": "大魯閣",
        "2498": "宏達電"
    }
    
    date = sys.argv[1] if len(sys.argv) > 1 else "20260331"
    
    print(f"=== 台股每日收盤 ({date}) ===\n")
    
    for code, name in stocks.items():
        price_data = get_price(code, date)
        if price_data:
            p = format_price(price_data)
            print(f"{code} {name}: 收盤 {p['close']} 漲跌 {p['change']}")
        else:
            print(f"{code} {name}: 無資料")