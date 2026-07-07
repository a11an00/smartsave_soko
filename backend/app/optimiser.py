# app/optimiser.py
#handles the combinatorial optimization of shopping carts across multiple supermarkets
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))#this section allows us to import modules from the parent directory, enabling access to database and schema definitions without needing to install the package globally.

from typing import List
from sqlalchemy.sql import text
from database import SessionLocal
from app.schemas import CartItemRequest

class CartOptimiser:
    def __init__(self, items: List[CartItemRequest]):
        self.items = items
        self.store_mapping = {1: "Naivas", 2: "Carrefour", 3: "Cleanshelf"}

    def compute(self, buffer_kes: float) -> dict:
        single_store_costs = {1: 0.0, 2: 0.0, 3: 0.0}
        split_itinerary = []
        optimized_split_cost = 0.0
        
        db = SessionLocal()
        try:
            for item in self.items:
                # Direct lookup query pulling real cross-supermarket prices from your scraped dataset
                # Note: Adjust your table and column names below to align with your database models
                query = text("""
                    SELECT supermarket_id, name, price 
                    FROM products 
                    WHERE normalized_item_id = :item_id
                """)
                rows = db.execute(query, {"item_id": item.normalized_item_id}).fetchall()
                
                if not rows:
                    continue
                
                item_name = rows[0][1]
                store_prices = {row[0]: float(row[2]) for row in rows}
                
                # 1. Update single store totals (apply penalty for out-of-stock items)
                for sid in single_store_costs.keys():
                    price = store_prices.get(sid)
                    if price is not None:
                        single_store_costs[sid] += price * item.quantity
                    else:
                        single_store_costs[sid] += 99999.0  # Massive penalty if item is out of stock
                
                # 2. Identify absolute lowest price cross-shopping node
                best_store_id = min(store_prices, key=store_prices.get)
                cheapest_price = store_prices[best_store_id]
                extended_cost = cheapest_price * item.quantity
                
                optimized_split_cost += extended_cost
                split_itinerary.append({
                    "item_id": item.normalized_item_id,
                    "name": item_name,
                    "quantity": item.quantity,
                    "purchased_from": self.store_mapping.get(best_store_id, "Unknown"),
                    "unit_price": cheapest_price,
                    "total": extended_cost
                })
                
            # 3. Choose the absolute best single-store option for cost evaluation
            best_single_store_id = min(single_store_costs, key=single_store_costs.get)
            best_single_cost = single_store_costs[best_single_store_id]
            
            # If any store cost hits our penalty cap, it means no single store has everything
            has_complete_single_store = best_single_cost < 99999.0
            
            gross_savings = best_single_cost - optimized_split_cost if has_complete_single_store else 0.0
            
            # Decision Arbitrage Logic (Module 5, Task 3)
            should_split = gross_savings > buffer_kes if has_complete_single_store else True
            
            return {
                "recommendation": "SPLIT_SHOPPING_ORDER" if should_split else "SINGLE_STORE_ORDER",
                "metrics": {
                    "best_single_store": self.store_mapping.get(best_single_store_id) if has_complete_single_store else "None (Incomplete Stock)",
                    "single_store_total_kes": best_single_cost if has_complete_single_store else None,
                    "optimized_split_total_kes": optimized_split_cost,
                    "calculated_savings_kes": gross_savings,
                    "passes_threshold_hurdle": should_split
                },
                "split_itinerary": split_itinerary
            }
            
        finally:
            db.close()