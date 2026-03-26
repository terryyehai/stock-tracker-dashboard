#!/usr/bin/env python3
"""每日趨勢自動發現"""
import cloudscraper
from bs4 import BeautifulSoup
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/.openclaw/workspace/stock-tracker/active-discovery.db")

SOURCES = [
    {"name": "HKAPC", "url": "https://www.hkepc.com/", "cat": "科技"},
    {"name": "TechNews", "url": "https://technews.tw/", "cat": "科技"},
]

TECH_KEYWORDS = {
    "記憶體": ["DRAM", "HBM", "TurboQuant"],
    "AI": ["AI", "生成式", "LLM"],
    "半導體": ["晶片", "CoWoS", "封裝"],
    "新能源": ["電動車", "儲能", "固態電池"],
}

def update_daily():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📡 每日更新: {today}")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    new_findings = 0
    
    for source in SOURCES:
        try:
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(source["url"], timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for item in soup.select("article h3, .title")[:10]:
                    title = item.text.strip()
                    if len(title) > 10:
                        for cat, kws in TECH_KEYWORDS.items():
                            if any(kw in title for kw in kws):
                                c.execute("SELECT COUNT(*) FROM discoveries WHERE title=? AND date=?", (title, today))
                                if c.fetchone()[0] == 0:
                                    c.execute("INSERT INTO discoveries (date, keyword, category, source, title, summary, found_stocks, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                             (today, kws[0], cat, source["name"], title, "自動發現", "", "auto"))
                                    new_findings += 1
                                    print(f"   ✅ {title[:30]}...")
        except Exception as e:
            print(f"   ⚠️ {source['name']}: {str(e)[:30]}")
    
    conn.commit()
    conn.close()
    print(f"\n✅ 今日新增 {new_findings} 項")

if __name__ == "__main__":
    update_daily()
