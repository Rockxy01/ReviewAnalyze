from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import pandas as pd
from fake_useragent import UserAgent
import time
import random
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from textblob import TextBlob
from collections import defaultdict
import urllib.parse
import base64
import logging
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

class AmazonReviewAnalyzer:
    def __init__(self):
        self.ua = UserAgent()
        self.driver = None

    def setup_selenium(self, retries=3):
    """Initialize Selenium WebDriver with appropriate options"""
    for attempt in range(retries):
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument(f'user-agent={self.ua.random}')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Set binary location for Render environment
            if os.environ.get('IS_RENDER'):
                logger.info("Running in Render environment")
                chrome_options.binary_location = '/usr/bin/google-chrome-stable'
                service = Service('/usr/bin/chromedriver')
            else:
                logger.info("Running in local environment")
                service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("Selenium WebDriver initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up Selenium (attempt {attempt+1}/{retries}): {e}")
            # Log more detailed error information
            logger.error(f"Full error details: {str(e)}")
            if attempt < retries - 1:  # Only sleep if we're going to retry
                time.sleep(2)  # Wait before retrying
    
    logger.error("Failed to initialize Selenium after all attempts")
    return False

    def get_product_image(self, url):
        """Fetch the product image URL using Selenium"""
        try:
            if not self.driver:
                success = self.setup_selenium()
                if not success:
                    return None

            self.driver.get(url)
            time.sleep(2)  # Wait for page to load
            
            image_selectors = [
                (By.ID, "landingImage"),
                (By.ID, "imgBlkFront"),
                (By.ID, "main-image"),
                (By.CSS_SELECTOR, "#main-image-container img"),
                (By.CSS_SELECTOR, "#imageBlock_feature_div img"),
                (By.CSS_SELECTOR, ".a-dynamic-image")
            ]
            
            img_element = None
            for selector_type, selector in image_selectors:
                try:
                    img_element = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((selector_type, selector))
                    )
                    if img_element:
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} not found: {e}")
                    continue
            
            if img_element:
                img_url = img_element.get_attribute('src')
                if img_url:
                    headers = {'User-Agent': self.ua.random}
                    response = requests.get(img_url, headers=headers)
                    if response.status_code == 200:
                        img_base64 = base64.b64encode(response.content).decode('utf-8')
                        return img_base64
            
            logger.warning("No product image found")
            return None
        except Exception as e:
            logger.error(f"Error fetching product image: {e}")
            return None

    def analyze_sentiment(self, text):
            """Analyze sentiment of text using TextBlob"""
            try:
                text = text.strip()  # Remove leading/trailing whitespace
                if not text:
                    return 'Neutral'  # Empty text is neutral
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity
                return 'Positive' if polarity > 0.1 else 'Negative' if polarity < -0.1 else 'Neutral'
            except Exception as e:
                logger.error(f"Error in sentiment analysis: {e}")
                return 'Neutral'
            
    def clean_url(self, url):
        """Extract domain and ASIN from Amazon URL"""
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc
        path_parts = parsed_url.path.strip('/').split('/')
        
        if len(path_parts) > 1 and path_parts[0] == 'dp':
            asin = path_parts[1]
        elif len(path_parts) > 0 and path_parts[0] in ['product-reviews', 'gp/product']:
            asin = urllib.parse.parse_qs(parsed_url.query)['ASIN'][0] if 'ASIN' in urllib.parse.parse_qs(parsed_url.query) else None
        else:
            asin = None
        
        return domain, asin 
            
    def fetch_reviews_selenium(self, url, num_pages=15):
        """Fetch reviews using Selenium with international domain support"""
        reviews = []
        try:
            review_url = url.replace("/dp/", "/product-reviews/")

            for page in range(1, num_pages + 1):
                try:
                    page_url = f"{review_url}?pageNumber={page}"
                    self.driver.get(page_url)

                    # Wait for reviews to load
                    WebDriverWait(self.driver, 20).until(  # Increased timeout
                        EC.presence_of_element_located((By.CLASS_NAME, "review"))
                    )

                    review_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-hook="review"]')

                    for review in review_elements:
                        try:
                            review_text = review.find_element(By.CSS_SELECTOR, 'span[data-hook="review-body"]').text.strip()
                            rating_element = review.find_element(By.CSS_SELECTOR, 'i[data-hook="review-star-rating"], i[data-hook="cmps-review-star-rating"]')
                            rating_text = rating_element.get_attribute('textContent')
                            rating = float(rating_text.split(' ')[0])

                            review_data = {
                                'text': review_text,
                                'rating': rating,
                                'sentiment': self.analyze_sentiment(review_text)
                            }
                            reviews.append(review_data)
                        except Exception as e:
                            logger.debug(f"Error parsing review: {e}")
                            continue

                    logger.info(f"Fetched page {page} - Found {len(review_elements)} reviews")

                except Exception as e:
                    logger.error(f"Error fetching page {page}: {e}")
                    break

        except Exception as e:
            logger.error(f"Error: {e}")

        return reviews
    
    def generate_summary(self, reviews, url):
        """Generate a detailed narrative summary based on in-depth review analysis"""
        if not reviews:
            return "No reviews found for analysis."

        try:
            domain, asin = self.clean_url(url)
            self.driver.get(url)
            product_title = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "productTitle"))
            ).text.strip()
        except:
            product_title = "Product"

        df = pd.DataFrame(reviews)

        total_reviews = len(df)
        avg_rating = df['rating'].mean()

        # Get detailed reviews (longer than 200 characters)
        detailed_reviews = [r for r in reviews if len(r['text']) > 200]
        positive_reviews = [r for r in detailed_reviews if r['sentiment'] == 'Positive']
        negative_reviews = [r for r in detailed_reviews if r['sentiment'] == 'Negative']
        neutral_reviews = [r for r in detailed_reviews if r['sentiment'] == 'Neutral']

        # Calculate percentages
        positive_percent = (len([r for r in reviews if r['sentiment'] == 'Positive']) / total_reviews) * 100
        negative_percent = (len([r for r in reviews if r['sentiment'] == 'Negative']) / total_reviews) * 100

        # Analyze common themes in detailed reviews
        def extract_themes(review_list):
            themes = defaultdict(list)
            common_aspects = {
                'quality': ['quality', 'build', 'material', 'durability', 'construction'],
                'value': ['price', 'value', 'worth', 'cost', 'expensive', 'cheap'],
                'performance': ['performance', 'speed', 'fast', 'slow', 'efficient'],
                'features': ['feature', 'functionality', 'options', 'capabilities'],
                'design': ['design', 'look', 'aesthetic', 'style', 'appearance'],
                'usability': ['easy', 'simple', 'intuitive', 'user-friendly', 'difficult'],
                'reliability': ['reliable', 'consistent', 'stable', 'issues', 'problems'],
                'support': ['support', 'customer service', 'warranty', 'help']
            }

            for review in review_list:
                text = review['text'].lower()
                for aspect, keywords in common_aspects.items():
                    if any(keyword in text for keyword in keywords):
                        # Find complete sentences containing the keyword
                        sentences = text.split('.')
                        relevant_sentences = [s.strip() for s in sentences if any(keyword in s for keyword in keywords) and s.strip()]
                        if relevant_sentences:
                            themes[aspect].append(relevant_sentences[0])  # Store the first relevant complete sentence
            return themes

        positive_themes = extract_themes(positive_reviews)
        negative_themes = extract_themes(negative_reviews)

        # Generate the comprehensive summary
        sentiment_desc = "mixed reviews"
        if positive_percent >= 80:
            sentiment_desc = "overwhelmingly positive reviews"
        elif positive_percent >= 70:
            sentiment_desc = "largely positive reviews"
        elif positive_percent >= 60:
            sentiment_desc = "generally positive reviews"
        elif negative_percent >= 60:
            sentiment_desc = "generally negative reviews"

        # Create the main summary paragraph
        summary = f"Based on a detailed analysis of {total_reviews} customer reviews, the {product_title} has received {sentiment_desc} with an average rating of {avg_rating:.1f} out of 5 stars. "

        # Add positive aspects with specific examples
        if positive_themes:
            summary += "The standout features praised by customers include "
            positive_points = []
            for aspect, comments in positive_themes.items():
                if comments:
                    example = max(comments, key=len)  # Get the most detailed comment
                    positive_points.append(f"the {aspect} ({example})")

            if positive_points:
                summary += ", ".join(positive_points[:-1])
                if len(positive_points) > 1:
                    summary += f", and {positive_points[-1]}"
                else:
                    summary += positive_points[0]
                summary += ". "

        # Add balanced perspective from neutral reviews
        if neutral_reviews:
            balanced_opinion = max(neutral_reviews, key=lambda x: len(x['text']))
            summary += f"A balanced perspective from users notes that {balanced_opinion['text'][:150]}... "
    
        # Add constructive criticism with specific examples
        if negative_themes:
            summary += "However, some users have expressed concerns about "
            negative_points = []
            for aspect, comments in negative_themes.items():
                if comments:
                    example = max(comments, key=len)  # Get the most detailed comment
                    negative_points.append(f"the {aspect} ({example})")

            if negative_points:
                summary += ", ".join(negative_points[:-1])
                if len(negative_points) > 1:
                    summary += f", and {negative_points[-1]}"
                else:
                    summary += negative_points[0]
                summary += ". "

        # Add final recommendation
        if avg_rating >= 4.0 and positive_percent >= 70:
            summary += "Given the substantial positive feedback and high average rating, this product comes highly recommended by the majority of users, particularly for those valuing "
            summary += " and ".join(list(positive_themes.keys())[:2]) + "."
        elif avg_rating >= 3.5 and positive_percent >= 60:
            summary += "While most users are satisfied with their purchase, potential buyers should weigh the praised aspects against the reported limitations to ensure it meets their specific needs."
        else:
            summary += "Given the mixed feedback, potential buyers should carefully consider these varied experiences and whether the reported issues might affect their intended use of the product."

        return summary

    def analyze_url(self, url):
        """Main function to analyze product reviews from URL"""
        logger.info(f"Starting analysis for URL: {url}")
        try:
            if not self.driver:
                success = self.setup_selenium()
                if not success:
                    return {"error": "Failed to initialize WebDriver"}

            logger.info("Fetching product image")
            product_image = self.get_product_image(url)
            
            logger.info("Fetching reviews")
            reviews = self.fetch_reviews_selenium(url, num_pages=15)

            logger.info("Generating summary")
            summary = self.generate_summary(reviews, url)

            return {
                "summary": summary,
                "image": product_image,
                "total_reviews": len(reviews),
                "average_rating": sum([r['rating'] for r in reviews]) / len(reviews) if reviews else None
            }

        except Exception as e:
            logger.error(f"Error in analyze_url: {e}")
            return {"error": str(e)}
        finally:
            try:
                if self.driver:
                    self.driver.quit()
                    self.driver = None
                    logger.info("WebDriver closed successfully")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
        
@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error loading template: {e}")
        return f"Error loading template: {str(e)}", 500

@app.route('/analyze', methods=['POST'])
def analyze():
    logger.info("Received analyze request")
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'})
        
        url = data['url']
        if not url or 'amazon' not in url.lower():
            return jsonify({'error': 'Please enter a valid Amazon URL'})
        
        logger.info(f"Analyzing URL: {url}")
        analyzer = AmazonReviewAnalyzer()
        result = analyzer.analyze_url(url)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in /analyze endpoint: {e}")
        return jsonify({'error': f'An error occurred: {str(e)}'})

if __name__ == "__main__":
    app.run(debug=True, port=5500)
