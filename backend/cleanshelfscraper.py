import asyncio
import re
from playwright.async_api import async_playwright
from selectolax.parser import HTMLParser
from database import SessionLocal
from pipeline import ingest_scraped_product

# Aligned to your database relation index for Cleanshelf
supermarket_id = 3  

CLEANSHELF_SUBCATEGORIES = [
    "fats-oils",
    "food-cupboard"
]

async def scrape_cleanshelf():
    async with async_playwright() as p:
        print("[Scraper] Launching browser engine for Cleanshelf...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        
        for subcat in CLEANSHELF_SUBCATEGORIES:
            url = f"https://cleanshelf.co.ke/{subcat}"
            print(f"\n [Processing Subcategory] Cleanshelf -> {subcat.upper()}")
            print(f"[Cleanshelf] Requesting: {url}")
            
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)
                
                # Scroll sequence to force lazy element parsing boundaries
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
                await page.wait_for_timeout(1500)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 1.5);")
                await page.wait_for_timeout(1500)
                
                # --- DOM EVALUATION ENGINE ---
                extracted_items = await page.evaluate("""
                    () => {
                        const items = [];
                        // Broaden query lookup target criteria to encompass typical grid layout wrappers
                        const cards = document.querySelectorAll('[class*="product-item"], [class*="product-card"], .product-box, .grid-product');
                        
                        if (cards.length > 0) {
                            cards.forEach(card => {
                                const img = card.querySelector('img');
                                const heading = card.querySelector('h1, h2, h3, h4, .title, [class*="title"], [class*="name"]');
                                
                                let title = "";
                                if (heading && heading.innerText.trim()) title = heading.innerText;
                                else if (img) title = img.getAttribute('alt') || img.getAttribute('title') || '';
                                
                                const textContent = card.innerText || '';
                                if (title.trim()) {
                                    items.push({ title: title, fullText: textContent });
                                }
                            });
                        } else {
                            // Secondary fallback if layouts compress straight into semantic images
                            const images = document.querySelectorAll('img');
                            images.forEach(img => {
                                const altText = img.getAttribute('alt') || img.getAttribute('title') || '';
                                if (!altText || altText.length < 4) return;
                                
                                let parentBox = img.parentElement;
                                let textContent = "";
                                
                                for (let i = 0; i < 5; i++) {
                                    if (parentBox) {
                                        if (parentBox.innerText && (parentBox.innerText.includes('KES') || parentBox.innerText.includes('Ksh') || /\\d/.test(parentBox.innerText))) {
                                            textContent = parentBox.innerText;
                                            break;
                                        }
                                        parentBox = parentBox.parentElement;
                                    }
                                }
                                items.push({ title: altText, fullText: textContent });
                            });
                        }
                        return items;
                    }
                """)
                
                print(f"[Cleanshelf] Retrieved {len(extracted_items)} semantic blocks from browser context.")
                
                db = SessionLocal()
                try:
                    for item in extracted_items:
                        raw_title = item['title'].strip()
                        full_card_text = item['fullText']
                        
                        # Isolate pricing sequences matching common localized denomination headers
                        price_match = re.search(r"(?:KES|Ksh|Sh)\s*([\d,]+(?:\.\d{2})?)", full_card_text, re.IGNORECASE)
                        clean_price = None
                        
                        if price_match:
                            price_str = price_match.group(1).replace(",", "")
                            try:
                                clean_price = float(price_str)
                            except ValueError:
                                pass
                                
                        if not clean_price:
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
                print(f"[Cleanshelf Error] Execution broke down on branch route: {e}")
                
        await browser.close()
        print("\n[Cleanshelf] Engine run execution completed.")

if __name__ == "__main__":
    asyncio.run(scrape_cleanshelf())