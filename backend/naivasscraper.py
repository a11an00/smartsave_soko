import asyncio
import re
from playwright.async_api import async_playwright
from selectolax.parser import HTMLParser
from database import SessionLocal
from pipeline import ingest_scraped_product

# Aligned to your database schema lowercase naming convention
supermarket_id = 1 

# Target subcategory slugs layout direct product streams on Naivas Online
NAIVAS_SUBCATEGORIES = [

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

async def handle_naivas_location(page):
    """Hits Naivas root first to establish session context and clear location modals."""
    try:
        print("[Naivas] Initializing base session on homepage...")
        await page.goto("https://www.naivas.online/", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)
        
        blockers = [
            "button:has-text('Close')", 
            "button:has-text('Confirm')",
            "button:has-text('Select')", 
            "text=Select Address",
            "[aria-label='Close']",
            ".close-menu"
        ]
        
        for selector in blockers:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible():
                    print(f"[Naivas] Dismissing setup barrier via: {selector}")
                    await locator.click()
                    await page.wait_for_timeout(1500)
            except Exception:
                continue
        print("[Naivas] Base cookies and session tokens initialized.")
    except Exception as e:
        print(f"[Naivas Warning] Base initialization step had an issue: {e}")

async def scrape_naivas():
    async with async_playwright() as p:
        print("[Scraper] Launching browser engine for Naivas...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        
        # Step 1: Initialize cookies and bypass location walls at root level
        await handle_naivas_location(page)
        
        # Step 2: Crawl subcategories within the initialized session context
        for subcat in NAIVAS_SUBCATEGORIES:
            url = f"https://www.naivas.online/{subcat}"
            print(f"\n [Processing Subcategory] Naivas -> {subcat.upper()}")
            print(f"[Naivas] Requesting: {url}")
            
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                print("[Naivas] Waiting for lazy content to append to layout tree...")
                try:
                    await page.wait_for_selector(".product-card-img img", timeout=15000)
                except Exception:
                    print("[Naivas Warning] Target selector wait expired. Proceeding with snapshot capture.")
                
                # Secondary modal cleanup if popups trigger on context routing shifts
                for selector in ["button:has-text('Close')", "[aria-label='Close']"]:
                    try:
                        if await page.locator(selector).first.is_visible():
                            await page.locator(selector).first.click()
                    except Exception:
                        continue

                # Trigger dynamic page scroll sequences to force lazy components to evaluate
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
                await page.wait_for_timeout(2000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 1.5);")
                await page.wait_for_timeout(1500)
                
                # --- ACCURATE DOM ANCESTOR EXTRACTION ---
                # fetch the parent flex/grid layout card container matching all item details 
                extracted_items = await page.evaluate("""
                    () => {
                        const items = [];
                        const wrappers = document.querySelectorAll('.product-card-img');
                        
                        wrappers.forEach(wrapper => {
                            const img = wrapper.querySelector('img');
                            if (!img) return;
                            const title = img.getAttribute('alt') || '';
                            if (!title) return;
                            
                            // ANCESTOR TARGET FIX:
                            // Walk backwards up until we hit the complete card bounding cell containing everything
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
                
                print(f"[Naivas] Retrieved {len(extracted_items)} complete string blocks from browser.")
                
                db = SessionLocal()
                try:
                    for item in extracted_items:
                        raw_title = item['title'].strip()
                        full_card_text = item['fullText']
                        
                        clean_price = None
                        
                        # Match regex patterns specifically hunting for your visible KES string label format
                        price_match = re.search(r"KES\s*([\d,]+(?:\.\d{2})?)", full_card_text, re.IGNORECASE)
                        
                        if price_match:
                            price_str = price_match.group(1).replace(",", "")
                            try:
                                clean_price = float(price_str)
                            except ValueError:
                                pass
                                
                        # Execute logging stream verification and pipeline ingest distribution
                        if raw_title and clean_price:
                            print(f" -> [Captured] '{raw_title}' - KES {clean_price}")
                            ingest_scraped_product(db, supermarket_id, raw_title, clean_price)
                        else:
                            print(f" [Skipped Debug] Title: '{raw_title}' | Raw Found Text Context: {full_card_text.replace(chr(10), ' ')}")
                            
                finally:
                    db.close()
            except Exception as e:
                print(f"[Naivas Error] Failed sequence processing on path route: {e}")
                
        await browser.close()
        print("\n[Naivas] Engine run sequence fully closed.")

if __name__ == "__main__":
    asyncio.run(scrape_naivas())