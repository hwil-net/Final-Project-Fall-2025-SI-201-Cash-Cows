# Name: Dezmond Blair
# Student ID: 7083 2724
# Email: dezb@umich.edu
# List any AI tool (e.g. ChatGPT, GitHub Copilot): ChatGPT assistance with API requests and database logic


import sqlite3
import requests
from config import API_KEY, ACCESS_TOKEN, KICKS_API_KEY

API_BASE = "https://api.stockx.com/v2"
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "x-api-key": API_KEY}
DB_NAME = "stockx_data.db"

def create_tables():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS products
                   (product_id TEXT PRIMARY KEY, name TEXT, brand TEXT, 
                    style_id TEXT, retail_price REAL, release_date TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS market_data
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT, size TEXT,
                    lowest_ask REAL, highest_bid REAL, sell_faster REAL,
                    FOREIGN KEY (product_id) REFERENCES products(product_id))''')
    # kicks.dev historical snapshot table
    cur.execute('''CREATE TABLE IF NOT EXISTS kicks_history
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT,
                    historical_average REAL, last_sale REAL, sales_last_72h INTEGER,
                    FOREIGN KEY (product_id) REFERENCES products(product_id))''')
    # optional: us market extras from kicks (earn_more)
    cur.execute('''CREATE TABLE IF NOT EXISTS kicks_us_market
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT,
                    historical_average REAL, last_sale REAL, sales_last_72h INTEGER,
                    sell_faster REAL, earn_more REAL,
                    FOREIGN KEY (product_id) REFERENCES products(product_id))''')
    # kicks detailed variant prices (from display[variants]/display[prices])
    cur.execute('''CREATE TABLE IF NOT EXISTS kicks_prices
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT,
                    size TEXT, lowest_ask REAL, asks INTEGER, price_type TEXT, updated_at TEXT,
                    FOREIGN KEY (product_id) REFERENCES products(product_id))''')
    conn.commit()
    conn.close()

def get_api_products(search_term):
    resp = requests.get(f"{API_BASE}/catalog/search", headers=HEADERS,
                       params={"query": search_term, "pageSize": 25})
    return resp.json().get("products", []) if resp.status_code == 200 else []

def get_market_data(product_id):
    # grab market data for a product
    resp = requests.get(f"{API_BASE}/catalog/products/{product_id}/market-data", headers=HEADERS)
    if resp.status_code != 200:
        print(f"    Market data error for {product_id}: status {resp.status_code}")
        return {}
    return resp.json()

def get_variants(product_id):
    # get different sizes for a product
    resp = requests.get(f"{API_BASE}/catalog/products/{product_id}/variants", headers=HEADERS)
    if resp.status_code == 200:
        data = resp.json()
        # Handle both list and dict responses
        return data if isinstance(data, list) else data.get("variants", [])
    return []

def get_variant_market_data(product_id, variant_id):
    # market data for one specific size
    resp = requests.get(f"{API_BASE}/catalog/products/{product_id}/variants/{variant_id}/market-data", headers=HEADERS)
    return resp.json() if resp.status_code == 200 else {}

def insert_api_data(product_data):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    attrs = product_data.get("productAttributes", {})
    product_id = product_data.get("productId")
    
    cur.execute('''INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?)''',
                (product_id, product_data.get("title"), 
                 product_data.get("brand"), product_data.get("styleId"),
                 attrs.get("retailPrice"), attrs.get("releaseDate")))
    conn.commit()
    conn.close()
    return product_id

def insert_market_data(product_id, size, lowest_ask, highest_bid, sell_faster):
    # save market data to db
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''INSERT INTO market_data (product_id, size, lowest_ask, highest_bid, sell_faster)
                   VALUES (?, ?, ?, ?, ?)''',
                (product_id, size, lowest_ask, highest_bid, sell_faster))
    conn.commit()
    conn.close()

def get_historical_data(query_term):
    # kicks.dev price history snapshot for a query term
    url = "https://api.kicks.dev/v3/stockx/products"
    headers = {"Authorization": f"Bearer {KICKS_API_KEY}", "Content-Type": "application/json"}
    params = {"query": query_term, "limit": 1}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("data") or []
        if not items:
            return None
        p = items[0]
        market = p.get("market", {})
        # try multiple possible field names commonly seen
        historical_avg = (market.get("averageDeadstockPrice")
                          or market.get("avgDeadstockPrice")
                          or market.get("avg_price"))
        last_sale = market.get("lastSale") or market.get("last_sale")
        sales_72h = (market.get("salesLast72Hours")
                     or market.get("sales_72h")
                     or market.get("ordersLast72Hours"))
        sell_faster = market.get("sellFaster") or market.get("sell_faster")
        earn_more = market.get("earnMore") or market.get("earn_more")
        return {
            "name": p.get("title"),
            "style_id": p.get("styleId"),
            "historical_average": historical_avg,
            "last_sale": last_sale,
            "sales_last_72h": sales_72h,
            "sell_faster": sell_faster,
            "earn_more": earn_more
        }
    except requests.exceptions.RequestException as e:
        print(f"error fetching kicks.dev: {e}")
        return None

def insert_kicks_history_for_style(style_id, hist):
    # find matching product by style_id, then save kicks snapshot
    if not hist or not style_id:
        return
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT product_id FROM products WHERE style_id = ? LIMIT 1", (style_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
    product_id = row[0]
    cur.execute('''INSERT INTO kicks_history (product_id, historical_average, last_sale, sales_last_72h)
                   VALUES (?, ?, ?, ?)''',
                (product_id, hist.get("historical_average"), hist.get("last_sale"), hist.get("sales_last_72h") or 0))
    conn.commit()
    conn.close()

def get_kicks_market_data(shoe_name):
    # kicks.dev simple market snapshot (free tier, US default)
    url = "https://api.kicks.dev/v3/stockx/products"
    headers = {"Authorization": f"Bearer {KICKS_API_KEY}", "Content-Type": "application/json"}
    params = {"query": shoe_name, "limit": 1}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 403:
            print("kicks 403: forbidden (restricted/paid endpoint)")
            return None
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("data") or []
        if not items:
            print(f"no kicks data for {shoe_name}")
            return None
        p = items[0]
        m = p.get("market", {})
        return {
            "name": p.get("title"),
            "style_id": p.get("styleId"),
            "past_avg_price": m.get("averageDeadstockPrice"),
            "last_sale_price": m.get("lastSale"),
            "total_sold": m.get("salesLast72Hours")
        }
    except requests.exceptions.RequestException as e:
        print(f"kicks api error: {e}")
        return None

def get_kicks_product_id_or_slug(term):
    # resolve product id/slug via search
    url = "https://api.kicks.dev/v3/stockx/products"
    headers = {"Authorization": f"Bearer {KICKS_API_KEY}", "Content-Type": "application/json"}
    params = {"query": term, "limit": 1}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        items = (resp.json().get("data") or [])
        if not items:
            return None
        p = items[0]
        return {"id": p.get("id"), "slug": p.get("slug"), "title": p.get("title")}
    except requests.exceptions.RequestException as e:
        print(f"kicks resolve error: {e}")
        return None

def get_kicks_product_detail(id_or_slug, include_variants=True, include_prices=True):
    # fetch product with variants/prices using display flags
    url = f"https://api.kicks.dev/v3/stockx/products/{id_or_slug}"
    headers = {"Authorization": f"Bearer {KICKS_API_KEY}", "Content-Type": "application/json"}
    params = {}
    if include_variants:
        params["display[variants]"] = "true"
    if include_prices:
        params["display[prices]"] = "true"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("data") or {}
    except requests.exceptions.RequestException as e:
        print(f"kicks detail error: {e}")
        return {}

def insert_kicks_prices_for_style(style_id, detail):
    # store up to 5 price rows mapped to product_id
    if not detail:
        return
    variants = detail.get("variants") or []
    if not variants:
        return
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT product_id FROM products WHERE style_id = ? LIMIT 1", (style_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
    pid = row[0]
    count = 0
    for v in variants:
        size = v.get("size")
        lowest_ask = v.get("lowest_ask")
        updated_at = v.get("updated_at")
        prices = v.get("prices") or []
        # choose first price entry if present
        price_entry = prices[0] if prices else None
        asks = price_entry.get("asks") if price_entry else None
        price_type = price_entry.get("type") if price_entry else None
        cur.execute('''INSERT INTO kicks_prices (product_id, size, lowest_ask, asks, price_type, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (pid, size, lowest_ask, asks, price_type, updated_at))
        count += 1
        if count >= 5:
            break
    conn.commit()
    conn.close()
def insert_kicks_us_market_for_style(style_id, hist):
    # store available us market fields from kicks
    if not hist:
        return
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT product_id FROM products WHERE style_id = ? LIMIT 1", (style_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
    pid = row[0]
    cur.execute('''INSERT INTO kicks_us_market (product_id, historical_average, last_sale, sales_last_72h, sell_faster, earn_more)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (pid,
                 hist.get("historical_average"),
                 hist.get("last_sale"),
                 hist.get("sales_last_72h") or 0,
                 hist.get("sell_faster"),
                 hist.get("earn_more")))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
    
    # use multiple search terms to get 100 items in db
    search_terms = ["jordan 4", "yeezy 350", "dunk low", "air force 1"]
    total = 0
    
    for term in search_terms:
        products = get_api_products(term)
        print(f"{term}: {len(products)} products")
        for p in products:
            insert_api_data(p)
            total += 1
    
    print(f"\nTotal rows inserted: {total}")

    # Fetch market data for products
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT product_id FROM products LIMIT 5")
    product_ids = [row[0] for row in cur.fetchall()]
    conn.close()
    
    print("\nFetching market data:")
    for pid in product_ids:
        # grab pricing info
        market = get_market_data(pid)
        
        # api can return different formats
        if isinstance(market, list):
            # list of variants
            print(f"  {pid}: found {len(market)} variants")
            for variant_data in market[:3]:  # Limit to 3 variants
                std = variant_data.get("standardMarketData", {})
                var_id = variant_data.get("variantId")
                lowest = std.get("lowestAsk")
                highest_bid = std.get("highestBidAmount")
                sell_faster = std.get("sellFaster")
                
                if lowest:
                    insert_market_data(pid, str(var_id)[:8], lowest, highest_bid, sell_faster)
        elif market:
            # dict format
            std = market.get("standardMarketData", market)
            lowest = std.get("lowestAsk")
            highest_bid = std.get("highestBidAmount")
            sell_faster = std.get("sellFaster")
            print(f"  {pid}: lowestAsk=${lowest}, highestBid=${highest_bid}")
            
            # save it
            if lowest or highest_bid:
                insert_market_data(pid, "ALL", lowest, highest_bid, sell_faster)
        
            # check individual sizes
            variants = get_variants(pid)
            for v in variants[:3]:  # Limit to 3 sizes per product
                var_id = v.get("id")
                size = v.get("sizeChart", {}).get("displayOptions", [{}])[0].get("size", "N/A")
                
                var_market = get_variant_market_data(pid, var_id)
                if var_market:
                    std = var_market.get("standardMarketData", var_market)
                    insert_market_data(pid, size, std.get("lowestAsk"), std.get("highestBidAmount"), std.get("sellFaster"))

    # kicks.dev: store up to 5 historical snapshots per run (<=25 items rule)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT name, style_id FROM products WHERE style_id IS NOT NULL LIMIT 5")
    samples = cur.fetchall()
    conn.close()
    for name, style_id in samples:
        hist = get_historical_data(name)
        if hist:
            # extend with us market fields when present
            # map kicks market to our snapshot
            # sell_faster/earn_more may be available
            insert_kicks_history_for_style(style_id, hist)
            insert_kicks_us_market_for_style(style_id, {
                "historical_average": hist.get("historical_average"),
                "last_sale": hist.get("last_sale"),
                "sales_last_72h": hist.get("sales_last_72h"),
                "sell_faster": hist.get("sell_faster"),
                "earn_more": hist.get("earn_more")
            })
        # kicks detailed product with variants/prices
        resolved = get_kicks_product_id_or_slug(name)
        if resolved:
            id_or_slug = resolved.get("slug") or resolved.get("id")
            detail = get_kicks_product_detail(id_or_slug, include_variants=True, include_prices=True)
            if detail:
                insert_kicks_prices_for_style(style_id, detail)
    
    # Show what we got
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM market_data")
    print(f"\nMarket data rows: {cur.fetchone()[0]}")
    cur.execute("SELECT product_id, size, lowest_ask, highest_bid, sell_faster FROM market_data LIMIT 5")
    print("Sample market data:")
    for row in cur.fetchall():
        print(f"  {row}")
    # show kicks snapshots
    cur.execute("SELECT COUNT(*) FROM kicks_history")
    print(f"kicks history rows: {cur.fetchone()[0]}")
    cur.execute("SELECT product_id, historical_average, last_sale, sales_last_72h FROM kicks_history LIMIT 5")
    print("Sample kicks history:")
    for row in cur.fetchall():
        print(f"  {row}")
    # show kicks us market
    cur.execute("SELECT COUNT(*) FROM kicks_us_market")
    print(f"kicks us market rows: {cur.fetchone()[0]}")
    cur.execute("SELECT product_id, historical_average, last_sale, sales_last_72h, sell_faster, earn_more FROM kicks_us_market LIMIT 5")
    print("Sample kicks us market:")
    for row in cur.fetchall():
        print(f"  {row}")
    # show kicks prices
    cur.execute("SELECT COUNT(*) FROM kicks_prices")
    print(f"kicks prices rows: {cur.fetchone()[0]}")
    cur.execute("SELECT product_id, size, lowest_ask, asks, price_type, updated_at FROM kicks_prices LIMIT 5")
    print("Sample kicks prices:")
    for row in cur.fetchall():
        print(f"  {row}")
    conn.close()