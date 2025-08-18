# bot.py - ReviewCheckk Bot (Enhanced with OCR & Depth)
"""
REVIEWCHECKK BOT - ENHANCED VERSION WITH OCR
Follows 99+ Rules | Resource-Conscious | Includes OCR Fallback
"""

import os
import re
import io
import time
import logging
import asyncio
import tempfile
import requests
from urllib.parse import urlparse, parse_qs
from PIL import Image
import pytesseract
from bs4 import BeautifulSoup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update, InputMediaPhoto

# ========================
# CONFIGURATION
# ========================
BOT_TOKEN = "8327175937:AAGoWZPlDM_UX7efZv6_7vJMHDsrZ3-EyIA" # Replace with your token
BOT_USERNAME = "@Easy_uknowbot"
PIN_DEFAULT = "110001"
SUPPORTED_DOMAINS = {
    "amazon.in": "amazon",
    "flipkart.com": "flipkart",
    "meesho.com": "meesho",
    "myntra.com": "myntra",
    "ajio.com": "ajio",
    "snapdeal.com": "snapdeal"
}
SHORTENER_DOMAINS = ["cutt.ly", "fkrt.cc", "amzn-to.co", "bitli.in", "spoo.me", "da.gd", "wishlink.com"]

# ========================
# LOGGING SETUP
# ========================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========================
# UTILITY FUNCTIONS
# ========================

def expand_short_url(url, max_redirects=5):
    """Expand shortened URLs."""
    logger.info(f"Expanding short URL: {url}")
    original_url = url
    for _ in range(max_redirects):
        try:
            response = requests.head(url, allow_redirects=False, timeout=5)
            if 'location' in response.headers:
                url = response.headers['location']
                logger.debug(f"Redirected to: {url}")
            else:
                break
        except Exception as e:
            logger.warning(f"Error expanding URL {url}: {e}")
            return original_url
    logger.info(f"Expanded URL: {url}")
    return url

def clean_url(url):
    """Rule 14-16: Remove affiliate tags and shorten parameters."""
    logger.info(f"Cleaning URL: {url}")
    # Expand if short
    if any(short_domain in url for short_domain in SHORTENER_DOMAINS):
        url = expand_short_url(url)

    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    # Keep essential product parameters only
    essential_params = {
        'meesho.com': ['pid', 'product_id'],
        'myntra.com': ['p', 'productId'],
        'amazon.in': ['asin', 'dp'],
        'flipkart.com': ['pid', 'marketplace', 'product_id']
    }
    domain_key = next((k for k in essential_params if k in parsed.netloc), None)
    keep_params = essential_params.get(domain_key, [])
    
    filtered_query = "&".join([
        f"{k}={v[0]}" for k, v in query_params.items() 
        if k.lower() in [p.lower() for p in keep_params]
    ])
    clean_url_str = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if filtered_query:
        clean_url_str += f"?{filtered_query}"
    logger.info(f"Cleaned URL: {clean_url_str}")
    return clean_url_str

def is_supported(url):
    """Check if domain is supported."""
    domain = urlparse(url).netloc.lower()
    return any(supported_domain in domain for supported_domain in SUPPORTED_DOMAINS)

def get_platform(url):
    """Get platform name from URL."""
    domain = urlparse(url).netloc.lower()
    for platform_domain, platform_name in SUPPORTED_DOMAINS.items():
        if platform_domain in domain:
            return platform_name
    return "generic"

def clean_title(title, platform, url):
    """Rules 23-31: Clean title according to strict formatting rules."""
    logger.debug(f"Cleaning title: '{title}' for platform: {platform}")
    if not title:
        return "Product"
    title = title.encode('ascii', 'ignore').decode('unicode_escape').strip()
    title = re.sub(r'\\[uU][0-9a-fA-F]{4}', '', title) # Remove unicode escapes
    title = re.sub(r'[^\w\s\-\'\.]', ' ', title) # Keep alphanum, space, -, ', .
    title = re.sub(r'\s+', ' ', title).strip() # Collapse spaces
    
    words = title.split()
    if not words:
        return "Product"
    
    # Rule 24: First word must be brand (assume first word is brand for now)
    brand = words[0].title()
    rest_title = ' '.join(words[1:8]) # Rule 28: 5-8 words max

    # Rule 29: Clothing must include gender
    is_clothing = any(kw in url.lower() for kw in ['men', 'women', 'kids', 'shirt', 't-shirt', 'jeans', 'kurti', 'saree', 'dress'])
    gender = ""
    if is_clothing:
        if re.search(r'\b(women|ladies|female|girl)\b', title, re.IGNORECASE):
            gender = "Women"
        elif re.search(r'\b(men|gentlemen|male|boy)\b', title, re.IGNORECASE):
            gender = "Men"
        elif re.search(r'\b(kids|children|baby)\b', title, re.IGNORECASE):
            gender = "Kids"
        else:
            gender = "Unisex" # Default if not found

    # Rule 30: Quantity like Pack of 2, 300ml, 1 Piece
    quantity = ""
    qty_match = re.search(r'\b(\d+)\s*(?:piece|pcs|ml|gm|kg|ltr|pack|set)\b', title, re.IGNORECASE)
    if qty_match:
        unit = qty_match.group(0).split()[-1]
        quantity = f"{qty_match.group(1)} {unit.title()}"

    # Rebuild title
    if is_clothing:
        # [Brand] [Gender] [Quantity] [Product Name]
        parts = [part for part in [brand, gender, quantity, rest_title] if part]
        return " ".join(parts)
    else:
        # [Brand] [Product Title] from @[price] rs
        # Price will be added later
        parts = [part for part in [brand, quantity, rest_title] if part]
        return " ".join(parts)

def parse_price(price_str):
    """Rules 32-39: Parse price string to numeric value."""
    logger.debug(f"Parsing price: '{price_str}'")
    if not price_str:
        return "Price unavailable"
    # Extract numeric value
    price_value = re.sub(r'[^\d.]', '', price_str)
    if not price_value:
        return "Price unavailable"
    try:
        return f"{float(price_value):.0f}"
    except ValueError:
        return "Price unavailable"

def extract_text_from_image(image_bytes):
    """OCR Fallback for title extraction."""
    logger.info("Performing OCR on image...")
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Convert to grayscale for better OCR
        grayscale_image = image.convert('L')
        text = pytesseract.image_to_string(grayscale_image)
        logger.debug(f"OCR extracted text: {text[:100]}...")
        return text.strip()
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return ""

# ========================
# SCRAPER FUNCTIONS
# ========================

def scrape_product(url, platform):
    """Scrape product details using requests and BeautifulSoup."""
    logger.info(f"Scraping {platform} product: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        logger.error(f"Failed to fetch page for {url}: {e}")
        return None

    title, price, image_url = "Product", "Price unavailable", None

    # --- Platform Specific Scraping ---
    if platform == "myntra":
        title_elem = soup.find('h1', class_='pdp-title')
        name_elem = soup.find('h1', class_='pdp-name')
        price_elem = soup.find('span', class_='pdp-price')
        image_elem = soup.find('div', class_='image-grid-image') # Main image container
        
        title = f"{name_elem.get_text(strip=True)} {title_elem.get_text(strip=True)}" if name_elem and title_elem else "Myntra Product"
        price = price_elem.get_text(strip=True) if price_elem else "Price unavailable"
        if image_elem and image_elem.get('style'):
             # Extract URL from style: background-image: url('...')
             style = image_elem['style']
             match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
             image_url = match.group(1) if match else None

    elif platform == "meesho":
        title_elem = soup.find('h1', class_='Text__StyledText-sc-1h1ca1g-0') # Check actual class
        if not title_elem: title_elem = soup.find('h1') # Fallback
        price_elem = soup.find('span', {'data-testid': 'price'}) # Check actual data-testid
        if not price_elem: price_elem = soup.find('span', string=re.compile(r'₹')) # Fallback
        
        title = title_elem.get_text(strip=True) if title_elem else "Meesho Product"
        price = price_elem.get_text(strip=True) if price_elem else "Price unavailable"
        # Image is harder without JS, skip for now or use a generic selector
        img_elem = soup.find('img', {'alt': lambda x: x and 'product' in x.lower()})
        image_url = img_elem.get('src') if img_elem else None

    elif platform == "amazon":
        title_elem = soup.find('span', {'id': 'productTitle'})
        price_whole = soup.find('span', {'class': 'a-price-whole'})
        price_symbol = soup.find('span', {'class': 'a-price-symbol'})
        price = f"{price_symbol.get_text(strip=True) if price_symbol else ''}{price_whole.get_text(strip=True) if price_whole else ''}"
        title = title_elem.get_text(strip=True) if title_elem else "Amazon Product"
        img_elem = soup.find('img', {'id': 'landingImage'})
        image_url = img_elem.get('src') if img_elem else None

    elif platform == "flipkart":
         # Flipkart often uses dynamic class names, this is a rough attempt
        title_elem = soup.find('span', {'class': 'VU-ZEz'}) # Product title class
        price_elem = soup.find('div', {'class': 'Nx9bqj'}) # Price class
        title = title_elem.get_text(strip=True) if title_elem else "Flipkart Product"
        price = price_elem.get_text(strip=True) if price_elem else "Price unavailable"
        img_elem = soup.find('img', {'class': '_2r_T1I'}) # Main image class
        image_url = img_elem.get('src') if img_elem else None

    else: # Generic fallback
        title_elem = soup.find('title') or soup.find('h1')
        title = title_elem.get_text(strip=True) if title_elem else "Product"
        # Generic price search
        price_elem = soup.find(string=re.compile(r'₹|Rs\.|Price'))
        if price_elem:
            price_match = re.search(r'[\d,]+\.?\d*', price_elem)
            price = price_match.group() if price_match else "Price unavailable"
        else:
            price = "Price unavailable"

    # Clean and finalize
    clean_title_str = clean_title(title, platform, url)
    clean_price = parse_price(price)

    return {
        'platform': platform,
        'title': clean_title_str,
        'price': clean_price,
        'url': url,
        'image_url': image_url
    }

# ========================
# FORMATTING
# ========================

def format_output(data, pin=PIN_DEFAULT):
    """Rules 40-50, 81-85: Format output according to platform-specific rules."""
    platform = data['platform']
    title = data['title']
    price = data['price']
    url = data['url']

    # Rule 51: Common footer
    footer = "\n@reviewcheckk"

    if platform == 'meesho':
        # Rule 41: Meesho format
        formatted = f"{title} @{price} rs\n{url}"
        # Rule 45: Add pin code
        formatted += f"\nPin - {pin}"
        return formatted + footer

    elif 'clothing' in title.lower() or platform in ['myntra', 'meesho']: # Heuristic for clothing
        # Rule 42: Clothing format (non-Meesho)
        formatted = f"{title} @{price} rs\n{url}"
        return formatted + footer

    else:
        # Rule 43: Non-clothing format
        formatted = f"{title} from @{price} rs\n{url}"
        return formatted + footer

# ========================
# COMMAND HANDLERS
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🚀 {BOT_USERNAME} Ready!\n"
        "Send product links from Amazon, Flipkart, Meesho, Myntra, Ajio, Snapdeal.\n"
        "Commands: /advancing, /off_advancing, /img"
    )

async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.strip()
    if command == "/advancing":
        # In a real bot, you'd set a flag. Here we just acknowledge.
        await update.message.reply_text("✅ Advanced Mode ON (Simulated)")
    elif command == "/off_advancing":
        await update.message.reply_text("✅ Advanced Mode OFF (Simulated)")

async def img_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Regenerating image... (Simulated)")

# ========================
# MESSAGE HANDLER
# ========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    text = update.message.text or update.message.caption or ""
    photo = update.message.photo[-1] if update.message.photo else None # Get largest photo
    
    urls = re.findall(r'https?://[^\s]+', text)
    pin_code = PIN_DEFAULT
    pin_match = re.search(r'(?:pin|code)\s*[:\-]?\s*(\d{6})', text, re.IGNORECASE)
    if pin_match:
        pin_code = pin_match.group(1)

    # --- Handle OCR Fallback ---
    ocr_title = ""
    if photo and not urls:
        logger.info("No URL found, attempting OCR...")
        try:
            file = await context.bot.get_file(photo.file_id)
            image_bytes = await file.download_as_bytearray()
            ocr_title = extract_text_from_image(bytes(image_bytes))
            if ocr_title:
                 # Try to find a URL in the OCR text
                ocr_urls = re.findall(r'https?://[^\s]+', ocr_title)
                urls.extend(ocr_urls)
                logger.info(f"Found URLs via OCR: {ocr_urls}")
        except Exception as e:
            logger.error(f"Error during OCR processing: {e}")
    
    if not urls:
        if ocr_title:
            await update.message.reply_text(f"OCR Extracted Text:\n{ocr_title[:200]}...\n(No valid product link found)")
        # else: # Optional: Ignore messages with no links/usable content
        #     pass
        return

    for url in urls:
        logger.info(f"Processing URL: {url}")
        clean_url_str = clean_url(url)
        
        if not is_supported(clean_url_str):
            await update.message.reply_text("❌ Unsupported or invalid product link.")
            continue

        platform = get_platform(clean_url_str)
        data = scrape_product(clean_url_str, platform)

        if not data:
            await update.message.reply_text("❌ Unable to extract product info.")
            continue

        formatted_text = format_output(data, pin_code)
        
        # --- Handle Image Sending ---
        media_group = []
        if data.get('image_url'):
            try:
                img_response = requests.get(data['image_url'], timeout=10)
                img_response.raise_for_status()
                image_bytes = img_response.content
                # Validate it's an image
                img = Image.open(io.BytesIO(image_bytes))
                # Send image with caption
                await update.message.reply_photo(photo=io.BytesIO(image_bytes), caption=formatted_text)
                continue # Skip sending text separately
            except Exception as e:
                logger.warning(f"Failed to send image from URL: {e}")
        
        # Fallback: Send text only
        await update.message.reply_text(formatted_text)

    logger.info(f"Processed message in {time.time() - start_time:.2f} seconds.")

# ========================
# MAIN
# ========================

def main():
    logger.info("Starting ReviewCheckk Bot...")
    try:
        app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
        
        # Register handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("advancing", mode_command))
        app.add_handler(CommandHandler("off_advancing", mode_command))
        app.add_handler(CommandHandler("img", img_command))
        app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION | filters.PHOTO, handle_message))
        
        logger.info("Bot handlers registered. Starting polling...")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)

if __name__ == "__main__":
    main()    
    
        # If there's a caption, try to extract product info
        if caption:
            # Simple title extraction from caption
            title = caption.split('\n')[0][:100]  # First line, max 100 chars
            
            # Create a basic response
            response = f"{title}\n[Image-based product]\n\n@reviewcheckk"
            
            # Send the same image back with formatted caption
            await update.message.reply_photo(
                photo=photo.file_id,
                caption=response
            )
    except Exception as e:
        logger.error(f"Error handling image: {e}")

def extract_urls(text):
    """Extract all URLs from text"""
    if not text:
        return []
    
    # URL regex pattern
    url_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
    urls = re.findall(url_pattern, text)
    return urls

def format_product_post(product_data):
    """Format product data according to requirements"""
    try:
        platform = product_data.get('platform', 'unknown')
        title = product_data.get('title', 'Product Title')
        price = product_data.get('price', '0')
        url = product_data.get('url', '')
        pin = product_data.get('pin', '110001')
        gender = product_data.get('gender', '')
        quantity = product_data.get('quantity', '')
        sizes = product_data.get('sizes', '')
        
        # Clean and format title
        clean_title = title.strip()
        
        # Platform-specific formatting
        if platform == 'meesho':
            # [Gender] [Quantity] [Clean Title] @[price] rs
            formatted_title = f"{gender} {quantity} {clean_title}".strip()
            formatted_title = f"{formatted_title} @{price} rs"
            
            response = f"{formatted_title}\n{url}\n\n"
            
            # Add sizes if available
            if sizes:
                response += f"Size - {sizes}\n"
            else:
                response += "Size - All\n"
            
            # Add pin
            response += f"Pin - {pin}\n\n@reviewcheckk"
            
        else:
            # For other platforms: [Brand] [Clean Title] from @[price] rs
            # For clothing: [Gender] [Quantity] [Clean Title] @[price] rs
            if gender or quantity:
                formatted_title = f"{gender} {quantity} {clean_title}".strip()
                formatted_title = f"{formatted_title} @{price} rs"
            else:
                # Assume brand is first word for non-clothing
                words = clean_title.split()
                if len(words) > 1:
                    brand = words[0]
                    rest_title = ' '.join(words[1:])
                    formatted_title = f"{brand} {rest_title} from @{price} rs"
                else:
                    formatted_title = f"{clean_title} from @{price} rs"
            
            response = f"{formatted_title}\n{url}\n\n@reviewcheckk"
        
        return response.strip()
    except Exception as e:
        logger.error(f"Error formatting post: {e}")
        return "❌ Unable to extract product info."

async def main():
    """Main function to start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.CAPTION,
        process_message
    ))
    
    # Start the bot
    logger.info("Starting bot...")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
