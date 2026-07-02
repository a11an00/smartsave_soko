import asyncio
import re
from playwright.async_api import async_playwright
from database import SessionLocal
from pipeline import ingest_scraped_product

# Aligned to your database relation index for Cleanshelf
supermarket_id = 3  

# Verified e-commerce inventory subcategory list for Cleanshelf
CLEANSHELF_SUBCATEGORIES = [
    "dairy-products",
    "butter-2",
    "beverages",
    "breads-spreads",
    "breakfast-cereals-baby-foods",
    "condiments",
    "oils-salt",
    "pastry-fresh-foods",
    "soaps-detergents",
    "snacks-confectionery",
    "soft-drinks",
    "flour-sugar",
    "maize-flour-2",
    "alcoholic-drinks"

]

TOTAL_PAGES_TO_SCRAPE = 3

async def handle_cleanshelf_popups(page, max_wait_time_ms=5000):
    """
    Actively tracks down and neutralizes region selection prompts, location blockers, 
    and newsletter modals by scanning for text hooks in a timed event loop.
    """
    try:
        start_time = asyncio.get_event_loop().time()
        blockers = [
            "button:has-text('Use My Location')",
            "button:has-text('Select Location')",
            "button:has-text('Confirm Location')",
            "button:has-text('Confirm')",
            "button:has-text('Select')", 
            "button:has-text('Close')", 
            "button:has-text('Dismiss')",
            "text=Select Address",
            "[aria-label='Close']",
            ".modal-close",
            ".close",
            ".dismiss-button"
        ]
        
        while (asyncio.get_event_loop().time() - start_time) * 1000 < max_wait_time_ms:
            popup_found = False
            for selector in blockers:
                try:
                    locator = page.locator(selector).first
                    if await locator.is_visible():
                        print(f"   [Cleanshelf Shield] Neutralizing blocker element: {selector}")
                        await locator.click()
                        await page.wait_for_timeout(1000)
                        popup_found = True
                        break  
                except Exception:
                    continue
            
            if not popup_found:
                await page.wait_for_timeout(500)
                break
                
    except Exception as e:
        print(f"   [Cleanshelf Warning] Layout overlay monitor caught an exception: {e}")

async def scrape_cleanshelf():
    async with async_playwright() as p:
        print("[Scraper] Launching browser engine for Cleanshelf...")
        browser = await p.chromium.launch(headless=False)
        
        # Geolocation configuration pointed at Nakuru coordinates
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            permissions=["geolocation"],
            geolocation={"latitude": -0.3031, "longitude": 36.0613}  
        )
        page = await context.new_page()
        
        print("[Cleanshelf] Priming initial baseline session at root shop entry...")
        try:
            await page.goto("https://cleanshelf.online/shop", timeout=45000, wait_until="domcontentloaded")
            await handle_cleanshelf_popups(page, max_wait_time_ms=6000)
        except Exception as e:
            print(f"[Cleanshelf Warning] Base shop route setup bypassed: {e}")
        
        for subcat in CLEANSHELF_SUBCATEGORIES:
            for page_num in range(1, TOTAL_PAGES_TO_SCRAPE + 1):
                
                # Dynamic parameter syntax generation
                if page_num == 1:
                    url = f"https://cleanshelf.online/shop?category_slug={subcat}"
                else:
                    url = f"https://cleanshelf.online/shop?category_slug={subcat}&page={page_num}"
                
                print(f"\n [Processing Stream] Cleanshelf -> {subcat.upper()} | PAGE {page_num}")
                print(f"[Quickmart] Navigating: {url}")
                
                try:
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    await handle_cleanshelf_popups(page, max_wait_time_ms=5000)
                    
                    # Layout hydration scrolling script
                    for i in range(4):
                        await page.evaluate(f"window.scrollTo(0, (document.body.scrollHeight / 4) * {i + 1});")
                        await page.wait_for_timeout(1000)
                    
                    # Secondary scroll safety sweep
                    await handle_cleanshelf_popups(page, max_wait_time_ms=2000)
                    
                    # --- REFINED DYNAMIC HARVESTER ENGINE ---
                    extracted_items = await page.evaluate(f"""
                        () => {{
                            const data = [];
                            const elements = document.querySelectorAll('p, span, div, h3, h4, h5, a');
                            const subcatLower = "{subcat.lower()}";
                            
                            elements.forEach(el => {{
                                const text = el.innerText ? el.innerText.trim() : '';
                                
                                if (text && (text.startsWith('KES') || text.startsWith('Ksh') || /^\\d{{2,4}}(\\.\\d{{2}})?$/.test(text))) {{
                                    
                                    let parent = el.parentElement;
                                    let title = "";
                                    let attempts = 0;
                                    
                                    while (parent && attempts < 5) {{
                                        const targets = parent.querySelectorAll('a, h3, h4, h5, .product-name, div[class*="title"]');
                                        for (let target of targets) {{
                                            const targetText = target.innerText ? target.innerText.trim() : '';
                                            
                                            if (
                                                targetText.length > 4 && 
                                                targetText.toLowerCase() !== subcatLower &&
                                                targetText.toLowerCase() !== "shop" &&
                                                !targetText.startsWith('KES') && 
                                                !targetText.startsWith('Ksh') &&
                                                !/^\\d+$/.test(targetText)
                                            ) {{
                                                title = targetText;
                                                break;
                                            }}
                                        }}
                                        
                                        if (title) break;
                                        parent = parent.parentElement;
                                        attempts++;
                                    }}
                                    
                                    if (!title && el.parentElement) {{
                                        const lines = el.parentElement.innerText.split('\\n');
                                        for (let line of lines) {{
                                            const cleanLine = line.trim();
                                            if (
                                                cleanLine.length > 5 && 
                                                cleanLine.toLowerCase() !== subcatLower && 
                                                cleanLine.toLowerCase() !== "shop" &&
                                                !cleanLine.includes('KES') && 
                                                !cleanLine.includes('Ksh')
                                            ) {{
                                                title = cleanLine;
                                                break;
                                            }}
                                        }}
                                    }}
                                    
                                    if (title && title.length < 90) {{
                                        data.push({{ 
                                            title: title, 
                                            fullText: el.parentElement ? el.parentElement.innerText : text 
                                        }});
                                    }}
                                }}
                            }});
                            
                            return Array.from(new Set(data.map(a => JSON.stringify(a)))).map(e => JSON.parse(e));
                        }}
                    """)
                    
                    print(f"[Cleanshelf] Page {page_num} successfully isolated {len(extracted_items)} clean unique items.")
                    
                    db = SessionLocal()
                    try:
                        for item in extracted_items:
                            raw_title = item['title'].strip()
                            full_card_text = item['fullText']
                            
                            if any(x in raw_title.lower() for x in ['cart', 'checkout', 'login', 'account', 'menu', 'shop', 'categories']):
                                continue
                                
                            price_match = re.search(r"(?:KES|Ksh|Sh)?\s*([\d,]+(?:\.\d{2})?)", full_card_text, re.IGNORECASE)
                            clean_price = None
                            
                            if price_match:
                                price_str = price_match.group(1).replace(",", "")
                                try:
                                    clean_price = float(price_str)
                                except ValueError:
                                    pass

                            if raw_title and clean_price and clean_price > 5:
                                # Ensure we aren't storing the category title accidentally
                                if raw_title.lower() != subcat.lower():
                                    print(f"  -> [Captured] '{raw_title}' - KES {clean_price}")
                                    ingest_scraped_product(db, supermarket_id, raw_title, clean_price)
                    finally:
                        db.close()
                        
                except Exception as e:
                    print(f"[Cleanshelf Error] Loop processing issue: {e}")
                    
        await browser.close()
        print("\n[Cleanshelf] Engine execution finalized cleanly.")

if __name__ == "__main__":
    asyncio.run(scrape_cleanshelf())