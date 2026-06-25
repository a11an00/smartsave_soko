import asyncio
import re
from playwright.async_api import async_playwright
from database import SessionLocal
from pipeline import ingest_scraped_product

# Aligned to your database relation index for Quickmart
supermarket_id = 2  

QUICKMART_SUBCATEGORIES = [
    "home",  
    "flour",
    "beverages",
    "juices-carbonates",
    "cooking-oils-fats",
    "sugar",
    "rice-cereals",
    "dairy-products",
    "cakes-bread",
    "tv",
]

async def scrape_quickmart():
    async with async_playwright() as p:
        print("[Scraper] Launching browser engine for Quickmart...")
        browser = await p.chromium.launch(headless=False)
        
        # Pre-grant geolocation permissions natively
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            permissions=["geolocation"], 
            geolocation={"latitude": -1.2921, "longitude": 36.8219}
        )
        page = await context.new_page()
        

        #  INITIALIZE HOME PAGE & BYPASS LANDING MODALS
        
        print("\n[Quickmart] Initializing on Home Page to handle location setup...")
        try:
            await page.goto("https://www.quickmart.co.ke/", timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
            
            # Handle Cookie/Privacy Banner
            try:
                cookie_btn = page.locator(
                    'button:has-text("Accept All"), button:has-text("Accept Cookies"), button:has-text("Allow All"), #onetrust-accept-btn-handler'
                ).first
                if await cookie_btn.is_visible(timeout=2000):
                    print("[Quickmart] Cookie banner cleared.")
                    await cookie_btn.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

            # Click "Use My Current Location" (Step 1 of Location Modal)
            try:
                location_btn = page.locator(
                    'button:has-text("Use My Current Location"), a:has-text("Use My Current Location"), div:has-text("Use My Current Location")'
                ).last
                if await location_btn.is_visible(timeout=4000):
                    print("[Quickmart] Clicking 'Use My Current Location'...")
                    await location_btn.click()
                    await page.wait_for_timeout(3000)
            except Exception:
                pass

            #  Click "Continue" (Step 2 of Location Modal confirming branch)
            try:
                continue_btn = page.locator(
                    'button:has-text("Continue"), a:has-text("Continue"), .modal-body button:has-text("Continue")'
                ).first
                if await continue_btn.is_visible(timeout=4000):
                    print("[Quickmart] Branch confirmed via 'Continue'.")
                    await continue_btn.click()
                    await page.wait_for_timeout(4000)
            except Exception:
                pass

        except Exception as home_err:
            print(f"[Quickmart Warning] Home page initialization ran into an anomaly: {home_err}")

        
        # STEP 2: LOOP THROUGH TARGETED SUBCATEGORIES
        
        for subcat in QUICKMART_SUBCATEGORIES:
            url = f"https://www.quickmart.co.ke/{subcat}"
            print(f"\n[Processing Subcategory] Quickmart -> {subcat.upper()}")
            print(f"[Quickmart] Requesting: {url}")
            
            try:
                await page.goto(url, timeout=60000, wait_until="networkidle")
                await page.wait_for_timeout(4000)
                
                # Broad dynamic scrolling to trigger hydrations across columns
                for scroll in range(3):
                    await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {scroll + 1} / 4);")
                    await page.wait_for_timeout(1500)
                
                # --- BROAD AGNOSTIC DOM EXTRACTOR ---
                extracted_items = await page.evaluate("""
                    () => {
                        const items = [];
                        
                        // 1. Compile all potential element variations representing individual product containers
                        let cards = Array.from(document.querySelectorAll(
                            '[class*="product-item"], [class*="product-card"], [class*="product-thumb"], .grid-item, [class*="col-"]'
                        ));
                        
                        // Fallback: If classes are highly obfuscated, capture individual text/price layout blocks
                        if (cards.length < 5) {
                            cards = Array.from(document.querySelectorAll('div')).filter(el => {
                                const txt = el.innerText || '';
                                return txt.length < 400 && (txt.includes('KES') || txt.includes('Ksh')) && el.querySelector('img');
                            });
                        }
                        
                        cards.forEach(card => {
                            const img = card.querySelector('img');
                            const heading = card.querySelector('h1, h2, h3, h4, h5, .title, [class*="title"], [class*="name"]');
                            
                            let title = "";
                            if (heading && heading.innerText.trim()) {
                                title = heading.innerText;
                            } else if (img) {
                                title = img.getAttribute('alt') || img.getAttribute('title') || '';
                            }
                            
                            const textContent = card.innerText || '';
                            
                            // Prevent duplicating huge layout shells by restricting character size boundary limits
                            if (title.trim() && textContent.length < 500 && (textContent.includes('KES') || textContent.includes('Ksh') || /\\d/.test(textContent))) {
                                items.push({ title: title, fullText: textContent });
                            }
                        });
                        return items;
                    }
                """)
                
                print(f"[Quickmart] Retrieved {len(extracted_items)} raw text blocks from DOM context.")
                
                # --- DB INGESTION ENGINE ---
                db = SessionLocal()
                captured_count = 0
                try:
                    for item in extracted_items:
                        raw_title = item['title'].strip()
                        full_card_text = item['fullText']
                        
                        # Clean out linebreaks inside structural title properties
                        raw_title = re.sub(r'\s+', ' ', raw_title)
                        
                        # Search for currency variations
                        price_match = re.search(r"(?:KES|Ksh|Sh)\s*([\d,]+(?:\.\d{2})?)", full_card_text, re.IGNORECASE)
                        clean_price = None
                        
                        if price_match:
                            price_str = price_match.group(1).replace(",", "")
                            try:
                                clean_price = float(price_str)
                            except ValueError:
                                pass
                                
                        if not clean_price:
                            # Secondary fallback numbers matcher
                            all_numbers = re.findall(r"\d[\d,]*", full_card_text)
                            for num in all_numbers:
                                num_cleaned = num.replace(",", "")
                                if len(num_cleaned) >= 2:
                                    try:
                                        clean_price = float(num_cleaned)
                                        break
                                    except ValueError:
                                        continue

                        if raw_title and clean_price and 10 < clean_price < 150000:
                            print(f" -> [Captured] '{raw_title}' - KES {clean_price}")
                            ingest_scraped_product(db, supermarket_id, raw_title, clean_price)
                            captured_count += 1
                            
                    print(f"[Quickmart] Ingested {captured_count} products successfully into DB for {subcat.upper()}.")
                finally:
                    db.close()
                    
            except Exception as e:
                print(f"[Quickmart Error] Processing interrupted on path route: {e}")
                
        await browser.close()
        print("\n[Quickmart] Engine execution finalized cleanly.")

if __name__ == "__main__":
    asyncio.run(scrape_quickmart())