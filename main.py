"""
Entry point to run the full pipeline:
1) Populate/refresh data via api_functions (StockX + Kicks).
2) Compute metrics and create plots via analysis_and_plots.
"""

from api_functions import create_tables
import api_functions as api
import analysis_and_plots as analysis


def run_pipeline():
	# Ensure tables exist
	create_tables()

	# Populate products (≥100 via multiple queries)
	search_terms = ["jordan 4", "yeezy 350", "dunk low", "air force 1"]
	total = 0
	for term in search_terms:
		products = api.get_api_products(term)
		for p in products:
			api.insert_api_data(p)
			total += 1

	print(f"Inserted/updated product rows: {total}")

	# Fetch a small subset of market data per run (demo and rate-friendly)
	import sqlite3
	conn = sqlite3.connect(api.DB_NAME)
	cur = conn.cursor()
	cur.execute("SELECT product_id, name, style_id FROM products WHERE style_id IS NOT NULL LIMIT 5")
	sample_products = cur.fetchall()
	conn.close()

	print("\nFetching StockX market + Kicks prices for samples:")
	for pid, name, style_id in sample_products:
		# Product-level market data and a few variants
		market = api.get_market_data(pid)
		if isinstance(market, list):
			for variant_data in market[:3]:
				std = variant_data.get("standardMarketData", {})
				var_id = variant_data.get("variantId")
				lowest = std.get("lowestAsk")
				highest_bid = std.get("highestBidAmount")
				sell_faster = std.get("sellFaster")
				if lowest is not None:
					api.insert_market_data(pid, str(var_id)[:8], lowest, highest_bid, sell_faster)
		elif market:
			std = market.get("standardMarketData", market)
			lowest = std.get("lowestAsk")
			highest_bid = std.get("highestBidAmount")
			sell_faster = std.get("sellFaster")
			if lowest is not None or highest_bid is not None:
				api.insert_market_data(pid, "ALL", lowest, highest_bid, sell_faster)
			variants = api.get_variants(pid)
			for v in variants[:3]:
				var_id = v.get("id")
				size = v.get("sizeChart", {}).get("displayOptions", [{}])[0].get("size", "N/A")
				var_market = api.get_variant_market_data(pid, var_id)
				if var_market:
					std = var_market.get("standardMarketData", var_market)
					api.insert_market_data(pid, size, std.get("lowestAsk"), std.get("highestBidAmount"), std.get("sellFaster"))

		# Kicks: snapshot + detailed prices (limit per run)
		hist = api.get_historical_data(name)
		if hist:
			api.insert_kicks_history_for_style(style_id, hist)
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

	# Metrics + plots
	print("\nBuilding metrics and plots...")
	metrics = analysis.create_metrics(api.DB_NAME)
	analysis.write_metrics_to_file(metrics, "metrics_summary.json")
	analysis.create_graphs(metrics)


if __name__ == "__main__":
	run_pipeline()
