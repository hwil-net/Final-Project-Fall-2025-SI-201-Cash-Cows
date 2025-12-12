# Name: Dezmond Blair
# Student ID: 7083 2724
# Email: dezb@umich.edu
# List any AI tool (e.g. ChatGPT, GitHub Copilot): ChatGPT assistance with API requests and database logic


import sqlite3
import requests
from config import API_KEY, ACCESS_TOKEN

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
    
    # Show what we got
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM market_data")
    print(f"\nMarket data rows: {cur.fetchone()[0]}")
    cur.execute("SELECT product_id, size, lowest_ask, highest_bid, sell_faster FROM market_data LIMIT 5")
    print("Sample market data:")
    for row in cur.fetchall():
        print(f"  {row}")
    conn.close()