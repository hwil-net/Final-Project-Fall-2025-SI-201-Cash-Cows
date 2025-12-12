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
    Compute metrics aligned with the current schema:
    - StockX: average `lowest_ask` by `size` from `market_data`.
    - Kicks: average `lowest_ask` by `size` from `kicks_prices`.
    - Joined comparison: per-product/size pairs where both sources have data.
    """

    metrics = {
        "stockx_avg_ask_by_size": {},
        "kicks_avg_ask_by_size": {},
        "stockx_vs_kicks_samples": []
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
                """
            )
            metrics["stockx_avg_ask_by_size"] = {size: avg for size, avg in cur.fetchall()}

            # Kicks: average lowest_ask by size
            cur.execute(
                """
                SELECT size, AVG(lowest_ask)
                FROM kicks_prices
                WHERE lowest_ask IS NOT NULL
                GROUP BY size
                ORDER BY size
                """
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
    This covers the 'write data file from calculations' requirement.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=4)
    except IOError as e:
        print("File write error:", e)


def create_graphs(metrics: dict):
    """
    Visualizations:
    1) Bar chart: size vs average StockX lowest ask.
    2) Bar chart: size vs average Kicks lowest ask.
    3) Grouped bar chart: StockX vs Kicks for joined samples.
    """

    # 1. StockX size vs average lowest ask
    sx_sizes = list(metrics["stockx_avg_ask_by_size"].keys())
    sx_avgs = list(metrics["stockx_avg_ask_by_size"].values())
    if sx_sizes:
        plt.figure()
        plt.bar(sx_sizes, sx_avgs)
        plt.xlabel("Shoe size")
        plt.ylabel("Avg StockX lowest ask ($)")
        plt.title("StockX Average Lowest Ask by Size")
        plt.tight_layout()
        plt.savefig("stockx_avg_ask_by_size.png")
        plt.show()
    else:
        print("No StockX price-by-size data available.")

    # 2. Kicks size vs average lowest ask
    kk_sizes = list(metrics["kicks_avg_ask_by_size"].keys())
    kk_avgs = list(metrics["kicks_avg_ask_by_size"].values())
    if kk_sizes:
        plt.figure()
        plt.bar(kk_sizes, kk_avgs, color="orange")
        plt.xlabel("Shoe size")
        plt.ylabel("Avg Kicks lowest ask ($)")
        plt.title("Kicks Average Lowest Ask by Size")
        plt.tight_layout()
        plt.savefig("kicks_avg_ask_by_size.png")
        plt.show()
    else:
        print("No Kicks price-by-size data available.")

    # 3. Grouped bars: StockX vs Kicks for joined samples
    samples = metrics.get("stockx_vs_kicks_samples", [])
    if samples:
        labels = [f"{s['name']} (sz {s['size']})" for s in samples]
        sx_vals = [s["stockx_ask"] or 0 for s in samples]
        kk_vals = [s["kicks_ask"] or 0 for s in samples]

        x = range(len(labels))
        width = 0.45
        plt.figure(figsize=(10, 5))
        plt.bar([i - width/2 for i in x], sx_vals, width=width, label="StockX", color="#4C78A8")
        plt.bar([i + width/2 for i in x], kk_vals, width=width, label="Kicks", color="#F58518")
        plt.xticks(list(x), labels, rotation=45, ha="right")
        plt.ylabel("Lowest Ask ($)")
        plt.title("StockX vs Kicks: Lowest Ask by Product & Size")
        plt.legend()
        plt.tight_layout()
        plt.savefig("stockx_vs_kicks_grouped.png")
        plt.show()
    else:
        print("No joined StockX vs Kicks samples available to plot.")


def main():
    metrics = create_metrics()
    write_metrics_to_file(metrics, "metrics_summary.json")
    create_graphs(metrics)


if __name__ == "__main__":
    main()
