import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy.sql import text
from database import SessionLocal

class CartOptimiser:
    def __init__(self, cart_items: list):
        self.cart_items = cart_items
        self.OUT_OF_STOCK_PENALTY = 999999.0

    def compute(self, threshold_buffer_kes: float = 150.0) -> dict:
        db = SessionLocal()
        
        try:
            supermarket_rows = db.execute(text("SELECT supermarket_id, name FROM supermarkets")).fetchall()
            supermarkets = {row[0]: row[1] for row in supermarket_rows}
            
            single_store_costs = {sm_id: 0.0 for sm_id in supermarkets.keys()}
            single_store_breakdowns = {sm_id: [] for sm_id in supermarkets.keys()}
            
            split_itinerary = []
            optimized_split_total = 0.0
            
            for item in self.cart_items:
                p_id = item.get("product_id")
                qty = item.get("quantity", 1)
                
                # FIXED: Swapped out 'p.name / p.product_name' for 'p.unified_name'
                query = text("""
                    SELECT 
                        s.supermarket_id,
                        p.unified_name,
                        MIN(pp.price) AS lowest_branch_price
                    FROM product_prices pp
                    JOIN branches b ON pp.branch_id = b.branch_id
                    JOIN supermarkets s ON b.supermarket_id = s.supermarket_id
                    JOIN products p ON pp.product_id = p.product_id
                    WHERE pp.product_id = :p_id
                    GROUP BY s.supermarket_id, p.unified_name
                """)
                price_rows = db.execute(query, {"p_id": p_id}).fetchall()
                
                if not price_rows:
                    continue
                
                product_name = price_rows[0][1]
                store_prices = {row[0]: float(row[2]) for row in price_rows}
                
                for sm_id in supermarkets.keys():
                    price = store_prices.get(sm_id)
                    if price is not None:
                        item_cost = price * qty
                        single_store_costs[sm_id] += item_cost
                        single_store_breakdowns[sm_id].append({
                            "product_id": p_id,
                            "name": product_name,
                            "quantity": qty,
                            "unit_price": price,
                            "total_cost": item_cost,
                            "status": "Available"
                        })
                    else:
                        single_store_costs[sm_id] += self.OUT_OF_STOCK_PENALTY
                        single_store_breakdowns[sm_id].append({
                            "product_id": p_id,
                            "name": product_name,
                            "quantity": qty,
                            "unit_price": None,
                            "total_cost": None,
                            "status": "OUT_OF_STOCK"
                        })
                
                if store_prices:
                    best_sm_id = min(store_prices, key=store_prices.get)
                    best_price = store_prices[best_sm_id]
                    split_item_cost = best_price * qty
                    
                    optimized_split_total += split_item_cost
                    split_itinerary.append({
                        "product_id": p_id,
                        "name": product_name,
                        "quantity": qty,
                        "cheapest_store": supermarkets[best_sm_id],
                        "unit_price": best_price,
                        "total_cost": split_item_cost
                    })
            
            valid_single_stores = {
                sm_id: cost for sm_id, cost in single_store_costs.items() 
                if cost < self.OUT_OF_STOCK_PENALTY
            }
            
            if valid_single_stores:
                best_single_sm_id = min(valid_single_stores, key=valid_single_stores.get)
                best_single_cost = valid_single_stores[best_single_sm_id]
                best_single_name = supermarkets[best_single_sm_id]
                gross_savings = best_single_cost - optimized_split_total
                recommendation = "SPLIT_SHOPPING_ORDER" if gross_savings > threshold_buffer_kes else "SINGLE_STORE_ORDER"
            else:
                best_single_name = "None (Incomplete Stock Globally)"
                best_single_cost = None
                gross_savings = 0.0
                recommendation = "SPLIT_SHOPPING_ORDER"

            formatted_single_stores = {}
            for sm_id, name in supermarkets.items():
                cost = single_store_costs[sm_id]
                formatted_single_stores[name] = {
                    "total_basket_cost": cost if cost < self.OUT_OF_STOCK_PENALTY else "Incomplete Basket",
                    "items": single_store_breakdowns[sm_id]
                }

            return {
                "recommendation": recommendation,
                "arbitrage_metrics": {
                    "recommended_single_store": best_single_name,
                    "single_store_total_kes": best_single_cost,
                    "optimized_split_total_kes": optimized_split_total,
                    "potential_savings_kes": gross_savings,
                    "applied_threshold_buffer_kes": threshold_buffer_kes
                },
                "optimized_split_itinerary": split_itinerary,
                "single_store_alternatives": formatted_single_stores
            }
            
        finally:
            db.close()