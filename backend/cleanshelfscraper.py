import asyncio
import re
from playwright.async_api import async_playwright
from database import SessionLocal
from pipeline import ingest_scraped_product

supermarket_id = 3  # database identifier for Cleanshelf supermarket

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

TOTAL_PAGES_TO_SCRAPE = 7

async def handle_cleanshelf_popups(page, max_wait_time_ms=5000):
    """
    Actively tracks down and Jordan neutralizes region selection prompts, location blockers, 
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
                        await page.wait_for_timeout(1500)  
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
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            permissions=["geolocation"],
            geolocation={"latitude": -0.3031, "longitude": 36.0613}  
        )
        page = await context.new_page()
        
        print("[Cleanshelf] Priming initial baseline session at root shop entry...")
        try:
            await page.goto("https://cleanshelf.online/shop", timeout=45000, wait_until="networkidle")
            await handle_cleanshelf_popups(page, max_wait_time_ms=7000)
        except Exception as e:
            print(f"[Cleanshelf Warning] Base shop route setup bypassed: {e}")

        for subcat in CLEANSHELF_SUBCATEGORIES:
            print(f"\n[Processing Stream] Accessing Category Side-panel: {subcat.upper()}")
            
            try:
                category_selector = f"a[href*='category_slug={subcat}']"
                cat_link = page.locator(category_selector).first
                
                if await cat_link.is_visible():
                    print(f"   [Navigation] Navigating internally via sidebar click targeting: {subcat}")
                    await cat_link.click()
                else:
                    print(f"   [Navigation Fallback] Sidebar hidden, using link load for: {subcat}")
                    await page.goto(f"https://cleanshelf.online/shop?category_slug={subcat}", wait_until="domcontentloaded")
                
                await handle_cleanshelf_popups(page, max_wait_time_ms=4000)
                
            except Exception as e:
                print(f"[Cleanshelf Error] Could not parse navigation target {subcat}: {e}")
                continue

            # Sequential pagination block
            for page_num in range(1, TOTAL_PAGES_TO_SCRAPE + 1):
                print(f"\n -> [Scraping View] {subcat.upper()} | CURRENT PAGE STATE: {page_num}")
                
                try:
                    await handle_cleanshelf_popups(page, max_wait_time_ms=2000)

                    # Dynamic scrolling pipeline
                    for i in range(4):
                        await page.evaluate(f"window.scrollTo(0, (document.body.scrollHeight / 4) * {i + 1});")
                        await page.wait_for_timeout(800)
                    
                    # FIXED: Removed f-string entirely, changed to a pure raw string (r""") 
                    # Passed subcat.lower() as a runtime parameter down into the evaluate call.
                    extracted_items = await page.evaluate(r"""
                        (subcatLower) => {
                            const data = [];
                            const elements = document.querySelectorAll('p, span, div, h3, h4, h5, a');

                            const extractImageFromEl = (imgEl) => {
                                let url = imgEl.getAttribute('src') || '';
                                if (!url || url.startsWith('data:')) {
                                    url = imgEl.getAttribute('data-src') || imgEl.getAttribute('data-lazy-src') || url;
                                }
                                if (!url) {
                                    const srcset = imgEl.getAttribute('srcset') || imgEl.getAttribute('data-srcset');
                                    if (srcset) {
                                        url = srcset.split(',')[0].trim().split(' ')[0];
                                    }
                                }
                                return url;
                            };
                            
                            elements.forEach(el => {
                                const text = el.innerText ? el.innerText.trim() : '';
                                if (text && (text.startsWith('KES') || text.startsWith('Ksh') || /^\d{2,4}(\.\d{2})?$/.test(text))) {
                                    let parent = el.parentElement;
                                    let title = "";
                                    let imageUrl = "";
                                    let attempts = 0;
                                    
                                    while (parent && attempts < 5) {
                                        const targets = parent.querySelectorAll('a, h3, h4, h5, .product-name, div[class*="title"]');
                                        for (let target of targets) {
                                            const targetText = target.innerText ? target.innerText.trim() : '';
                                            if (
                                                targetText.length > 4 && 
                                                targetText.toLowerCase() !== subcatLower &&
                                                targetText.toLowerCase() !== "shop" &&
                                                !targetText.startsWith('KES') && 
                                                !targetText.startsWith('Ksh') &&
                                                !/^\d+$/.test(targetText)
                                            ) {
                                                title = targetText;
                                                break;
                                            }
                                        }

                                        // Look for a nearby image in this same ancestor scope
                                        if (!imageUrl) {
                                            const imgEl = parent.querySelector('img');
                                            if (imgEl) {
                                                imageUrl = extractImageFromEl(imgEl);
                                            }
                                        }

                                        if (title) break;
                                        parent = parent.parentElement;
                                        attempts++;
                                    }
                                    
                                    if (!title && el.parentElement) {
                                        const lines = el.parentElement.innerText.split('\n');
                                        for (let line of lines) {
                                            const cleanLine = line.trim();
                                            if (
                                                cleanLine.length > 5 && 
                                                cleanLine.toLowerCase() !== subcatLower && 
                                                cleanLine.toLowerCase() !== "shop" &&
                                                !cleanLine.includes('KES') && 
                                                !cleanLine.includes('Ksh')
                                            ) {
                                                title = cleanLine;
                                                break;
                                            }
                                        }
                                    }
                                    
                                    if (title && title.length < 90) {
                                        data.push({ 
                                            title: title, 
                                            fullText: el.parentElement ? el.parentElement.innerText : text,
                                            imageUrl: imageUrl
                                        });
                                    }
                                }
                            });
                            return Array.from(new Set(data.map(a => JSON.stringify(a)))).map(e => JSON.parse(e));
                        }
                    """, subcat.lower()) # <-- Parameter passed safely here
                    
                    print(f"[Cleanshelf] Extracted {len(extracted_items)} items on page {page_num}.")
                    
                    if extracted_items:
                        db = SessionLocal()
                        try:
                            for item in extracted_items:
                                raw_title = item['title'].strip()
                                full_card_text = item['fullText']

                                raw_image_url = (item.get('imageUrl') or '').strip()
                                image_url = None
                                if raw_image_url:
                                    if raw_image_url.startswith("//"):
                                        image_url = f"https:{raw_image_url}"
                                    elif raw_image_url.startswith("/"):
                                        image_url = f"https://cleanshelf.online{raw_image_url}"
                                    else:
                                        image_url = raw_image_url
                                
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
                                    if raw_title.lower() != subcat.lower():
                                        print(f"  -> [Captured] '{raw_title}' - KES {clean_price} - IMG: {image_url or 'N/A'}")
                                        ingest_scraped_product(db, supermarket_id, raw_title, clean_price, image_url=image_url, category=subcat)
                        finally:
                            db.close()

                    # Handle Pagination Transitions using setup from image_eb2560.png
                    if page_num < TOTAL_PAGES_TO_SCRAPE:
                        print(f"[Pagination] Transitioning forward from page {page_num}...")
                        
                        next_button = page.locator("button:has-text('Next'), a:has-text('Next'), .next").first
                        
                        if await next_button.is_visible() and await next_button.is_enabled():
                            print("   [Pagination] 'Next' pill button located. Executing click event.")
                            await next_button.scroll_into_view_if_needed()
                            await next_button.click()
                            
                            await page.wait_for_timeout(3500)
                        else:
                            print("[Pagination Warning] 'Next' button element is missing or disabled. Closing subcategory.")
                            break
                            
                except Exception as e:
                    print(f"[Cleanshelf Error] Loop processing hurdle on current screen: {e}")
                    continue
                    
        print("\n[Cleanshelf] Finalizing operations...")
        await page.wait_for_timeout(2000)
        await browser.close()
        print("[Cleanshelf] Engine execution finalized cleanly.")

if __name__ == "__main__":
    asyncio.run(scrape_cleanshelf())