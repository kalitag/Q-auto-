import asyncio
from playwright.async_api import async_playwright
from PIL import Image
import io
import base64

async def take_screenshot(url):
    """Take mobile-view screenshot of product page"""
    try:
        async with async_playwright() as p:
            # Launch browser with mobile user agent
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 375, 'height': 812},
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15'
            )
            
            page = await context.new_page()
            
            # Navigate to URL with timeout
            await page.goto(url, wait_until='networkidle', timeout=10000)
            
            # Wait for common product elements to load
            await page.wait_for_timeout(2000)
            
            # Take screenshot
            screenshot = await page.screenshot(full_page=False)
            
            await browser.close()
            
            # Convert to PIL Image for processing
            image = Image.open(io.BytesIO(screenshot))
            
            # Convert back to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=85)
            
            return img_byte_arr.getvalue()
    except Exception as e:
        print(f"Screenshot error: {e}")
        return None

def is_out_of_stock(html_content):
    """Check if product is out of stock"""
    if not html_content:
        return False
    
    # Common out-of-stock indicators
    oos_indicators = [
        'out of stock', 'out of Stock', 'sold out', 'sold Out',
        'currently unavailable', 'not available', 'not in stock'
    ]
    
    content_lower = html_content.lower()
    
    return any(indicator in content_lower for indicator in oos_indicators)
