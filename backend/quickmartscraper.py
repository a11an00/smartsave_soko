import asyncio
import re
from playwright.async_api import async_playwright
from database import SessionLocal
from pipeline import ingest_scraped_product

supermarket_id = 2  # Quickmart's unique identifier in the database
#list of subcategories to scrape from Quickmart, can be expanded or modified as needed
QUICKMART_SUBCATEGORIES = [
    "spirits",
    "beer",
    "wines",
    "juices-carbonates",
    "cooking-oils-fats",
    "sugar",
    "rice-cereals",
    "dairy-products",
    "cakes-bread",
    "tv",
]

MAX_PAGES_PER_CATEGORY = 3  # Safeguard boundary limit
#handle all popups that may appear on the page, such as age gates, location screens, and initial cookie overlays
async def handle_quickmart_popups(page, max_wait_time_ms=5000):
    """Destroys age gates, location screens, and initial cookie overlays."""
    try:
        start_time = asyncio.get_event_loop().time()
        blockers = [
            "button:has-text('Yes')",
            "text=By Proceeding with this purchase, you confirm",
            "button:has-text('Use My Current Location')",
            "button:has-text('Continue')",
            "button:has-text('Close')",
            "[aria-label='Close']",
            ".modal-close",
            ".close"
        ]
        
        while (asyncio.get_event_loop().time() - start_time) * 1000 < max_wait_time_ms:
            popup_found = False
            for selector in blockers:
                try:
                    locator = page.locator(selector).first
                    if await locator.is_visible():
                        print(f"   [Quickmart Shield] Cleared modal element: {selector}")
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
        print(f"   [Quickmart Warning] Popup exception: {e}")

async def scrape_quickmart():
    async with async_playwright() as p:
        print("[Scraper] Launching browser engine for Quickmart...")
        browser = await p.chromium.launch(headless=False)
        #open chrome browser with a custom user agent and viewport size to mimic a real user
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            permissions=["geolocation"], 
            geolocation={"latitude": -0.3031, "longitude": 36.0613} # Nakuru County
        )
        page = await context.new_page()
        
        # open website and pass to popup handler
        print("\n[Quickmart] Performing baseline setup...")
        try:
            await page.goto("https://www.quickmart.co.ke/", timeout=60000, wait_until="domcontentloaded")
            await handle_quickmart_popups(page, max_wait_time_ms=6000)
        except Exception as home_err:
            print(f"[Quickmart Warning] Base initialization bypassed: {home_err}")
        #loop through each subcategory and scrape product data
        for subcat in QUICKMART_SUBCATEGORIES:
            url = f"https://www.quickmart.co.ke/{subcat}"
            print(f"\n [Processing Subcategory] Quickmart -> {subcat.upper()}")
            
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                await handle_quickmart_popups(page, max_wait_time_ms=5000)
                
                page_count = 1
                while page_count <= MAX_PAGES_PER_CATEGORY:
                    print(f"\n⚡ [Viewport Processing] Scanning Page {page_count}...")
                    
                    # Gradual viewport scroll down to force lazy component loading
                    for scroll in range(4):
                        await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {scroll + 1} / 4);")
                        await page.wait_for_timeout(1000)
                    
                    # view whole page content and wait for any dynamic content to load
                    #find product cards by common class patterns and filter for price text and title text
                    extracted_items = await page.evaluate("""
                        () => {
                            const items = [];
                            let cards = Array.from(document.querySelectorAll(
                                '[class*="product-item"], [class*="product-card"], [class*="product-thumb"], .grid-item, [class*="col-"]'
                            ));
                            
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
                                if (title.trim() && textContent.length < 500 && (textContent.includes('KES') || textContent.includes('Ksh') || /\\d/.test(textContent))) {
                                    items.push({ title: title, fullText: textContent });
                                }
                            });
                            return items;
                        }
                    """)
                    
                    print(f"[Quickmart] Retrieved {len(extracted_items)} raw elements on Page {page_count}.")
                    
                    # Save results to DB
                    db = SessionLocal()
                    try:
                        for item in extracted_items:
                            raw_title = re.sub(r'\s+', ' ', item['title'].strip())
                            full_card_text = item['fullText']
                            
                            price_match = re.search(r"(?:KES|Ksh|Sh)\s*([\d,]+(?:\.\d{2})?)", full_card_text, re.IGNORECASE)
                            clean_price = None
                            
                            if price_match:
                                try: clean_price = float(price_match.group(1).replace(",", ""))
                                except ValueError: pass
                                
                            if raw_title and clean_price and 10 < clean_price < 150000:
                                if len(raw_title) < 90 and raw_title.lower() != subcat.lower():
                                    print(f" -> [Captured] '{raw_title}' - KES {clean_price}")
                                    ingest_scraped_product(db, supermarket_id, raw_title, clean_price)
                    finally:
                        db.close()

                    # --- PAGINATION NAVIGATION SHIELD ---
                    #navigate from the current page to the next page if available, else break the loop
                    # We attempt to locate the next button by its structural position in the pagination block.
                    pagination_buttons = page.locator("div.pagination button, .pagination button, [class*='pagination'] button, [class*='page'] a")
                    button_count = await pagination_buttons.count()
                    
                    if button_count >= 2:
                        # The second-to-last button is structurally the single-right chevron (">")
                        next_button = pagination_buttons.nth(button_count - 2)
                        
                        if await next_button.is_visible():
                            # Check if the button or its parent container is visually disabled or unclickable
                            is_disabled = await next_button.evaluate("""
                                el => el.hasAttribute('disabled') || 
                                      el.classList.contains('disabled') || 
                                      el.getAttribute('aria-disabled') === 'true' ||
                                      getComputedStyle(el).pointerEvents === 'none'
                            """)
                            
                            if is_disabled:
                                print(f"[Quickmart] Page {page_count} is the final terminal node index. Finishing subcategory.")
                                break
                                
                            print(f"[Pagination Click] Clicking next chevron to load Page {page_count + 1}...")
                            await next_button.scroll_into_view_if_needed()
                            await next_button.click(force=True)
                            
                            # Give the dynamic client framework a moment to completely swap out the product cards
                            await page.wait_for_timeout(4000) 
                            page_count += 1
                        else:
                            print("[Quickmart] Next pagination button is hidden or out of frame.")
                            break
                    else:
                        print("[Quickmart] No functional pagination element block found on this layout layout.")
                        break

            except Exception as e:
                print(f"[Quickmart Error] Processing interrupted on path route: {e}")
                
        await browser.close()
        print("\n[Quickmart] Engine execution finalized cleanly.")

if __name__ == "__main__":
    asyncio.run(scrape_quickmart())