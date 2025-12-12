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
    compute metrics aligned with the current schema:
    - stockx: average lowest_ask by size from market_data
    - kicks: average lowest_ask by size from kicks_prices
    - joined comparison: per-product samples where both sources have data
    """

    metrics = {
        "stockx_avg_ask_by_size": {},
        "kicks_avg_ask_by_size": {},
        "stockx_vs_kicks_samples": []
    }

    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()

            # stockx: average lowest_ask by size
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

            # kicks: average lowest_ask by size
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

            # joined samples at product level: use integer product_key for joins
            cur.execute(
                """
                WITH sx AS (
                  SELECT pl.product_key,
                         COALESCE(
                           (
                             SELECT COALESCE(m.lowest_ask, m.highest_bid)
                             FROM market_data m
                             WHERE m.product_key = pl.product_key
                               AND m.size = 'ALL'
                               AND COALESCE(m.lowest_ask, m.highest_bid) IS NOT NULL
                             LIMIT 1
                           ),
                           (
                             SELECT AVG(m2.lowest_ask)
                             FROM market_data m2
                             WHERE m2.product_key = pl.product_key
                               AND m2.lowest_ask IS NOT NULL
                           )
                         ) AS stockx_price
                  FROM product_lookup pl
                ),
                kk AS (
                  SELECT product_key, AVG(lowest_ask) AS kicks_price
                  FROM kicks_prices
                  WHERE lowest_ask IS NOT NULL
                  GROUP BY product_key
                )
                SELECT p.name,
                       sx.stockx_price AS stockx_price,
                       kk.kicks_price AS kicks_price
                FROM sx
                JOIN kk USING (product_key)
                JOIN product_lookup pl USING (product_key)
                JOIN products p ON p.product_id = pl.product_id
                WHERE sx.stockx_price IS NOT NULL
                  AND kk.kicks_price IS NOT NULL
                ORDER BY p.name
                LIMIT 20
                """
            )
            metrics["stockx_vs_kicks_samples"] = [
                {"name": name, "size": None, "stockx_ask": sx, "kicks_ask": kk}
                for (name, sx, kk) in cur.fetchall()
            ]

    except sqlite3.Error as e:
        print("database error:", e)

    return metrics


def write_metrics_to_file(metrics: dict, filename: str = "metrics_summary.json"):
    """
    write the calculated metrics to a json file.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=4)
    except IOError as e:
        print("file write error:", e)


def create_graphs(metrics: dict):
    """
    visualizations:
    1) bar chart: size vs average stockx lowest ask
    2) bar chart: size vs average kicks lowest ask
    3) grouped bar chart: stockx vs kicks for joined samples
    """

    # 1. stockx size vs average lowest ask
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
        print("no stockx price-by-size data available.")

    # 2. kicks size vs average lowest ask
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
        print("no kicks price-by-size data available.")

    # 3. grouped bars: stockx vs kicks for joined samples
    samples = metrics.get("stockx_vs_kicks_samples", [])
    if samples:
        def label_for(s):
            return s['name'] if not s.get('size') else f"{s['name']} (sz {s['size']})"
        labels = [label_for(s) for s in samples]
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
        print("no joined stockx vs kicks samples available to plot.")


def main():
    metrics = create_metrics()
    write_metrics_to_file(metrics, "metrics_summary.json")
    create_graphs(metrics)


if __name__ == "__main__":
    main()
