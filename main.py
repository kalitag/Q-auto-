import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, filters, 
    ContextTypes, CommandHandler
)
from utils import (
    is_shortened_url, unshorten_url, 
    is_supported_platform
)
from scraper import ProductScraper
from screenshot import take_screenshot
from config import BOT_TOKEN, BOT_USERNAME
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

scraper = ProductScraper()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await update.message.reply_text(
        f"Hello! I'm {BOT_USERNAME}\n"
        "Forward me any e-commerce product link and I'll format it for you!"
    )

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message processing function"""
    try:
        message = update.message
        text = message.text if message.text else ""
        caption = message.caption if message.caption else ""
        
        # Combine text and caption for processing
        full_text = f"{text} {caption}".strip()
        
        # Extract URLs from message
        urls = extract_urls(full_text)
        
        if not urls:
            # Check if it's an image with caption
            if message.photo:
                await handle_image_message(update, context, full_text)
            return
        
        # Process each URL
        for url in urls:
            await process_single_url(update, context, url, full_text, message)
            
    except Exception as e:
        logger.error(f"Error processing message: {e}")

async def process_single_url(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           url: str, full_text: str, message):
    """Process a single product URL"""
    try:
        # Handle shortened URLs
        if is_shortened_url(url):
            url = unshorten_url(url)
        
        # Check if platform is supported
        if not is_supported_platform(url):
            return
        
        # Take screenshot
        screenshot = await take_screenshot(url)
        
        # Scrape product data
        product_data = scraper.scrape_product(url, full_text)
        
        # Check if out of stock
        if product_data.get("out_of_stock"):
            await update.message.reply_text("⚠️ Product is OUT OF STOCK")
            return
        
        # Check for scraping errors
        if product_data.get("error"):
            await update.message.reply_text("❌ Unable to extract product info.")
            return
        
        # Format response
        formatted_response = format_product_post(product_data)
        
        # Send response with screenshot
        if screenshot:
            await update.message.reply_photo(
                photo=screenshot,
                caption=formatted_response,
                parse_mode=None
            )
        else:
            await update.message.reply_text(formatted_response)
            
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        await update.message.reply_text("❌ Unable to extract product info.")

async def handle_image_message(update: Update, context: ContextTypes.DEFAULT_TYPE, caption: str):
    """Handle forwarded images"""
    try:
        # Get the largest photo
        photo = update.message.photo[-1]
        
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
