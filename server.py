import os
import csv
import io
import json
import time
import urllib.request
import urllib.error

from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN")

INSTRUMENT_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
QUOTE_URL = "https://api.dhan.co/v2/marketfeed/quote"

# Initial watchlist
WATCHLIST = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "ITC",
    "LT",
    "BHARTIARTL",
    "HINDALCO",
    "TATAMOTORS",
    "MARUTI"
]

instrument_cache = {}
instrument_cache_time = 0


def download_instruments():

    global instrument_cache
    global instrument_cache_time

    # Cache for 6 hours
    if instrument_cache and time.time() - instrument_cache_time < 21600:
        return instrument_cache

    try:

        request = urllib.request.Request(
            INSTRUMENT_URL,
            headers={"User-Agent": "Live-Market-Dashboard"}
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read().decode("utf-8", errors="ignore")

        reader = csv.DictReader(io.StringIO(content))

        result = {}

        for row in reader:

            exchange = row.get("SEM_EXM_EXCH_ID", "")
            segment = row.get("SEM_SEGMENT", "")
            instrument = row.get("SEM_INSTRUMENT_NAME", "")
            symbol = row.get("SEM_TRADING_SYMBOL", "")
            security_id = row.get("SEM_SMST_SECURITY_ID", "")
            name = row.get("SM_SYMBOL_NAME", "") or symbol

            # NSE Equity only
            if (
                exchange == "NSE"
                and segment == "E"
                and instrument == "EQUITY"
                and symbol in WATCHLIST
                and security_id
            ):
                result[symbol] = {
                    "security_id": security_id,
                    "name": name
                }

        instrument_cache = result
        instrument_cache_time = time.time()

        return result

    except Exception as e:
        print("Instrument download error:", e)
        return instrument_cache


def get_market_data():

    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:

        return {
            "status": "Dhan credentials not configured",
            "stocks": []
        }

    instruments = download_instruments()

    if not instruments:

        return {
            "status": "Instrument list unavailable",
            "stocks": []
        }

    security_ids = [
        item["security_id"]
        for item in instruments.values()
    ]

    payload = {
        "NSE_EQ": [int(x) for x in security_ids]
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        QUOTE_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "access-token": DHAN_ACCESS_TOKEN,
            "client-id": DHAN_CLIENT_ID
        }
    )

    try:

        with urllib.request.urlopen(request, timeout=15) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

        stocks = []

        quote_data = result.get("data", {}).get("NSE_EQ", {})

        for symbol, info in instruments.items():

            security_id = str(info["security_id"])

            item = quote_data.get(security_id)

            if not item:
                continue

            price = float(item.get("last_price", 0) or 0)

            ohlc = item.get("ohlc", {}) or {}

            previous_close = float(
                ohlc.get("close", 0) or 0
            )

            volume = int(
                item.get("volume", 0) or 0
            )

            change_percent = 0

            if previous_close > 0:

                change_percent = (
                    (price - previous_close)
                    / previous_close
                ) * 100

            stocks.append({
                "symbol": symbol,
                "name": info["name"],
                "exchange": "NSE",
                "price": price,
                "change_percent": change_percent,
                "volume": volume
            })

        return {
            "status": "Dhan live market connected",
            "stocks": stocks,
            "server_time": int(time.time())
        }

    except urllib.error.HTTPError as e:

        error_text = ""

        try:
            error_text = e.read().decode("utf-8")
        except Exception:
            pass

        print("Dhan HTTP error:", e.code, error_text)

        return {
            "status": "Dhan API error",
            "stocks": [],
            "error": error_text
        }

    except Exception as e:

        print("Dhan API error:", e)

        return {
            "status": "Dhan connection error",
            "stocks": [],
            "error": str(e)
        }


@app.route("/")
def home():

    return send_from_directory(".", "index.html")


@app.route("/api/dashboard")
def dashboard():

    return jsonify(get_market_data())


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 8080))

    app.run(
        host="0.0.0.0",
        port=port
    )
