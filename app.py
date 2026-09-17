#!/usr/bin/env python3
"""
SOXL 구성종목 대시보드 — Render(클라우드) 배포용 서버
-----------------------------------------------------
- GET /                → soxl_dashboard.html
- GET /api/quotes?symbols=SOXL,NVDA,...  → JSON 시세
- 시세 소스: 1) Yahoo v7 quote  2) Yahoo 1분봉 다운로드  3) Finnhub (환경변수 FINNHUB_KEY 가 있을 때, 거래량 없음)
- 20초 캐시: 여러 사람이 동시에 열어도 외부 API 호출은 20초에 1번
"""
import json, os, sys, time, threading, urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import yfinance as yf
from yfinance.data import YfData

PORT = int(os.environ.get("PORT", "8787"))
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_SEC = int(os.environ.get("CACHE_SEC", "20"))
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "").strip()

V7 = "https://query2.finance.yahoo.com/v7/finance/quote"
FIELDS = ",".join([
    "regularMarketPrice", "regularMarketPreviousClose", "regularMarketChangePercent",
    "regularMarketVolume", "averageDailyVolume3Month", "marketState",
])

_cache = {"t": 0, "key": None, "data": None}
_avg_cache = {"t": 0, "data": {}}
_lock = threading.Lock()


def _via_v7(symbols):
    d = YfData()
    j = d.get_raw_json(V7, params={"symbols": ",".join(symbols), "fields": FIELDS})
    out = {}
    for r in j.get("quoteResponse", {}).get("result", []):
        price, prev, chg = r.get("regularMarketPrice"), r.get("regularMarketPreviousClose"), r.get("regularMarketChangePercent")
        if chg is None and price and prev:
            chg = (price / prev - 1) * 100
        out[r.get("symbol")] = {
            "price": price, "prevClose": prev, "changePct": chg,
            "volume": r.get("regularMarketVolume"), "avgVolume": r.get("averageDailyVolume3Month"),
            "marketState": r.get("marketState"),
        }
    if not out:
        raise RuntimeError("v7 quote: empty result")
    return out


def _avg_volume(symbols):
    now = time.time()
    if now - _avg_cache["t"] < 3600 and all(s in _avg_cache["data"] for s in symbols):
        return _avg_cache["data"]
    df = yf.download(symbols, period="3mo", interval="1d", progress=False, auto_adjust=False, group_by="ticker", threads=True)
    data = {}
    for s in symbols:
        try:
            v = df[s]["Volume"].dropna()
            data[s] = float(v.iloc[:-1].tail(63).mean()) if len(v) > 1 else None
        except Exception:
            data[s] = None
    _avg_cache.update(t=now, data=data)
    return data


def _via_download(symbols):
    df = yf.download(symbols, period="5d", interval="1m", progress=False, auto_adjust=False,
                     group_by="ticker", threads=True, prepost=False)
    avg = _avg_volume(symbols)
    out = {}
    for s in symbols:
        try:
            t = df[s].dropna(subset=["Close"])
            if t.empty:
                continue
            days = sorted(set(t.index.date))
            today, prev_day = days[-1], (days[-2] if len(days) > 1 else None)
            td = t[[d == today for d in t.index.date]]
            price = float(td["Close"].iloc[-1])
            prev = float(t[[d == prev_day for d in t.index.date]]["Close"].iloc[-1]) if prev_day else None
            out[s] = {"price": price, "prevClose": prev, "changePct": (price / prev - 1) * 100 if prev else None,
                      "volume": float(td["Volume"].sum()), "avgVolume": avg.get(s), "marketState": None}
        except Exception:
            continue
    if not out:
        raise RuntimeError("download fallback: empty result")
    return out


def _via_finnhub(symbols):
    if not FINNHUB_KEY:
        raise RuntimeError("FINNHUB_KEY 미설정")
    out = {}
    for s in symbols:
        u = f"https://finnhub.io/api/v1/quote?symbol={s}&token={FINNHUB_KEY}"
        with urllib.request.urlopen(u, timeout=10) as r:
            d = json.load(r)
        if d.get("c"):
            out[s] = {"price": d["c"], "prevClose": d.get("pc"), "changePct": d.get("dp"),
                      "volume": None, "avgVolume": None, "marketState": None}
        time.sleep(1.05)  # 60회/분 한도
    if not out:
        raise RuntimeError("finnhub: empty result")
    return out


def get_quotes(symbols):
    key = ",".join(symbols)
    with _lock:
        if _cache["key"] == key and time.time() - _cache["t"] < CACHE_SEC:
            return _cache["data"]
        errors = []
        for name, fn in (("yahoo-v7", _via_v7), ("yahoo-download", _via_download), ("finnhub", _via_finnhub)):
            try:
                data = fn(symbols)
                _cache.update(t=time.time(), key=key, data={"quotes": data, "source": name, "ts": int(time.time())})
                return _cache["data"]
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}: {e}")
                print(f"[{name} 실패] {e}", file=sys.stderr)
        if _cache["data"]:            # 모두 실패 → 마지막 성공값이라도 반환
            return dict(_cache["data"], stale=True)
        raise RuntimeError(" | ".join(errors))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/quotes":
            syms = [s.strip().upper() for s in parse_qs(u.query).get("symbols", [""])[0].split(",") if s.strip()][:60]
            try:
                body, code = json.dumps(get_quotes(syms)).encode(), 200
            except Exception as e:
                body, code = json.dumps({"error": str(e)}).encode(), 502
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path == "/healthz":
            self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"ok"); return
        if u.path in ("/", ""):
            self.path = "/soxl_dashboard.html"
        return super().do_GET()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"listening on 0.0.0.0:{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
