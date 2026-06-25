from database import SessionLocal
from pipeline import ingest_scraped_product

db = SessionLocal()

try:
    print("--- Testing Naivas Ingestion ---")
    # Simulates pulling 1 item from Naivas Central catalog. 
    # It will find BOTH Naivas Westside and Naivas Downtown branches and give them this price.
    ingest_scraped_product(db, supermarket_id=1, raw_title="Kabras Sugar 2Kg", scrape_price=310.00)
    
    print("\n--- Testing Quickmart Ingestion ---")
    # Simulates pulling the same item from Quickmart Central catalog.
    # It will find BOTH Quickmart Shabab and Quickmart 58 branches and update them.
    ingest_scraped_product(db, supermarket_id=2, raw_title="KABRAS SUGAR Premium 2 kg", scrape_price=295.00)

finally:
    db.close()
    