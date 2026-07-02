from sqlalchemy import text
from sqlalchemy.orm import Session
from rapidfuzz import process, fuzz
import cleaner

def ingest_scraped_product(db: Session, supermarket_id: int, raw_title: str, scrape_price: float):
    # Parse the raw title to extract size and unit information
    size_val, size_unit, clean_title = cleaner.parse_volume_and_unit(raw_title)
    
    #  Checks if a matching product sizing profile already exists
    existing_products = db.execute(
        text("SELECT product_id, unified_name FROM products WHERE size_value = :val AND size_unit = :unit"),
        {"val": size_val, "unit": size_unit}
    ).fetchall()
    
    matched_product_id = None
    
    if existing_products:
        product_pool = {p[1]: p[0] for p in existing_products} 
        best_match = process.extractOne(clean_title, product_pool.keys(), scorer=fuzz.token_sort_ratio)
        
        if best_match and best_match[1] >= 85:
            matched_product_id = product_pool[best_match[0]]
            print(f"-> Fuzzy Match Linked: '{raw_title}' to existing Product ID: {matched_product_id}")

    # If it's a completely new addition, append it to the database and retrieve the newly generated product_id
    if not matched_product_id:
        insert_prod = db.execute(
            text("INSERT INTO products (unified_name, size_value, size_unit) VALUES (:name, :val, :unit)"),
            {"name": clean_title, "val": size_val, "unit": size_unit}
        )
        db.commit()
        matched_product_id = insert_prod.lastrowid
        print(f"-> Created Catalog Row: {clean_title} ({size_val}{size_unit})")

    #Grab ALL branches belonging to this supermarket chain and broadcast the price to each of them, ensuring uniformity across the chain
    branches = db.execute(
        text("SELECT branch_id FROM branches WHERE supermarket_id = :s_id"),
        {"s_id": supermarket_id}
    ).fetchall()
    
    if not branches:
        print(f"[Warning] Zero physical branches registered in database for Supermarket ID {supermarket_id}")
        return

    # 5. Loop through every branch and seed the price uniformly
    for row in branches:
        branch_id = row[0]
        db.execute(
            text("""
                INSERT INTO product_prices (branch_id, product_id, price) 
                VALUES (:b_id, :p_id, :price)
                ON DUPLICATE KEY UPDATE price = :price, last_updated = CURRENT_TIMESTAMP
            """),
            {"b_id": branch_id, "p_id": matched_product_id, "price": scrape_price}
        )
    
    db.commit()
    print(f"-> Successfully broadcasted KES {scrape_price} across {len(branches)} local branches.")