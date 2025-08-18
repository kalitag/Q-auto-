# config.py

# ======================
# BOT CONFIGURATION
# ======================
BOT_TOKEN = "8327175937:AAGoWZPlDM_UX7efZv6_7vJMHDsrZ3-EyIA" # <-- REPLACE WITH YOUR ACTUAL TOKEN
BOT_NAME = "Work_flow"
BOT_USERNAME = "@Easy_uknowbot"
ADMIN_USER_IDS = []  # Add numeric Telegram user IDs for admin commands, e.g., [123456789, 987654321]

# ======================
# PLATFORM SUPPORT
# ======================
SUPPORTED_DOMAINS = {
    'amazon': 'amazon.in',
    'flipkart': 'flipkart.com',
    'meesho': 'meesho.com',
    'myntra': 'myntra.com',
    'ajio': 'ajio.com',
    'snapdeal': 'snapdeal.com',
    'wishlink': 'wishlink.com'
}

SHORTENER_DOMAINS = [
    'cutt.ly', 'fkrt.cc', 'amzn-to.co',
    'bitli.in', 'spoo.me', 'da.gd', 'wishlink.com'
]

# ======================
# SYSTEM & DEFAULTS
# ======================
PIN_DEFAULT = '110001'
SCREENSHOT_DIR = "screenshots"
MAX_RETRIES = 2
WATERMARK_THRESHOLD = 0.85 # Placeholder for future use
OCR_CONFIDENCE = 0.75      # Placeholder for future use

# ======================
# PERFORMANCE TUNING
# ======================
PERFORMANCE = {
    'page_load_timeout': 8,      # Seconds for page load
    'element_wait_timeout': 5,   # Seconds for element waits
    'max_workers': 3,            # Max concurrent scraping tasks
    'cache_ttl': 300,            # 5 minutes (Placeholder)
    'cache_max_size': 1000,      # Max cache entries (Placeholder)
    'response_target': 2.5,      # Target processing time per message (seconds)
    'monitor_interval': 10       # Log performance every N messages
}

# Global state flags (can be modified by commands)
MODE_ADVANCED = False
