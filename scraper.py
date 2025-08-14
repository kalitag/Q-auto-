import requests
from bs4 import BeautifulSoup
import json
import re
from utils import (
    extract_price, detect_gender, clean_title, 
    extract_quantity, is_out_of_stock
)
from config import DEFAULT_PIN

class ProductScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

import requests
from bs4 import BeautifulSoup
from utils import (
    is_out_of_stock,
    format_price,
    clean_text
)

class ProductScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def scrape_product(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Determine which site to scrape
            if 'flipkart' in url.lower():
                return self._scrape_flipkart(soup)
            elif 'amazon' in url.lower():
                return self._scrape_amazon(soup)
            else:
                return {"error": "Unsupported website"}

        except Exception as e:
            return {"error": f"Scraping failed: {str(e)}"}

    def _scrape_flipkart(self, soup):
        # Flipkart specific selectors
        title_elem = soup.find('span', {'class': 'B_NuCI'})
        price_elem = soup.find('div', {'class': '_30jeq3 _16Jk6d'})
        image_elem = soup.find('img', {'class': '_396cs4 _2amPTt _3qGmMb'})
        
        title = title_elem.get_text().strip() if title_elem else "Title not found"
        price = price_elem.get_text().strip() if price_elem else "Price not found"
        image_url = image_elem.get('src') if image_elem else ""
        
        # Check stock status
        out_of_stock = is_out_of_stock(soup)
        
        return {
            'title': title,
            'price': format_price(price),
            'image_url': image_url,
            'out_of_stock': out_of_stock
        }

    def _scrape_amazon(self, soup):
        # Amazon specific selectors
        title_elem = soup.find('span', {'id': 'productTitle'})
        price_elem = soup.find('span', {'class': 'a-price-whole'})
        image_elem = soup.find('img', {'id': 'landingImage'})
        
        title = title_elem.get_text().strip() if title_elem else "Title not found"
        price = price_elem.get_text().strip() if price_elem else "Price not found"
        image_url = image_elem.get('src') if image_elem else ""
        
        # Check stock status
        out_of_stock = is_out_of_stock(soup)
        
        return {
            'title': title,
            'price': format_price(price),
            'image_url': image_url,
            'out_of_stock': out_of_stock
    }
    
    def scrape_product(self, url, message_text=""):
        """Main scraping function"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Check if out of stock
            if is_out_of_stock(response.text):
                return {"out_of_stock": True}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract product details
            product_data = {
                "title": self._extract_title(soup, response.text),
                "price": self._extract_price(soup, response.text),
                "platform": self._detect_platform(url),
                "url": url,
                "pin": self._extract_pin(message_text),
                "gender": detect_gender(self._extract_title(soup, response.text)),
                "quantity": extract_quantity(self._extract_title(soup, response.text)),
                "sizes": self._extract_sizes(soup, url)
            }
            
            return product_data
        except Exception as e:
            print(f"Scraping error: {e}")
            return {"error": True}
    
    def _extract_title(self, soup, html_text):
        """Extract clean product title"""
        # Try multiple sources
        title_selectors = [
            'meta[property="og:title"]',
            'meta[name="title"]',
            'title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get('content') or element.get_text()
                if title:
                    return clean_title(title)
        
        # Try JSON-LD
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get('@type') == 'Product':
                    return clean_title(data.get('name', ''))
            except:
                continue
        
        return "Product Title"
    
    def _extract_price(self, soup, html_text):
        """Extract product price"""
        # Try JSON-LD first
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, list):
                        offers = offers[0]
                    price = offers.get('price')
                    if price:
                        return str(int(float(price)))
            except:
                continue
        
        # Try meta tags
        price_selectors = [
            'meta[property="product:price:amount"]',
            'meta[name="twitter:data1"]'
        ]
        
        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price = element.get('content')
                if price:
                    try:
                        return str(int(float(price)))
                    except:
                        continue
        
        # Try text-based extraction
        price = extract_price(html_text)
        if price:
            return price
        
        return "0"
    
    def _detect_platform(self, url):
        """Detect e-commerce platform"""
        url_lower = url.lower()
        if 'meesho.com' in url_lower:
            return 'meesho'
        elif 'amazon.in' in url_lower:
            return 'amazon'
        elif 'flipkart.com' in url_lower:
            return 'flipkart'
        elif 'myntra.com' in url_lower:
            return 'myntra'
        elif 'ajio.com' in url_lower:
            return 'ajio'
        elif 'snapdeal.com' in url_lower:
            return 'snapdeal'
        elif 'wishlink.com' in url_lower:
            return 'wishlink'
        return 'unknown'
    
    def _extract_pin(self, message_text):
        """Extract pin code from message"""
        from utils import extract_pin_code
        pin = extract_pin_code(message_text)
        return pin if pin else DEFAULT_PIN
    
    def _extract_sizes(self, soup, url):
        """Extract available sizes (Meesho specific)"""
        if 'meesho.com' not in url.lower():
            return None
        
        # Common size selectors for Meesho
        size_selectors = [
            '.size-selector', '.size-chip', '[data-testid="size-chip"]'
        ]
        
        for selector in size_selectors:
            elements = soup.select(selector)
            if elements:
                sizes = []
                for el in elements:
                    size_text = el.get_text().strip().upper()
                    if size_text and any(size in size_text for size in ['S', 'M', 'L', 'XL', 'XXL', 'FREE']):
                        sizes.append(size_text)
                
                if sizes:
                    # If all common sizes are available, return "All"
                    if len(sizes) >= 5:
                        return "All"
                    return ', '.join(list(set(sizes)))
        
        return "All"  # Default assumption for Meesho
