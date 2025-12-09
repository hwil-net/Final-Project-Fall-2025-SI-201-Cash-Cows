# Name: Harold Wilson
# Student ID: 4548 3282
# Email: hwil@umich.edu
# List any AI tool (e.g. ChatGPT, GitHub Copilot): ChatGPT assistance with API and database logic

import sqlite3
import json
import matplotlib.pyplot as plt

DB_NAME = "stockx_data.db"


def create_metrics(db_name: str = DB_NAME) -> dict:
    """
    Read data from the products and market_data tables
    and compute summary metrics for the project.
    """

    conn = sqlite3.connect(db_name)
    cur = conn.cursor()

    # 1. Average last sale price by size
    cur.execute("""
        SELECT size, AVG(last_sale)
        FROM market_data
        WHERE last_sale IS NOT NULL
        GROUP BY size
        ORDER BY size
    """)
    avg_price_by_size = {size: avg for size, avg in cur.fetchall()}

    # 2. Total sales volume per product (joined with product name)
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
    top_products_by_volume = {name: vol for name, vol in cur.fetchall()}

    # 3. Overall average sales volume (optional extra metric)
    cur.execute("""
        SELECT AVG(sales_volume)
        FROM market_data
        WHERE sales_volume IS NOT NULL
    """)
    row = cur.fetchone()
    overall_avg_volume = row[0] if row and row[0] is not None else 0

    conn.close()

    return {
        "avg_price_by_size": avg_price_by_size,
        "top_products_by_volume": top_products_by_volume,
        "overall_avg_volume": overall_avg_volume
    }


def write_metrics_to_file(metrics: dict, filename: str = "metrics_summary.json"):
    """
    Write the calculated metrics to a JSON file.
    This covers the 'write data file from calculations' requirement.
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)


def create_graphs(metrics: dict):
    """
    Create visualizations:
    1) Bar chart: shoe size vs average last sale price
    2) Bar chart: top products vs total sales volume
    Both are saved as PNG files and shown on screen.
    """

    # 1. Size vs average last sale price
    sizes = list(metrics["avg_price_by_size"].keys())
    avg_prices = list(metrics["avg_price_by_size"].values())

    if sizes:
        plt.figure()
        plt.bar(sizes, avg_prices)
        plt.xlabel("Shoe size")
        plt.ylabel("Average last sale price")
        plt.title("Average last sale price by size")
        plt.tight_layout()
        plt.savefig("avg_price_by_size.png")
        plt.show()

    # 2. Product vs total sales volume (top 10)
    names = list(metrics["top_products_by_volume"].keys())
    volumes = list(metrics["top_products_by_volume"].values())

    if names:
        plt.figure()
        plt.bar(names, volumes)
        plt.xticks(rotation=45, ha="right")
        plt.xlabel("Product")
        plt.ylabel("Total sales volume")
        plt.title("Top products by sales volume")
        plt.tight_layout()
        plt.savefig("top_products_by_volume.png")
        plt.show()


def main():
    metrics = create_metrics()
    print("Overall average sales volume:", metrics["overall_avg_volume"])
    write_metrics_to_file(metrics, "metrics_summary.json")
    create_graphs(metrics)


if __name__ == "__main__":
    main()
