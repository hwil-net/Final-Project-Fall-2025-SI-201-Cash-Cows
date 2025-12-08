# Name: Harold Wilson
# Student ID: 4548 3282
# Email: hwil@umich.edu
# List any AI tool (e.g. ChatGPT, GitHub Copilot): ChatGPT assistance with API requests and database logic


import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt


# Scrape product page
def scrape_product_page(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    def safe_text(selector):
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else None

    # These selectors may need adjustment after HTML inspection
    release_date = safe_text("[data-testid='product-detail-release-date']")
    colorway     = safe_text("[data-testid='product-detail-colorway']")
    silhouette   = safe_text("[data-testid='product-detail-silhouette']")
    retail_price = safe_text("[data-testid='product-detail-retail-price']")
    description  = safe_text("[data-testid='product-detail-description']")

    retail_price_val = None
    if retail_price:
        price_digits = "".join(ch for ch in retail_price if ch.isdigit() or ch == ".")
        retail_price_val = float(price_digits) if price_digits else None

    product_id = url.rstrip("/").split("/")[-1]

    return {
        "product_id": product_id,
        "release_date": release_date,
        "colorway": colorway,
        "silhouette": silhouette,
        "retail_price": retail_price_val,
        "description": description
    }

def insert_scraped_info(info: dict, db_name: str = DB_NAME):
    conn = sqlite3.connect(db_name)
    cur = conn.cursor()

    cur.execute("SELECT id FROM products WHERE stockx_id = ?", (info["slug"],))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return
    product_id_int = row[0]

    cur.execute("""
        INSERT INTO scraped_info
        (product_id, release_date, colorway, silhouette, retail_price, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        product_id_int,
        info["release_date"],
        info["colorway"],
        info["silhouette"],
        info["retail_price"],
        info["description"]
    ))

    conn.commit()
    conn.close()


def create_metrics(db_name: str = DB_NAME) -> dict:
    conn = sqlite3.connect(db_name)
    cur = conn.cursor()

    cur.execute("""
        SELECT SUM(sales_volume), MIN(sale_date), MAX(sale_date)
        FROM market_data
        WHERE sale_date IS NOT NULL
    """)
    total_pairs, min_date, max_date = cur.fetchone()

    if min_date and max_date and total_pairs:
        d0 = datetime.strptime(min_date, "%Y-%m-%d").date()
        d1 = datetime.strptime(max_date, "%Y-%m-%d").date()
        num_days = (d1 - d0).days + 1
        avg_pairs_sold_per_day = total_pairs / num_days if num_days > 0 else 0
    else:
        avg_pairs_sold_per_day = 0

    cur.execute("""
        SELECT m.size, AVG(m.last_sale_price)
        FROM market_data m
        JOIN products p ON m.product_id = p.id
        WHERE m.last_sale_price IS NOT NULL
        GROUP BY m.size
    """)
    avg_price_by_size = {size: avg for size, avg in cur.fetchall()}

    cur.execute("""
        SELECT sale_date, SUM(sales_volume)
        FROM market_data
        WHERE sale_date IS NOT NULL
        GROUP BY sale_date
        ORDER BY sale_date
    """)
    daily_pairs_sold = {date_str: total for date_str, total in cur.fetchall()}

    conn.close()

    return {
        "avg_pairs_sold_per_day": avg_pairs_sold_per_day,
        "avg_price_by_size": avg_price_by_size,
        "daily_pairs_sold": daily_pairs_sold
    }