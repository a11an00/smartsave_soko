import asyncio
import re
from playwright.async_api import async_playwright
from database import SessionLocal
from pipeline import ingest_scraped_product

supermarket_id = 1 

NAIVAS_SUBCATEGORIES = [
    "spirits",
    "beers",
    "fats-oils",
    "snacks",
    "breakfast",
    "cold-beverage",
    "hot-beverage",
    "televisions",
    "dairy",
    "beverage-deals",
    "breakfast",
    "dairy/fresh-milk",
    "commodities/flour",
    "commodities/rice-cereals",
    "commodities/sugar-sweeteners",
    "food-cupboard/crisps",

]


#        SCRAPER CONFIGURATION

MAX_SCROLL_ATTEMPTS = 5  # Adjust this to cap how deep you scroll

async def handle_naivas_popups(page, max_wait_time_ms=5000):
    """
    Actively intercepts and dismisses the specific age gates, cookie cards, 
    and overlays visible in Screenshot 2026-07-02 180710.jpg.
    """
    try:
        start_time = asyncio.get_event_loop().time()
        blockers = [
            # 1. Age Verification Targets (From screenshot)
            "button:has-text(\"Yes, I'm 18!\")",
            "button:has-text('Yes')",
            
            # 2. Cookie Banner Targets (From screenshot)
            "button:has-text('OK!')",
            "button:has-text('OK')",
            
            # 3. Structural/Fallback Close Elements
            "button:has-text('Close')", 
            "button:has-text('Confirm')",
            "button:has-text('Select')", 
            "[aria-label='Close']",
            ".close-menu"
        ]
        
        while (asyncio.get_event_loop().time() - start_time) * 1000 < max_wait_time_ms:
            popup_found = False
            for selector in blockers:
                try:
                    locator = page.locator(selector).first
                    if await locator.is_visible():
                        print(f"   [Naivas Shield] Automatically dismissing blocker: {selector}")
                        await locator.click(timeout=2000)
                        await page.wait_for_timeout(1000)
                        popup_found = True
                        break  
                except Exception:
                    continue
            
            if not popup_found:
                await page.wait_for_timeout(500)
                break
    except Exception as e:
        print(f"   [Naivas Warning] Popup handling exception: {e}")

async def handle_naivas_location(page):
    """Hits Naivas root first to establish session context and clear baseline overlays."""
    try:
        print("[Naivas] Initializing base session on homepage...")
        await page.goto("https://www.naivas.online/", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await handle_naivas_popups(page, max_wait_time_ms=6000)
        print("[Naivas] Base cookies and session tokens initialized.")
    except Exception as e:
        print(f"[Naivas Warning] Base initialization step had an issue: {e}")

async def scrape_naivas():
    async with async_playwright() as p:
        print("[Scraper] Launching browser engine for Naivas...")
        browser = await p.chromium.launch(headless=False)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            permissions=["geolocation"],
            geolocation={"latitude": -0.3031, "longitude": 36.0613} # Nakuru County coordinates
        )
        page = await context.new_page()
        
        # Step 1: Initialize cookies and handle baseline elements
        await handle_naivas_location(page)
        
        # Step 2: Crawl subcategories
        for subcat in NAIVAS_SUBCATEGORIES:
            url = f"https://www.naivas.online/{subcat}"
            print(f"\n [Processing Subcategory] Naivas -> {subcat.upper()}")
            print(f"[Naivas] Requesting: {url}")
            
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                
                # RUN SWEEP IMMEDIATELY AFTER NAVIGATION (Squashes age gates instantly)
                await handle_naivas_popups(page, max_wait_time_ms=5000)
                
                print("[Naivas] Waiting for lazy content to append to layout tree...")
                try:
                    await page.wait_for_selector(".product-card-img img", timeout=10000)
                except Exception:
                    print("[Naivas Warning] Target selector wait expired. Proceeding with scroll routine.")
                
                # --- INFINITE SCROLL INTEGRATION WITH MAX CODES ---
                print(f"[Naivas] Initiating infinite scroll loop (Limit set to max {MAX_SCROLL_ATTEMPTS} attempts)...")
                last_height = await page.evaluate("document.body.scrollHeight")
                scroll_attempts = 0
                
                while scroll_attempts < MAX_SCROLL_ATTEMPTS:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    await page.wait_for_timeout(2500)
                    
                    # Run a sweep during scroll in case delayed overlays drop down
                    await handle_naivas_popups(page, max_wait_time_ms=1000)
                    
                    new_height = await page.evaluate("document.body.scrollHeight")
                    if new_height == last_height:
                        # Perform a brief partial upward/downward nudge to trigger finicky event listeners
                        await page.evaluate("window.scrollBy(0, -300);")
                        await page.wait_for_timeout(500)
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                        await page.wait_for_timeout(1500)
                        
                        new_height = await page.evaluate("document.body.scrollHeight")
                        if new_height == last_height:
                            print(f"[Naivas] Infinite scroll hit bottom layout limits naturally at {scroll_attempts} steps.")
                            break
                    
                    last_height = new_height
                    scroll_attempts += 1
                    print(f"   -> Extended page down [{scroll_attempts}/{MAX_SCROLL_ATTEMPTS}] times...")
                
                if scroll_attempts >= MAX_SCROLL_ATTEMPTS:
                    print(f"[Naivas] Hit maximum configured limit of {MAX_SCROLL_ATTEMPTS} scroll sweeps. Processing available DOM elements.")

                # Final cleaning sweeps before extracting text
                await handle_naivas_popups(page, max_wait_time_ms=2000)

                # --- ACCURATE DOM ANCESTOR EXTRACTION ---
                extracted_items = await page.evaluate("""
                    () => {
                        const items = [];
                        const wrappers = document.querySelectorAll('.product-card-img');
                        
                        wrappers.forEach(wrapper => {
                            const img = wrapper.querySelector('img');
                            if (!img) return;
                            const title = img.getAttribute('alt') || '';
                            if (!title) return;
                            
                            let cardElement = wrapper.parentElement;
                            while (cardElement && !cardElement.innerText.includes('KES')) {
                                if (cardElement.parentElement) {
                                    cardElement = cardElement.parentElement;
                                } else {
                                    break;
                                }
                            }
                            
                            const textContent = cardElement ? (cardElement.innerText || '') : '';
                            items.push({ title: title, fullText: textContent });
                        });
                        return items;
                    }
                """)
                
                print(f"[Naivas] Retrieved {len(extracted_items)} items from the expanded DOM structure.")
                
                db = SessionLocal()
                try:
                    captured_count = 0
                    for item in extracted_items:
                        raw_title = item['title'].strip()
                        full_card_text = item['fullText']
                        
                        clean_price = None
                        price_match = re.search(r"KES\s*([\d,]+(?:\.\d{2})?)", full_card_text, re.IGNORECASE)
                        
                        if price_match:
                            price_str = price_match.group(1).replace(",", "")
                            try:
                                clean_price = float(price_str)
                            except ValueError:
                                pass
                                
                        if raw_title and clean_price:
                            print(f" -> [Captured] '{raw_title}' - KES {clean_price}")
                            ingest_scraped_product(db, supermarket_id, raw_title, clean_price)
                            captured_count += 1
                    
                    print(f"[Naivas] Successfully ingested {captured_count} products for {subcat.upper()}.")
                finally:
                    db.close()
                    
            except Exception as e:
                print(f"[Naivas Error] Failed sequence processing on path route: {e}")
                
        await browser.close()
        print("\n[Naivas] Engine run sequence fully closed.")

if __name__ == "__main__":
    asyncio.run(scrape_naivas())