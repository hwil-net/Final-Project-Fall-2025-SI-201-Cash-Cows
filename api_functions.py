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
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, product_key INTEGER, size TEXT,
                    lowest_ask REAL, highest_bid REAL, sell_faster REAL,
                    FOREIGN KEY (product_key) REFERENCES product_lookup(product_key))''')
    # kicks.dev historical snapshot table
    cur.execute('''CREATE TABLE IF NOT EXISTS kicks_history
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, product_key INTEGER,
                    historical_average REAL, last_sale REAL, sales_last_72h INTEGER,
                    FOREIGN KEY (product_key) REFERENCES product_lookup(product_key))''')
    # optional: us market extras from kicks (earn_more)
    cur.execute('''CREATE TABLE IF NOT EXISTS kicks_us_market
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, product_key INTEGER,
                    historical_average REAL, last_sale REAL, sales_last_72h INTEGER,
                    sell_faster REAL, earn_more REAL,
                    FOREIGN KEY (product_key) REFERENCES product_lookup(product_key))''')
    # kicks detailed variant prices (from display[variants]/display[prices])
    cur.execute('''CREATE TABLE IF NOT EXISTS kicks_prices
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, product_key INTEGER,
                    size TEXT, lowest_ask REAL, asks INTEGER, price_type TEXT, updated_at TEXT,
                    FOREIGN KEY (product_key) REFERENCES product_lookup(product_key))''')
    # lookup table for integer keys
    cur.execute('''CREATE TABLE IF NOT EXISTS product_lookup
                   (product_key INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT UNIQUE)''')
    conn.commit()
    conn.close()

def ensure_product_keys():
    #ensure all products have an entry in product_lookup
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO product_lookup (product_id) SELECT product_id FROM products")
    conn.commit()
    conn.close()

def get_product_key(product_id):
    #get integer product_key for a product_id, creating lookup entry if needed.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO product_lookup (product_id) VALUES (?)", (product_id,))
    cur.execute("SELECT product_key FROM product_lookup WHERE product_id = ?", (product_id,))
    product_key = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return product_key

def get_api_products(search_term):
    resp = requests.get(f"{API_BASE}/catalog/search", headers=HEADERS,
                       params={"query": search_term, "pageSize": 25})
    return resp.json().get("products", []) if resp.status_code == 200 else []

def get_market_data(product_id):
    # grab market data for a product
    resp = requests.get(f"{API_BASE}/catalog/products/{product_id}/market-data", headers=HEADERS)
    if resp.status_code != 200:
        print(f"market data error for {product_id}: status {resp.status_code}")
        return {}
    return resp.json()

def get_variants(product_id):
    # get different sizes for a product
    resp = requests.get(f"{API_BASE}/catalog/products/{product_id}/variants", headers=HEADERS)
    if resp.status_code == 200:
        data = resp.json()
        # handle both list and dict responses
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
    # save market data using integer product_key 
    product_key = get_product_key(product_id)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''INSERT INTO market_data (product_key, size, lowest_ask, highest_bid, sell_faster)
                   VALUES (?, ?, ?, ?, ?)''',
                (product_key, size, lowest_ask, highest_bid, sell_faster))
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
    # save kicks history using integer product_key 
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
    product_key = get_product_key(product_id)
    cur.execute('''INSERT INTO kicks_history (product_key, historical_average, last_sale, sales_last_72h)
                   VALUES (?, ?, ?, ?)''',
                (product_key, hist.get("historical_average"), hist.get("last_sale"), hist.get("sales_last_72h") or 0))
    conn.commit()
    conn.close()



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
    # store kicks prices using integer product_key 
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
    product_key = get_product_key(pid)
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
        cur.execute('''INSERT INTO kicks_prices (product_key, size, lowest_ask, asks, price_type, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (product_key, size, lowest_ask, asks, price_type, updated_at))
        count += 1
        if count >= 5:
            break
    conn.commit()
    conn.close()
def insert_kicks_us_market_for_style(style_id, hist):
    # store kicks us market data using integer product_key 
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
    product_key = get_product_key(pid)
    cur.execute('''INSERT INTO kicks_us_market (product_key, historical_average, last_sale, sales_last_72h, sell_faster, earn_more)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (product_key,
                 hist.get("historical_average"),
                 hist.get("last_sale"),
                 hist.get("sales_last_72h") or 0,
                 hist.get("sell_faster"),
                 hist.get("earn_more")))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
    
    # Store ≤25 items per run
    search_terms = ["jordan 4", "yeezy 350", "dunk low", "air force 1"]
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products")
    current_count = cur.fetchone()[0]
    conn.close()
    
    term_index = (current_count // 25) % len(search_terms)
    term = search_terms[term_index]
    
    products = get_api_products(term)
    total = 0
    for p in products[:25]:  # Enforce 25-item limit per run
        insert_api_data(p)
        total += 1
    
    print(f"Run #{(current_count // 25) + 1}: Inserted {total} '{term}' products")
    print(f"Total in DB: {current_count + total}/100+")