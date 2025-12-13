# name: dezmond blair
# student id: 7083 2724
# email: dezb@umich.edu

import sqlite3
import api_functions as api
import analysis_and_plots as analysis


def run_pipeline():
    """populate database and generate metrics/plots.
    
    rubric compliance: stores ≤25 items per run.
    run this script 4+ times to reach ≥100 total items.
    """
    api.create_tables()
    
    # fetch ≤25 products per run (rubric requirement)
    # rotate through search terms across runs
    search_terms = ["jordan 4", "yeezy 350", "dunk low", "air force 1"]
    
    # determine which term to use this run based on current product count
    conn = sqlite3.connect(api.DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products")
    current_count = cur.fetchone()[0]
    conn.close()
    
    term_index = (current_count // 25) % len(search_terms)
    term = search_terms[term_index]
    
    products = api.get_api_products(term)
    total = 0
    for p in products[:25]:  # enforce 25-item limit
        api.insert_api_data(p)
        total += 1
    
    print(f"Run #{(current_count // 25) + 1}: Inserted {total} products for '{term}'")
    print(f"Total products in DB: {current_count + total}")
    
    # fetch market data for sample products
    conn = sqlite3.connect(api.DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT product_id, name, style_id FROM products WHERE style_id IS NOT NULL LIMIT 5")
    samples = cur.fetchall()
    conn.close()
    
    print("Fetching market data for samples...")
    for pid, name, style_id in samples:
        # stockx market data
        market = api.get_market_data(pid)
        if market:
            if isinstance(market, list):
                # list of variants with embedded market data
                for variant_data in market[:5]:  # Limit to 5 variants
                    std = variant_data.get("standardMarketData", {})
                    var_id = variant_data.get("variantId")
                    lowest = std.get("lowestAsk")
                    highest_bid = std.get("highestBidAmount")
                    sell_faster = std.get("sellFaster")
                    # get size from variants endpoint
                    if var_id:
                        variants = api.get_variants(pid)
                        for v in variants:
                            if v.get("id") == var_id:
                                size = v.get("sizeChart", {}).get("displayOptions", [{}])[0].get("size", "N/A")
                                if lowest is not None:
                                    api.insert_market_data(pid, size, lowest, highest_bid, sell_faster)
                                break
            else:
                # dict format
                std = market.get("standardMarketData", market)
                lowest = std.get("lowestAsk")
                highest_bid = std.get("highestBidAmount")
                sell_faster = std.get("sellFaster")
                if lowest is not None or highest_bid is not None:
                    api.insert_market_data(pid, "ALL", lowest, highest_bid, sell_faster)
        
        # kicks data
        hist = api.get_historical_data(name)
        if hist:
            api.insert_kicks_us_market_for_style(style_id, {
                "historical_average": hist.get("historical_average"),
                "last_sale": hist.get("last_sale"),
                "sales_last_72h": hist.get("sales_last_72h"),
                "sell_faster": hist.get("sell_faster"),
                "earn_more": hist.get("earn_more"),
            })
        
        resolved = api.get_kicks_product_id_or_slug(name)
        if resolved:
            id_or_slug = resolved.get("slug") or resolved.get("id")
            detail = api.get_kicks_product_detail(id_or_slug, include_variants=True, include_prices=True)
            if detail:
                api.insert_kicks_prices_for_style(style_id, detail)
    
    # populate integer keys and compute metrics
    api.ensure_product_keys()
    
    print("Computing metrics and creating visualizations...")
    metrics = analysis.create_metrics(api.DB_NAME)
    analysis.write_metrics_to_file(metrics, "metrics_summary.json")
    analysis.create_graphs(metrics)


if __name__ == "__main__":
    run_pipeline()
