import re
import requests
from urllib.parse import urlparse, parse_qs, urlunparse
from config import SUPPORTED_SHORTENERS, GENDER_KEYWORDS

def is_out_of_stock(soup):
    """
    Check if a product is out of stock based on the parsed HTML soup
    """
    # Common indicators of out of stock status
    out_of_stock_indicators = [
        'out of stock',
        'out of Stock',
        'sold out',
        'Sold Out',
        'unavailable',
        'not available',
        'currently unavailable'
    ]
    
    # Look for stock status in common locations
    stock_elements = soup.find_all(['div', 'span', 'p'], class_=lambda x: x and any(keyword in x.lower() for keyword in ['stock', 'availability', 'status']))
    
    for element in stock_elements:
        text = element.get_text().strip()
        if any(indicator in text for indicator in out_of_stock_indicators):
            return True
    
    # Check for specific out of stock classes
    out_of_stock_elements = soup.find_all(class_=lambda x: x and any(keyword in x.lower() for keyword in ['out-of-stock', 'outofstock', 'sold-out', 'soldout']))
    
    if out_of_stock_elements:
        return True
    
    return False

def format_price(price_str):
    """Format price string to extract numeric value"""
    if not price_str:
        return None
    
    # Remove currency symbols and extra characters
    import re
    price_clean = re.sub(r'[^\d.,]', '', price_str)
    
    # Handle different decimal separators
    if ',' in price_clean and '.' in price_clean:
        # Both comma and dot present, assume comma is thousand separator
        price_clean = price_clean.replace(',', '')
    elif ',' in price_clean:
        # Only comma, assume it's decimal separator for some locales
        price_clean = price_clean.replace(',', '.')
    
    try:
        return float(price_clean)
    except ValueError:
        return None

def clean_text(text):
    """Clean and normalize text"""
    if not text:
        return ""
    return text.strip().replace('\n', ' ').replace('\r', ' ')

def is_supported_platform(url):
    """Check if URL is from a supported e-commerce platform"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    return any(platform in domain for platform in [
        "amazon.in", "flipkart.com", "meesho.com", 
        "myntra.com", "ajio.com", "snapdeal.com", 
        "wishlink.com"
    ])

def is_shortened_url(url):
    """Check if URL is from a supported shortener"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    return any(shortener in domain for shortener in SUPPORTED_SHORTENERS)

def unshorten_url(url):
    """Resolve shortened URLs to their original form"""
    try:
        # Follow redirects without downloading content
        response = requests.head(url, allow_redirects=True, timeout=5)
        final_url = response.url
        
        # Remove affiliate parameters
        parsed = urlparse(final_url)
        query_params = parse_qs(parsed.query)
        
        # Remove common affiliate parameters
        affiliate_params = [
            'tag', 'ref', 'ref_', 'utm_source', 'utm_medium', 
            'utm_campaign', 'utm_term', 'utm_content', 'affid',
            'affExtParam1', 'affExtParam2', 'affID', 'p_id'
        ]
        
        cleaned_params = {k: v for k, v in query_params.items() 
                         if k not in affiliate_params}
        
        # Reconstruct URL without affiliate parameters
        new_query = '&'.join([f"{k}={v[0]}" for k, v in cleaned_params.items()])
        clean_url = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
        
        return clean_url if clean_url else final_url
    except:
        return url

def extract_price(text):
    """Extract price from text"""
    if not text:
        return None
    
    # Pattern to match ₹ or Rs followed by digits
    patterns = [
        r'[₹Rs]\s*([\d,]+)',
        r'(\d+)\s*[₹Rs]',
        r'price.*?[₹Rs]\s*([\d,]+)',
        r'[\₹Rs]\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price_str = match.group(1).replace(',', '')
            try:
                return str(int(float(price_str)))
            except:
                continue
    return None

def extract_pin_code(text):
    """Extract 6-digit pin code from text"""
    if not text:
        return None
    
    pin_pattern = r'\b\d{6}\b'
    match = re.search(pin_pattern, text)
    return match.group(0) if match else None

def detect_gender(title):
    """Detect gender from product title"""
    if not title:
        return ""
    
    title_lower = title.lower()
    
    for gender, keywords in GENDER_KEYWORDS.items():
        if any(keyword in title_lower for keyword in keywords):
            return gender.capitalize()
    
    return ""

def clean_title(title):
    """Clean product title"""
    if not title:
        return ""
    
    # Remove extra spaces and clean up
    title = re.sub(r'\s+', ' ', title.strip())
    
    # Remove common marketing words
    marketing_words = [
        'best', 'deal', 'offer', 'sale', 'discount', 'limited',
        'exclusive', 'new', 'latest', 'trending', 'popular'
    ]
    
    words = title.split()
    cleaned_words = [word for word in words if word.lower() not in marketing_words]
    
    return ' '.join(cleaned_words)

def extract_quantity(title):
    """Extract quantity information from title"""
    if not title:
        return ""
    
    # Patterns for quantity extraction
    patterns = [
        r'pack\s+of\s+(\d+)',
        r'set\s+of\s+(\d+)',
        r'(\d+)\s*pcs?',
        r'(\d+)\s*pieces?',
        r'(\d+)\s*items?'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return f"Pack of {match.group(1)}"
    
    return ""
