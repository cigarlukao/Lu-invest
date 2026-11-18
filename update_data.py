import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import yfinance as yf

# 您的五檔 ETF 持倉設定 (張數)
HOLDINGS = [
    {"id": "0056.TW", "name": "元大高股息", "lots": 21},
    {"id": "00919.TW", "name": "群益台灣精選高息", "lots": 25},
    {"id": "00713.TW", "name": "元大台灣高息低波", "lots": 10},
    {"id": "00878.TW", "name": "國泰永續高股息", "lots": 17},
    {"id": "00918.TW", "name": "大華優利高填息30", "lots": 12},
]
BASELINE_VALUE = 3390630  # 追蹤起算基準市值 (11/16)

def fetch_stock_data():
    histories = {}
    etf_results = []
    total_value = 0

    for item in HOLDINGS:
        ticker = yf.Ticker(item["id"])
        hist = ticker.history(period="15d").dropna(subset=["Close"])
        histories[item["id"]] = hist

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) >= 2 else latest

        close_price = round(float(latest["Close"]), 2)
        prev_close = float(prev["Close"])
        change = round(close_price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
        vol_lots = int(round(float(latest["Volume"]) / 1000))
        market_val = int(round(close_price * item["lots"] * 1000))
        total_value += market_val

        etf_results.append({
            "id": item["id"],
            "name": item["name"],
            "lots": item["lots"],
            "close": close_price,
            "change": change,
            "change_pct": change_pct,
            "market_val": market_val,
            "volume": vol_lots,
        })

    for etf in etf_results:
        etf["weight"] = round((etf["market_val"] / total_value) * 100, 2) if total_value else 0.0

    # 抓取台灣加權指數 (^TWII) 計算近 6 個交易日對照走勢
    taiex_hist = yf.Ticker("^TWII").history(period="15d").dropna(subset=["Close"])
    recent_dates = taiex_hist.index[-6:]

    chart_points = []
    base_taiex = float(taiex_hist.loc[recent_dates[0], "Close"])
    base_port = 0.0

    for idx, dt in enumerate(recent_dates):
        t_close = float(taiex_hist.loc[dt, "Close"])
        p_val = 0.0
        for item in HOLDINGS:
            h = histories[item["id"]]
            # 取該日或該日之前最近一筆收盤價
            sub = h.loc[:dt]
            c = float(sub.iloc[-1]["Close"]) if len(sub) > 0 else float(h.iloc[0]["Close"])
            p_val += c * item["lots"] * 1000

        if idx == 0:
            base_port = p_val

        taiex_pct = round(((t_close - base_taiex) / base_taiex) * 100, 2)
        port_pct = round(((p_val - base_port) / base_port) * 100, 2)
        chart_points.append({
            "date": dt.strftime("%m/%d"),
            "lu": port_pct,
            "taiex": taiex_pct,
        })

    latest_date_str = recent_dates[-1].strftime("%Y/%m/%d")
    taiex_latest = round(float(taiex_hist.iloc[-1]["Close"]), 2)
    taiex_prev = float(taiex_hist.iloc[-2]["Close"])
    taiex_diff = round(taiex_latest - taiex_prev, 2)
    taiex_diff_pct = round((taiex_diff / taiex_prev) * 100, 2)

    return {
        "trade_date": latest_date_str,
        "total_value": total_value,
        "baseline_diff": total_value - BASELINE_VALUE,
        "baseline_diff_pct": round(((total_value - BASELINE_VALUE) / BASELINE_VALUE) * 100, 2),
        "taiex": {
            "close": taiex_latest,
            "change": taiex_diff,
            "change_pct": taiex_diff_pct,
        },
        "etfs": etf_results,
        "chart": chart_points,
    }

def fetch_yahoo_news():
    news_list = []
    try:
        query = urllib.parse.quote("site:tw.stock.yahoo.com 台股 OR ETF OR 高股息")
        url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        for item in root.findall("./channel/item")[:5]:
            title = (item.findtext("title") or "").replace(" - Yahoo奇摩股市", "").replace(" - Yahoo", "")
            link = item.findtext("link") or "#"
            pub_date = item.findtext("pubDate") or ""
            news_list.append({"title": title, "link": link, "pubDate": pub_date})
    except Exception as e:
        print(f"抓取新聞失敗: {e}")
    return news_list

if __name__ == "__main__":
    tz_tw = timezone(timedelta(hours=8))
    now_tw = datetime.now(tz_tw).strftime("%Y年%m月%d日 %H:%M")

    output = fetch_stock_data()
    output["updated_at"] = now_tw
    output["news"] = fetch_yahoo_news()

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"更新完成！資料日期: {output['trade_date']}，總市值: {output['total_value']}")
