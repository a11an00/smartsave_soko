import asyncio
import re
from playwright.async_api import async_playwright
from selectolax.parser import HTMLParser
from database import SessionLocal
from pipeline import ingest_scraped_product

# Aligned to your database relation index for Quickmart
supermarket_id = 2  

QUICKMART_SUBCATEGORIES = [
    "fats-oils",
    "food-cupboard"
]

async def scrape_quickmart():
    async with async_playwright() as p:
        print("[Scraper] Launching browser engine for Quickmart...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        
        for subcat in QUICKMART_SUBCATEGORIES:
            url = f"https://www.quickmart.co.ke/{subcat}"
            print(f"\n🚀 [Processing Subcategory] Quickmart -> {subcat.upper()}")
            print(f"[Quickmart] Requesting: {url}")
            
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)
                
                # Dynamic page scroll to force lazy-loaded cards to hydrate text values
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
                await page.wait_for_timeout(2000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 1.5);")
                await page.wait_for_timeout(1500)
                
                # --- DOM EVALUATION ENGINE ---
                extracted_items = await page.evaluate("""
                    () => {
                        const items = [];
                        // Target common element markers or structural containers housing product items
                        const cards = document.querySelectorAll('[class*="product-item"], [class*="product-card"], .product-layouts, .grid-item');
                        
                        cards.forEach(card => {
                            const img = card.querySelector('img');
                            const heading = card.querySelector('h1, h2, h3, h4, .title, [class*="title"], [class*="name"]');
                            
                            let title = "";
                            if (heading && heading.innerText.trim()) {
                                title = heading.innerText;
                            } else if (img) {
                                title = img.getAttribute('alt') || img.getAttribute('title') || '';
                            }
                            
                            const textContent = card.innerText || '';
                            if (title.trim() && (textContent.includes('KES') || textContent.includes('Ksh') || /\\d/.test(textContent))) {
                                items.push({ title: title, fullText: textContent });
                            }
                        });
                        return items;
                    }
                """)
                
                print(f"[Quickmart] Retrieved {len(extracted_items)} clean blocks from DOM context.")
                
                db = SessionLocal()
                try:
                    for item in extracted_items:
                        raw_title = item['title'].strip()
                        full_card_text = item['fullText']
                        
                        # Match regex patterns hunting for visible currency strings safely
                        price_match = re.search(r"(?:KES|Ksh|Sh)\s*([\d,]+(?:\.\d{2})?)", full_card_text, re.IGNORECASE)
                        clean_price = None
                        
                        if price_match:
                            price_str = price_match.group(1).replace(",", "")
                            try:
                                clean_price = float(price_str)
                            except ValueError:
                                pass
                                
                        if not clean_price:
                            # Fallback extraction to general numbers if currency node is structurally isolated
                            all_numbers = re.findall(r"\d[\d,]*", full_card_text)
                            for num in all_numbers:
                                num_cleaned = num.replace(",", "")
                                if len(num_cleaned) >= 2:
                                    try:
                                        clean_price = float(num_cleaned)
                                        break
                                    except ValueError:
                                        continue

                        if raw_title and clean_price and clean_price > 5:
                            print(f" -> [Captured] '{raw_title}' - KES {clean_price}")
                            ingest_scraped_product(db, supermarket_id, raw_title, clean_price)
                finally:
                    db.close()
            except Exception as e:
                print(f"[Quickmart Error] Processing interrupted on path route: {e}")
                
        await browser.close()
        print("\n[Quickmart] Engine execution finalized cleanly.")

if __name__ == "__main__":
    asyncio.run(scrape_quickmart())