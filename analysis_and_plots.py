# Name: Harold Wilson
# Student ID: 4548 3282
# Email: hwil@umich.edu
# List any AI tool (e.g. ChatGPT, GitHub Copilot): ChatGPT assistance with API and database logic

import sqlite3
import json
import matplotlib.pyplot as plt
import os

DB_NAME = "stockx_data.db"

def check_db_exists(db_name: str = DB_NAME):
    """
    Simple check to ensure the database and tables exist 
    before trying to calculate metrics.
    """
    if not os.path.exists(db_name):
        print(f"Error: {db_name} not found. Run api_functions.py first.")
        return False

    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM market_data")
            count = cur.fetchone()[0]
            if count == 0:
                print("Warning: Database exists but 'market_data' table is empty.")
                print("You need to run api_functions.py to fetch data.")
                return False
            return True
    except sqlite3.OperationalError:
        print("Error: Database is missing required tables.")
        return False

def create_metrics(db_name: str = DB_NAME) -> dict:
    """
    Compute metrics aligned with the current schema:
    - StockX: average `lowest_ask` by `size` from `market_data`.
    - Kicks: average `lowest_ask` by `size` from `kicks_prices`.
    - Joined comparison: per-product/size pairs where both sources have data.
    """

    metrics = {
        "avg_price_by_size": {},
        "top_products_by_volume": {},
        "most_expensive_sales": {},
        "overall_avg_volume": 0
    }

    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()

            # StockX: average lowest_ask by size
            cur.execute(
                """
                SELECT size, AVG(lowest_ask)
                FROM market_data
                WHERE lowest_ask IS NOT NULL
                GROUP BY size
                ORDER BY size
            """)
            metrics["avg_price_by_size"] = {
                size: avg for size, avg in cur.fetchall()
            }

            # 2. Total sales volume per product (JOIN with product name)
            cur.execute("""
                SELECT p.name, SUM(m.sales_volume) AS total_volume
                FROM market_data AS m
                JOIN products AS p
                    ON m.product_id = p.product_id
                WHERE m.sales_volume IS NOT NULL
                GROUP BY m.product_id
                ORDER BY total_volume DESC
                LIMIT 10
            """)
            metrics["top_products_by_volume"] = {
                name: vol for name, vol in cur.fetchall()
            }

            # 3. Most Expensive Shoes (by Last Sale Price)
            cur.execute("""
                SELECT p.name, m.last_sale
                FROM market_data AS m
                JOIN products AS p
                    ON m.product_id = p.product_id
                WHERE m.last_sale IS NOT NULL
                ORDER BY m.last_sale DESC
                LIMIT 10
            """)
            metrics["most_expensive_sales"] = {
                name: price for name, price in cur.fetchall()
            }

            # 4. Overall average sales volume
            cur.execute("""
                SELECT AVG(sales_volume)
                FROM market_data
                WHERE sales_volume IS NOT NULL
            """)
            row = cur.fetchone()
            metrics["overall_avg_volume"] = (
                row[0] if row and row[0] is not None else 0
            )
            metrics["kicks_avg_ask_by_size"] = {size: avg for size, avg in cur.fetchall()}

            # Joined samples: prefer exact size match; fallback to StockX 'ALL' vs Kicks sizes
            cur.execute(
                """
                SELECT p.name,
                       m.size,
                       COALESCE(m.lowest_ask, m.highest_bid) AS stockx_price,
                       k.lowest_ask AS kicks_price
                FROM market_data m
                JOIN kicks_prices k ON k.product_id = m.product_id AND k.size = m.size
                JOIN products p ON p.product_id = m.product_id
                WHERE COALESCE(m.lowest_ask, m.highest_bid) IS NOT NULL
                  AND k.lowest_ask IS NOT NULL
                UNION ALL
                SELECT p.name,
                       k.size,
                       COALESCE(m.lowest_ask, m.highest_bid) AS stockx_price,
                       k.lowest_ask AS kicks_price
                FROM market_data m
                JOIN kicks_prices k ON k.product_id = m.product_id
                JOIN products p ON p.product_id = m.product_id
                WHERE m.size = 'ALL'
                  AND COALESCE(m.lowest_ask, m.highest_bid) IS NOT NULL
                  AND k.lowest_ask IS NOT NULL
                ORDER BY 1, 2
                LIMIT 20
                """
            )
            metrics["stockx_vs_kicks_samples"] = [
                {"name": name, "size": size, "stockx_ask": sx, "kicks_ask": kk}
                for (name, size, sx, kk) in cur.fetchall()
            ]

    except sqlite3.Error as e:
        print("Database error:", e)

    return metrics

def write_metrics_to_file(metrics: dict, filename: str = "metrics_summary.json"):
    """
    Write the calculated metrics to a JSON file.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=4)
        print(f"Successfully saved metrics to {filename}")
    except IOError as e:
        print("File write error:", e)

def create_graphs(metrics: dict):
    """
    Create visualizations and save as PNG files.
    """

    # 1. Size vs average last sale price
    sizes = list(metrics["avg_price_by_size"].keys())
    avg_prices = list(metrics["avg_price_by_size"].values())

    if not sizes:
        print("No price-by-size data available for graph.")
    else:
        plt.figure(figsize=(10, 6))
        plt.bar(sizes, avg_prices, color='skyblue')
        plt.xlabel("Shoe Size")
        plt.ylabel("Average Last Sale Price ($)")
        plt.title("Average Last Sale Price by Size")
        plt.tight_layout()
        plt.savefig("avg_price_by_size.png")
        print("Saved graph: avg_price_by_size.png")
        plt.close()

    # 2. Product vs total sales volume (top 10)
    names = list(metrics["top_products_by_volume"].keys())
    # Shorten names for cleaner graph
    short_names = [n[:15] + "..." if len(n) > 15 else n for n in names]
    volumes = list(metrics["top_products_by_volume"].values())

    if not names:
        print("No product volume data available for graph.")
    else:
        plt.figure(figsize=(10, 6))
        plt.bar(short_names, volumes, color='salmon')
        plt.xticks(rotation=45, ha="right")
        plt.xlabel("Product")
        plt.ylabel("Total Sales Volume")
        plt.title("Top Products by Sales Volume")
        plt.tight_layout()
        plt.savefig("top_products_by_volume.png")
        print("Saved graph: top_products_by_volume.png")
        plt.close()

    # 3. Most Expensive Shoes (Top 10 by Price)
    exp_names = list(metrics["most_expensive_sales"].keys())
    short_exp_names = [n[:15] + "..." if len(n) > 15 else n for n in exp_names]
    prices = list(metrics["most_expensive_sales"].values())

    if not exp_names:
        print("No pricing data available for expensive shoes graph.")
    else:
        plt.figure(figsize=(10, 6))
        plt.bar(short_exp_names, prices, color='gold')
        plt.xticks(rotation=45, ha="right")
        plt.xlabel("Product")
        plt.ylabel("Last Sale Price ($)")
        plt.title("Top 10 Most Expensive Shoes (Last Sale)")
        plt.tight_layout()
        plt.savefig("most_expensive_shoes.png")
        print("Saved graph: most_expensive_shoes.png")
        plt.close()

def main():
    if not check_db_exists():
        return

    metrics = create_metrics()
    print(f"Overall average sales volume: {metrics['overall_avg_volume']:.2f}")
    
    write_metrics_to_file(metrics, "metrics_summary.json")
    create_graphs(metrics)

if __name__ == "__main__":
    main()