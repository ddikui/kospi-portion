#!/usr/bin/env python3
"""코스피 상장 주식의 시가총액 비중을 제공하는 로컬 서버."""

from __future__ import annotations

import json
import math
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8787
CACHE_TTL_SECONDS = 180
PAGE_SIZE = 100
ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "public" if (ROOT / "public").exists() else (ROOT / "static")
CA_FILE = "/etc/ssl/cert.pem"


def create_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    if Path(CA_FILE).exists():
        return ssl.create_default_context(cafile=CA_FILE)
    return ssl.create_default_context()


SSL_CONTEXT = create_ssl_context()

MARKET_URL = (
    "https://m.stock.naver.com/api/stocks/marketValue/KOSPI"
    "?page={page}&pageSize={size}"
)
INDEX_URL = "https://m.stock.naver.com/api/index/KOSPI/basic"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

_cache_lock = threading.Lock()
_cache: dict | None = None
_cache_at = 0.0


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers=HEADERS,
    )
    with urllib.request.urlopen(request, timeout=20, context=SSL_CONTEXT) as response:
        return json.load(response)


def fetch_page(page: int) -> dict:
    url = MARKET_URL.format(page=page, size=PAGE_SIZE)
    last_error: Exception | None = None
    for _ in range(2):
        try:
            return fetch_json(url)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(0.3)
    raise RuntimeError(f"시세 페이지 {page}를 가져오지 못했습니다.") from last_error


def parse_number(value: str | int | float | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if text in {"", "N/A", "-"}:
        return 0.0
    return float(text)


def is_preferred(code: str) -> bool:
    # 거래소 단축코드 끝자리가 0이면 보통주, 그 외(5, 7, K 등)는 우선주 계열.
    return bool(code) and code[-1] != "0"


def build_payload() -> dict:
    first = fetch_page(1)
    total_count = int(first.get("totalCount") or PAGE_SIZE)
    page_count = max(1, math.ceil(total_count / PAGE_SIZE))
    pages = [first]
    if page_count > 1:
        with ThreadPoolExecutor(max_workers=8) as pool:
            pages.extend(pool.map(fetch_page, range(2, page_count + 1)))

    index = fetch_json(INDEX_URL)
    direction = (index.get("compareToPreviousPrice") or {}).get("name") or "UNCHANGED"

    seen: set[str] = set()
    stocks: list[dict] = []
    for page in pages:
        for item in page.get("stocks") or []:
            if item.get("stockEndType") != "stock":
                continue
            code = str(item.get("itemCode") or "")
            if not code or code in seen:
                continue
            market_cap = int(parse_number(item.get("marketValueRaw")))
            if market_cap <= 0:
                continue
            seen.add(code)
            change_direction = (item.get("compareToPreviousPrice") or {}).get("name") or "UNCHANGED"
            stocks.append(
                {
                    "code": code,
                    "name": item.get("stockName") or code,
                    "price": int(parse_number(item.get("closePriceRaw") or item.get("closePrice"))),
                    "change": int(parse_number(item.get("compareToPreviousClosePriceRaw"))),
                    "changeRate": parse_number(item.get("fluctuationsRatio")),
                    "direction": change_direction,
                    "marketCap": market_cap,
                    "volume": int(parse_number(item.get("accumulatedTradingVolumeRaw"))),
                    "tradingValue": int(parse_number(item.get("accumulatedTradingValueRaw"))),
                    "preferred": is_preferred(code),
                    "logo": item.get("itemLogoPngUrl") or "",
                    "tradedAt": item.get("localTradedAt") or "",
                }
            )

    stocks.sort(key=lambda row: row["marketCap"], reverse=True)
    total_cap = sum(row["marketCap"] for row in stocks)
    cumulative = 0
    for rank, row in enumerate(stocks, start=1):
        weight = (row["marketCap"] / total_cap * 100) if total_cap else 0.0
        cumulative += weight
        row["rank"] = rank
        row["weight"] = weight
        row["cumulative"] = cumulative

    def concentration(limit: int) -> float:
        return sum(row["weight"] for row in stocks[:limit])

    traded_at = stocks[0]["tradedAt"] if stocks else index.get("localTradedAt")
    return {
        "asOf": traded_at,
        "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "marketStatus": index.get("marketStatus") or first.get("marketStatus") or "",
        "source": "Naver Finance",
        "note": "상장 주식(보통주·우선주) 시가총액 합계 대비 비중입니다. ETF·ETN은 제외했고, 코스피 지수의 유동주식 비중과는 다릅니다.",
        "index": {
            "name": index.get("stockName") or "코스피",
            "close": parse_number(index.get("closePrice")),
            "change": parse_number(index.get("compareToPreviousClosePrice")),
            "changeRate": parse_number(index.get("fluctuationsRatio")),
            "direction": direction,
        },
        "totalMarketCap": total_cap,
        "stockCount": len(stocks),
        "commonCount": sum(1 for row in stocks if not row["preferred"]),
        "preferredCount": sum(1 for row in stocks if row["preferred"]),
        "concentration": {
            "top1": concentration(1),
            "top5": concentration(5),
            "top10": concentration(10),
            "top30": concentration(30),
        },
        "stocks": stocks,
    }


def get_market(force: bool = False) -> dict:
    global _cache, _cache_at
    now = time.time()
    with _cache_lock:
        if not force and _cache is not None and now - _cache_at < CACHE_TTL_SECONDS:
            payload = dict(_cache)
            payload["cached"] = True
            return payload
    payload = build_payload()
    payload["cached"] = False
    with _cache_lock:
        _cache = payload
        _cache_at = time.time()
    return payload


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/market":
            self.serve_market(force=False)
            return
        if parsed.path == "/api/market/refresh":
            self.serve_market(force=True)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def serve_market(self, force: bool) -> None:
        try:
            payload = get_market(force=force)
        except Exception as error:  # noqa: BLE001
            body = json.dumps(
                {"error": "시세를 가져오지 못했습니다.", "detail": str(error)},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")


def export_static(output_path: Path) -> None:
    print(f"시세 데이터를 수집하여 {output_path}에 저장합니다...")
    data = build_payload()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("저장 완료!")


def main() -> None:
    if "--export" in sys.argv:
        target = STATIC / "data" / "market.json"
        export_static(target)
        # root/data/market.json에도 복사
        root_target = ROOT / "data" / "market.json"
        root_target.parent.mkdir(parents=True, exist_ok=True)
        with open(root_target, "w", encoding="utf-8") as f:
            json.dump(build_payload(), f, ensure_ascii=False, indent=2)
        return

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"코스피 시가총액 비중  http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
