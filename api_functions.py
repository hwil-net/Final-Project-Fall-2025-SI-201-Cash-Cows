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
                    lowest_ask REAL, last_sale REAL, sales_volume INTEGER,
                    FOREIGN KEY (product_id) REFERENCES products(product_id))''')
    conn.commit()
    conn.close()

def get_api_products(search_term):
    resp = requests.get(f"{API_BASE}/catalog/search", headers=HEADERS,
                       params={"query": search_term, "pageSize": 25})
    return resp.json().get("products", []) if resp.status_code == 200 else []

def get_market_data(product_id):
    resp = requests.get(f"{API_BASE}/catalog/products/{product_id}", headers=HEADERS)
    return resp.json() if resp.status_code == 200 else {}

def insert_api_data(product_data):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    attrs = product_data.get("productAttributes", {})
    cur.execute('''INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?)''',
                (product_data.get("productId"), product_data.get("title"), 
                 product_data.get("brand"), product_data.get("styleId"),
                 attrs.get("retailPrice"), attrs.get("releaseDate")))
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

     # test get_market_data 
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT product_id FROM products LIMIT 3")
    product_ids = [row[0] for row in cur.fetchall()]
    conn.close()
    
    print("\nTesting get_market_data:")
    for pid in product_ids:
        market = get_market_data(pid)
        print(f"{pid}: {market}")