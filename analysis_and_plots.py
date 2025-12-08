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
