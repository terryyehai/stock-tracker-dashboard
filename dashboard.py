#!/usr/bin/env python3
"""
Stock Dashboard with SQL Query Interface
"""

import sqlite3
from flask import Flask, render_template_string, request, g

app = Flask(__name__)
DB_PATH = "/home/terry/.openclaw/workspace/stock-tracker/stocks.db"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    db = get_db()
    
    cur = db.execute("SELECT COUNT(DISTINCT code) as cnt FROM daily_prices")
    total_stocks = cur.fetchone()['cnt']
    
    cur = db.execute("SELECT MAX(date) as latest FROM daily_prices")
    latest_date = cur.fetchone()['latest']
    
    cur = db.execute("""
        SELECT code, close_price, 
               ((close_price - open_price) / open_price * 100) as pct
        FROM daily_prices WHERE date = ? ORDER BY pct DESC LIMIT 10
    """, (latest_date,))
    gainers = cur.fetchall()
    
    cur = db.execute("""
        SELECT code, close_price, 
               ((close_price - open_price) / open_price * 100) as pct
        FROM daily_prices WHERE date = ? ORDER BY pct ASC LIMIT 10
    """, (latest_date,))
    losers = cur.fetchall()
    
    watchlist = ["2330", "2454", "2317", "2603", "0050", "2885", "1303"]
    cur = db.execute("""
        SELECT code, close_price, 
               ((close_price - open_price) / open_price * 100) as pct
        FROM daily_prices WHERE date = ? AND code IN ({})
    """.format(','.join('?' * len(watchlist))), [latest_date] + watchlist)
    watchlist_data = cur.fetchall()
    
    return render_template_string(DASHBOARD_HTML, 
                                   total_stocks=total_stocks,
                                   latest_date=latest_date,
                                   gainers=gainers,
                                   losers=losers,
                                   watchlist=watchlist_data)

@app.route('/query', methods=['GET', 'POST'])
def query():
    result = None
    columns = None
    error = None
    sql = request.form.get('sql', '')
    
    if sql:
        try:
            db = get_db()
            cur = db.execute(sql)
            if sql.strip().upper().startswith('SELECT'):
                rows = cur.fetchall()
                if rows:
                    columns = rows[0].keys()
                    result = [dict(row) for row in rows]
                else:
                    result = []
            else:
                db.commit()
                result = [{"status": "OK", "rows_affected": cur.rowcount}]
        except Exception as e:
            error = str(e)
    
    return render_template_string(QUERY_HTML, result=result, columns=columns, error=error, sql=sql)

@app.route('/stocks')
def stocks():
    db = get_db()
    code = request.args.get('code', '2330')
    
    cur = db.execute("""
        SELECT * FROM daily_prices WHERE code = ? ORDER BY date DESC LIMIT 30
    """, (code,))
    rows = cur.fetchall()
    
    return render_template_string(STOCK_HTML, code=code, data=rows)

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Stock Dashboard</title>
    <style>
        body { font-family: Arial; margin: 20px; background: #f5f5f5; }
        h1 { color: #333; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat-box { background: white; padding: 20px; border-radius: 8px; }
        .stat-box h3 { margin: 0 0 10px 0; color: #666; }
        .stat-box .value { font-size: 24px; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; background: white; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #4CAF50; color: white; }
        .gain { color: green; }
        .loss { color: red; }
        .section { margin: 30px 0; }
        .nav { margin: 20px 0; }
        .nav a { margin-right: 20px; color: #4CAF50; text-decoration: none; }
    </style>
</head>
<body>
    <h1>📈 Stock Dashboard</h1>
    <div class="nav">
        <a href="/">Dashboard</a>
        <a href="/query">SQL Query</a>
        <a href="/stocks">Stock List</a>
    </div>
    <div class="stats">
        <div class="stat-box"><h3>Total Stocks</h3><div class="value">{{ total_stocks }}</div></div>
        <div class="stat-box"><h3>Latest Date</h3><div class="value">{{ latest_date }}</div></div>
    </div>
    <div class="section"><h2>⭐ Your Watchlist</h2>
        <table><tr><th>Code</th><th>Close</th><th>Change %</th></tr>
        {% for row in watchlist_data %}
        <tr><td><a href="/stocks?code={{ row['code'] }}">{{ row['code'] }}</a></td>
            <td>{{ "%.2f"|format(row['close_price']) }}</td>
            <td class="{% if row['pct'] > 0 %}gain{% else %}loss{% endif %}">{{ "%.2f"|format(row['pct']) }}%</td></tr>
        {% endfor %}</table>
    </div>
    <div class="section"><h2>🟢 Top Gainers</h2>
        <table><tr><th>Code</th><th>Close</th><th>Change %</th></tr>
        {% for row in gainers %}
        <tr><td><a href="/stocks?code={{ row['code'] }}">{{ row['code'] }}</a></td>
            <td>{{ "%.2f"|format(row['close_price']) }}</td>
            <td class="gain">{{ "%.2f"|format(row['pct']) }}%</td></tr>
        {% endfor %}</table>
    </div>
    <div class="section"><h2>🔴 Top Losers</h2>
        <table><tr><th>Code</th><th>Close</th><th>Change %</th></tr>
        {% for row in losers %}
        <tr><td><a href="/stocks?code={{ row['code'] }}">{{ row['code'] }}</a></td>
            <td>{{ "%.2f"|format(row['close_price']) }}</td>
            <td class="loss">{{ "%.2f"|format(row['pct']) }}%</td></tr>
        {% endfor %}</table>
    </div>
</body>
</html>
'''

QUERY_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>SQL Query</title>
    <style>
        body { font-family: monospace; margin: 20px; background: #f5f5f5; }
        .nav a { margin-right: 20px; color: #4CAF50; text-decoration: none; }
        textarea { width: 100%; height: 150px; font-family: monospace; font-size: 14px; padding: 10px; }
        button { background: #4CAF50; color: white; padding: 10px 20px; border: none; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; background: white; }
        th, td { padding: 8px; border: 1px solid #ddd; }
        th { background: #4CAF50; color: white; }
        .error { background: #ffebee; color: #c62828; padding: 10px; }
        pre { background: #263238; color: #aed581; padding: 15px; }
    </style>
</head>
<body>
    <h1>🔍 SQL Query Interface</h1>
    <div class="nav">
        <a href="/">Dashboard</a>
        <a href="/query">SQL Query</a>
        <a href="/stocks">Stock List</a>
    </div>
    <form method="post">
        <textarea name="sql" placeholder="SELECT * FROM daily_prices WHERE code='2330'">{{ sql }}</textarea>
        <br><br>
        <button type="submit">Execute</button>
    </form>
    {% if error %}<div class="error">Error: {{ error }}</div>{% endif %}
    {% if result %}
    <h3>Results ({{ result|length }} rows)</h3>
    <table><tr>{% for col in columns %}<th>{{ col }}</th>{% endfor %}</tr>
        {% for row in result %}
        <tr>{% for col in columns %}<td>{{ row[col] }}</td>{% endfor %}</tr>
        {% endfor %}</table>
    {% endif %}
    <h3>Example Queries:</h3>
    <pre>
-- 查詢台積電最近10天
SELECT * FROM daily_prices WHERE code='2330' ORDER BY date DESC LIMIT 10

-- 查詢漲幅超過5%的股票
SELECT code, close_price, ((close_price - open_price) / open_price * 100) as pct 
FROM daily_prices WHERE date='2026-04-02' AND pct > 5

-- 查詢所有ETF
SELECT * FROM daily_prices WHERE code LIKE '005%' AND date='2026-04-02'
    </pre>
</body>
</html>
'''

STOCK_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ code }} History</title>
    <style>
        body { font-family: Arial; margin: 20px; background: #f5f5f5; }
        .nav a { margin-right: 20px; color: #4CAF50; text-decoration: none; }
        table { width: 100%; border-collapse: collapse; background: white; }
        th, td { padding: 10px; border-bottom: 1px solid #eee; }
        th { background: #4CAF50; color: white; }
    </style>
</head>
<body>
    <h1>📊 {{ code }} Price History</h1>
    <div class="nav"><a href="/">Dashboard</a><a href="/query">SQL Query</a></div>
    <table>
        <tr><th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr>
        {% for row in data %}
        <tr><td>{{ row['date'] }}</td>
            <td>{{ "%.2f"|format(row['open_price']) }}</td>
            <td>{{ "%.2f"|format(row['high_price']) }}</td>
            <td>{{ "%.2f"|format(row['low_price']) }}</td>
            <td>{{ "%.2f"|format(row['close_price']) }}</td>
            <td>{{ row['volume'] }}</td></tr>
        {% endfor %}
    </table>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)