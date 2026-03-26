#!/usr/bin/env python3
"""
每日趨勢自動發現系統 v2 - 失敗重試機制
"""
import cloudscraper
from bs4 import BeautifulSoup
import sqlite3
import os
from datetime import datetime
import time

DB_PATH = os.path.expanduser("~/.openclaw/workspace/stock-tracker/active-discovery.db")

SOURCES = [
    {"name": "HKAPC", "url": "https://www.hkepc.com/", "cat": "科技", "retry": 3},
    {"name": "TechNews", "url": "https://technews.tw/", "cat": "科技", "retry": 3},
    {"name": "DIGITIMES", "url": "https://digitimes.com.tw/", "cat": "產業", "retry": 3},
    {"name": "經濟日報", "url": "https://money.udn.com/money/cate/1104", "cat": "財經", "retry": 3},
]

TECH_KEYWORDS = {
    "記憶體": ["DRAM", "HBM", "TurboQuant"],
    "AI": ["AI", "生成式", "LLM", "ChatGPT"],
    "半導體": ["CoWoS", "封裝", "3nm", "2nm"],
    "新能源": ["電動車", "儲能", "固態電池"],
    "散熱": ["液冷", "散熱", "冷卻"],
    "衛星": ["Starlink", "低軌", "衛星"],
}

def fetch_with_retry(url, max_retries=3, delay=2):
    """帶重試機制的網頁抓取"""
    scraper = cloudscraper.create_scraper()
    
    for attempt in range(max_retries):
        try:
            resp = scraper.get(url, timeout=30)
            if resp.status_code == 200:
                return True, resp.text
            elif resp.status_code == 403:
                print(f"   ⚠️ Cloudflare 阻擋，{delay}秒後重試 ({attempt+1}/{max_retries})")
                time.sleep(delay)
            else:
                return False, f"HTTP {resp.status_code}"
        except Exception as e:
            print(f"   ⚠️ 連線錯誤，重試中 ({attempt+1}/{max_retries})")
            time.sleep(delay)
    
    return False, "超過最大重試次數"

def update_daily():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📡 每日趨勢更新: {today}")
    print("-" * 40)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 失敗日誌表
    c.execute('''CREATE TABLE IF NOT EXISTS fetch_logs (
        date TEXT, source TEXT, status TEXT, error TEXT, retry_count INTEGER
    )''')
    
    new_findings = 0
    
    for source in SOURCES:
        print(f"\n🔍 {source['name']}...")
        success, result = fetch_with_retry(source["url"], source["retry"])
        
        if success:
            try:
                soup = BeautifulSoup(result, "html.parser")
                found_count = 0
                
                for item in soup.select("article h3, .title, h2")[:15]:
                    title = item.text.strip()
                    if len(title) > 10:
                        for cat, kws in TECH_KEYWORDS.items():
                            if any(kw in title for kw in kws):
                                c.execute("SELECT COUNT(*) FROM discoveries WHERE title=? AND date=?", (title, today))
                                if c.fetchone()[0] == 0:
                                    c.execute("INSERT INTO discoveries (date, keyword, category, source, title, summary, found_stocks, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                        (today, kws[0], cat, source["name"], title, "自動發現", "", "auto"))
                                    new_findings += 1
                                    found_count += 1
                                    break
                
                print(f"   ✅ 發現 {found_count} 項")
                c.execute("INSERT INTO fetch_logs VALUES (?, ?, ?, ?, ?)", (today, source["name"], "success", "", 0))
                        
            except Exception as e:
                print(f"   ⚠️ 解析錯誤: {str(e)[:30]}")
                c.execute("INSERT INTO fetch_logs VALUES (?, ?, ?, ?, ?)", (today, source["name"], "error", str(e)[:50], 1))
        else:
            print(f"   ❌ 失敗: {result}")
            c.execute("INSERT INTO fetch_logs VALUES (?, ?, ?, ?, ?)", (today, source["name"], "failed", result, source["retry"]))
    
    conn.commit()
    conn.close()
    
    print("-" * 40)
    print(f"✅ 今日共新增 {new_findings} 項趨勢")
    
    # 顯示失敗摘要
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT source, status, COUNT(*) FROM fetch_logs WHERE date=? AND status='failed' GROUP BY source", (today,))
    failed = c.fetchall()
    if failed:
        print("\n📊 失敗記錄:")
        for row in failed:
            print(f"   ❌ {row[0]}: {row[2]}次")
    conn.close()

if __name__ == "__main__":
    update_daily()