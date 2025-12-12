import sqlite3
import requests
import time
import os

# --- 1. CONFIGURATION ---
# ⚠️ CRITICAL: Update this token! It expires every 30 mins.
ACCESS_TOKEN = "PASTE_YOUR_NEW_TOKEN_HERE"
API_KEY = "QkCTllvhmS5lxWCmPtc4INk44tYSZkx9LBGt9Mca"

API_BASE = "https://api.stockx.com/v2"
DB_NAME = "stockx_data.db"

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}", 
    "x-api-key": API_KEY,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- 2. SOURCE 2: COINDESK API (Bitcoin Price) ---
def get_btc_price():
    """Fetches Bitcoin price to satisfy 'Two APIs' requirement."""
    try:
        r = requests.get("https://api.coindesk.com/v1/bpi/currentprice.json")
        return r.json()["bpi"]["USD"]["rate_float"]
    except:
        return 0.0

# --- 3. DATABASE SETUP (Integer Keys) ---
def create_tables():
    # Force delete old DB if it exists to fix "no such column" errors
    # (Only needed during development/testing phases)
    # if os.path.exists(DB_NAME):
    #     os.remove(DB_NAME) 
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Enable Foreign Keys
    cur.execute("PRAGMA foreign_keys = ON")

    # TABLE 1: PRODUCTS (Uses Integer ID 'id')
    cur.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    stockx_uuid TEXT UNIQUE, 
                    name TEXT, 
                    brand TEXT, 
                    retail_price REAL
                )''')
    
    # TABLE 2: MARKET_DATA (Links to Integer ID 'product_internal_id')
    cur.execute('''CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    product_internal_id INTEGER, 
                    size TEXT,
                    last_sale_usd REAL, 
                    last_sale_btc REAL,
                    FOREIGN KEY (product_internal_id) REFERENCES products(id)
                )''')
    conn.commit()
    conn.close()

# --- 4. DATA COLLECTION ---
def run_collection():
    create_tables()
    
    print("\n--- STOCKX PART 2 COLLECTOR ---")
    # Requirement: "limit how much data you store ... to 25 items"
    # We ask for user input so you can run this multiple times for different shoes.
    term = input("Enter a shoe to search (e.g. 'Jordan 4'): ")
    if not term: return

    # 1. Get BTC Price (2nd API)
    btc_price = get_btc_price()
    print(f"💰 BTC Price: ${btc_price:,.2f}")

    # 2. Get StockX Data (1st API) - LIMIT 25
    params = {"query": term, "limit": 25, "dataType": "product"}
    
    try:
        print(f"🔎 Searching StockX for '{term}'...")
        resp = requests.get(f"{API_BASE}/catalog/search", headers=HEADERS, params=params)
        
        if resp.status_code == 401:
            print("❌ Error: Access Token Expired! Please get a new one from your browser.")
            return
        
        items = resp.json().get("products", [])
        print(f"   -> Found {len(items)} items.")
        
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        count = 0
        
        for p in items:
            # Extract Data
            uuid = p.get("id")
            title = p.get("title")
            brand = p.get("brand")
            
            # Safe Retail Price Extraction
            retail = 0
            for t in p.get("traits", []):
                if "Retail" in t.get("name", ""):
                    try:
                        val = str(t.get("value", 0)).replace("$", "").replace(",", "")
                        retail = float(val)
                    except: pass
            
            # Market Data
            stats = p.get("market", {}).get("salesInformation", {})
            last_sale = float(stats.get("lastSale", 0) or 0)
            
            # Calculate BTC Value
            price_btc = last_sale / btc_price if btc_price else 0

            if uuid:
                # A. Insert into Products (Ignore dupes)
                cur.execute('''INSERT OR IGNORE INTO products (stockx_uuid, name, brand, retail_price)
                               VALUES (?,?,?,?)''', (uuid, title, brand, retail))
                
                # B. Get the Integer ID
                cur.execute("SELECT id FROM products WHERE stockx_uuid = ?", (uuid,))
                row = cur.fetchone()
                
                if row:
                    internal_id = row[0]
                    # C. Insert Market Data (Linking to Integer ID)
                    cur.execute('''INSERT INTO market_data (product_internal_id, size, last_sale_usd, last_sale_btc)
                                   VALUES (?, ?, ?, ?)''', (internal_id, "Avg", last_sale, price_btc))
                    count += 1
        
        conn.commit()
        
        # Verify Insertion
        print(f"✅ Saved {count} items.")
        
        # Test Verification Block (Fixed to check correct columns)
        print("\n--- VERIFICATION ---")
        cur.execute("SELECT id, name, retail_price FROM products ORDER BY id DESC LIMIT 3")
        rows = cur.fetchall()
        for r in rows:
            print(f"ID: {r[0]} | Name: {r[1]} | Retail: ${r[2]}")
            
        conn.close()
        
        print("\n💡 NOTE: Run this script 3 more times with different shoes to reach 100 items!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # If you still get "no such column" errors, uncomment the next line once to reset the DB:
    if os.path.exists(DB_NAME): os.remove(DB_NAME)
    
    run_collection()