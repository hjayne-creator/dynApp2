import os
import json
import re
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
import nltk
from nltk.tokenize import word_tokenize
from nltk.util import ngrams
from collections import Counter
import uuid
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import requests
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Initialize OpenAI client (will automatically use OPENAI_API_KEY from environment)
client = OpenAI()

# Browser headers for web scraping
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'seo2025')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour
app.config['WTF_CSRF_SSL_STRICT'] = False  # Allow HTTP in development
csrf = CSRFProtect(app)

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

def crawl_url(url):
    """Crawl a URL and extract content with SEO metadata"""
    try:
        # Validate URL format
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return None, f"Invalid URL format: {url}"
        
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Make request with browser headers and timeout
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
        response.raise_for_status()
        
        # Parse HTML content
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Extract SEO metadata
        meta_title = ""
        meta_description = ""
        
        title_tag = soup.find('title')
        if title_tag:
            meta_title = title_tag.get_text().strip()
        
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        if meta_desc_tag:
            meta_description = meta_desc_tag.get('content', '').strip()
        
        # Extract ecommerce-specific content with weighted importance
        ecommerce_content = extract_ecommerce_content(soup)
        
        # Build prioritized content string with weighted repetition for importance
        weighted_content = []
        
        # Product title (weight: 3x) - most important for SEO
        if ecommerce_content['product_title']:
            weighted_content.extend([ecommerce_content['product_title']] * 3)
        
        # Product description (weight: 2x) - very important
        if ecommerce_content['description']:
            weighted_content.extend([ecommerce_content['description']] * 2)
        
        # Specifications (weight: 2x) - contains key product attributes
        if ecommerce_content['specifications']:
            weighted_content.extend([ecommerce_content['specifications']] * 2)
        
        # Breadcrumbs (weight: 1x) - category context
        if ecommerce_content['breadcrumbs']:
            weighted_content.append(ecommerce_content['breadcrumbs'])
        
        # Reviews (weight: 1x) - customer language
        if ecommerce_content['reviews']:
            weighted_content.append(ecommerce_content['reviews'])
        
        # Price info (weight: 1x) - less important for keyword extraction
        if ecommerce_content['price_info']:
            weighted_content.append(ecommerce_content['price_info'])
        
        # Fallback to generic content extraction if no ecommerce content found
        if not any(ecommerce_content.values()):
            # Try to find main content areas
            content_selectors = [
                'main', 'article', '[role="main"]', '.content', '.main-content',
                '#content', '#main', '.post-content', '.entry-content', '.article-content'
            ]
            
            main_content = ""
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    main_content = content_elem.get_text()
                    break
            
            if not main_content:
                # Remove navigation, header, footer, sidebar elements
                for elem in soup(['nav', 'header', 'footer', 'aside', '.sidebar', '.navigation', '.menu']):
                    elem.decompose()
                
                body = soup.find('body')
                if body:
                    main_content = body.get_text()
                else:
                    main_content = soup.get_text()
            
            weighted_content.append(main_content)
        
        # Combine all weighted content
        combined_content = ' '.join(weighted_content)
        clean_text = clean_html(combined_content)
        
        return {
            'url': url,
            'title': meta_title,
            'description': meta_description,
            'content': clean_text,
            'status': 'success'
        }, None
        
    except requests.exceptions.Timeout:
        return None, f"Timeout error for {url}"
    except requests.exceptions.RequestException as e:
        return None, f"Request error for {url}: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error for {url}: {str(e)}"

def clean_html(text):
    """Remove HTML tags and clean text"""
    soup = BeautifulSoup(text, 'html.parser')
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    # Get text and clean up whitespace
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    return text

def tokenize_text(text, max_ngram=4):
    """Tokenize text into 1-4 word phrases with ecommerce-optimized filtering"""
    # Clean and normalize text
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    words = word_tokenize(text)
    
    # Refined stop words - removed some ecommerce-valuable terms, added more noise words
    stop_words = {
        # Basic stop words
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he', 
        'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'will', 'with',
        'i', 'you', 'your', 'we', 'they', 'them', 'this', 'these', 'those', 'or', 'but',
        'if', 'then', 'else', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now',
        
        # Generic ecommerce noise (keep valuable terms like "product", "price", "quality")
        'account', 'com', 'login', 'checkout', 'cart', 'currently', 'available',
        'please', 'click', 'here', 'view', 'see', 'per', 'use', 'within', 'inc', 
        'log', 'must', 'option', 'yes', 'no', 'also', 'cancel', 'password', 'create', 
        'get', 'canceled', 'submitted', 'sign', 'up', 'register', 'login', 'logout',
        
        # Website navigation noise
        'home', 'page', 'next', 'previous', 'back', 'top', 'bottom', 'menu', 'link',
        'button', 'tab', 'section', 'content', 'main', 'sidebar', 'footer', 'header',
        
        # Generic action words without product context
        'read', 'learn', 'find', 'discover', 'explore', 'browse', 'visit', 'contact',
        'about', 'help', 'support', 'faq', 'terms', 'privacy', 'policy', 'legal'
    }
    
    # Ecommerce-valuable terms to preserve (remove from stop words if present)
    preserve_terms = {
        'product', 'products', 'price', 'prices', 'cost', 'quality', 'brand', 'brands',
        'shipping', 'delivery', 'return', 'returns', 'warranty', 'guarantee',
        'review', 'reviews', 'rating', 'ratings', 'customer', 'customers',
        'sale', 'discount', 'offer', 'deal', 'promotion', 'free', 'premium',
        'size', 'sizes', 'color', 'colors', 'style', 'styles', 'model', 'models',
        'material', 'materials', 'feature', 'features', 'specification', 'specs'
    }
    
    # Update stop words by removing preserve terms
    stop_words = stop_words - preserve_terms
    
    # Filter words with improved criteria
    filtered_words = []
    for word in words:
        if (word not in stop_words and 
            len(word) >= 2 and  # Allow 2-letter words for sizes, models, etc.
            not word.isdigit() and
            not (len(word) == 2 and word not in ['xs', 'sm', 'md', 'lg', 'xl', 'os']) and  # Allow size abbreviations
            word.isalpha()):  # Only alphabetic characters
            filtered_words.append(word)
    
    tokens = {}
    
    # Add single words
    for word in filtered_words:
        if len(word) >= 3 or word in preserve_terms:  # Allow shorter preserve terms
            tokens[word] = tokens.get(word, 0) + 1
    
    # Add n-grams with improved validation
    for n in range(2, min(max_ngram + 1, len(filtered_words) + 1)):
        n_grams = list(ngrams(filtered_words, n))
        for gram in n_grams:
            # More lenient n-gram filtering for ecommerce phrases
            if (len(gram) > 1 and
                not all(word in stop_words for word in gram) and  # Not all stop words
                not any(len(word) < 2 for word in gram) and  # No single characters
                any(word in preserve_terms or len(word) >= 3 for word in gram)):  # At least one meaningful word
                
                phrase = ' '.join(gram)
                # Skip overly generic phrases
                if not phrase.startswith(('the ', 'a ', 'an ')) and not phrase.endswith((' the', ' a', ' an')):
                    tokens[phrase] = tokens.get(phrase, 0) + 1
    
    return tokens

def find_common_keywords(file_keywords_list):
    """Find keywords with strategic frequency and coverage analysis for competitive research"""
    if not file_keywords_list:
        return []
    
    num_files = len(file_keywords_list)
    
    # Get all unique keywords that appear in at least one file
    all_keywords = set()
    for keywords_dict in file_keywords_list:
        all_keywords.update(keywords_dict.keys())
    
    # Calculate metrics for each keyword
    keyword_metrics = {}
    for keyword in all_keywords:
        # Count how many files contain this keyword
        files_containing = sum(1 for keywords_dict in file_keywords_list if keyword in keywords_dict)
        
        # Calculate total frequency across all files
        total_freq = sum(keywords_dict.get(keyword, 0) for keywords_dict in file_keywords_list)
        
        # Calculate average frequency per file that contains it
        avg_freq = total_freq / files_containing if files_containing > 0 else 0
        
        # Calculate coverage percentage
        coverage = files_containing / num_files
        
        keyword_metrics[keyword] = {
            'total_frequency': total_freq,
            'files_containing': files_containing,
            'coverage': coverage,
            'avg_frequency': avg_freq
        }
    
    # Multi-tier filtering strategy for competitive analysis
    # Adaptive thresholds based on number of URLs
    strategic_keywords = {}
    
    # Calculate adaptive thresholds
    min_files_for_majority = max(2, int(num_files * 0.5))  # At least 50% but minimum 2 files
    min_files_for_partial = max(1, int(num_files * 0.33))  # At least 33% but minimum 1 file
    
    # Ensure different thresholds for better tier separation
    if min_files_for_majority == min_files_for_partial and num_files >= 3:
        min_files_for_partial = min_files_for_majority - 1
    
    for keyword, metrics in keyword_metrics.items():
        # Tier 1: Keywords in ALL files (highest priority)
        if metrics['coverage'] == 1.0 and metrics['total_frequency'] >= 2:
            strategic_keywords[keyword] = metrics['total_frequency'] + 1000  # Boost score
        
        # Tier 2: Keywords in majority of files (50%+) with decent frequency
        elif metrics['files_containing'] >= min_files_for_majority and metrics['total_frequency'] >= 3:
            strategic_keywords[keyword] = metrics['total_frequency'] + 500  # Medium boost
        
        # Tier 3: High-frequency keywords even if not in majority (competitive gaps)
        elif metrics['total_frequency'] >= max(4, num_files) and metrics['avg_frequency'] >= 1.5:
            strategic_keywords[keyword] = metrics['total_frequency'] + 200  # Small boost
        
        # Tier 4: Quality keywords with specific valuable patterns
        elif (metrics['files_containing'] >= min_files_for_partial and 
              metrics['total_frequency'] >= 2 and
              any(term in keyword.lower() for term in [
                  'premium', 'professional', 'advanced', 'pro', 'deluxe', 'luxury',
                  'organic', 'natural', 'eco', 'sustainable', 'biodegradable',
                  'wireless', 'bluetooth', 'smart', 'digital', 'electronic',
                  'waterproof', 'durable', 'lightweight', 'portable', 'compact',
                  'multi', 'ultra', 'super', 'extra', 'plus', 'max', 'high',
                  'quality', 'best', 'top', 'rated', 'popular', 'featured'
              ])):
            strategic_keywords[keyword] = metrics['total_frequency'] + 150  # Quality boost
        
        # Tier 5: General valuable keywords appearing in multiple URLs
        elif (metrics['files_containing'] >= min_files_for_partial and 
              metrics['total_frequency'] >= 3 and
              metrics['avg_frequency'] >= 1.0):
            strategic_keywords[keyword] = metrics['total_frequency'] + 50  # Base boost
    
    # Sort by strategic score (descending) and then alphabetically
    sorted_keywords = sorted(
        strategic_keywords.items(), 
        key=lambda x: (-x[1], x[0].lower())
    )
    
    # Convert back to original format but include coverage info
    result = []
    for keyword, score in sorted_keywords:
        original_freq = keyword_metrics[keyword]['total_frequency']
        coverage = keyword_metrics[keyword]['coverage']
        files_count = keyword_metrics[keyword]['files_containing']
        
        result.append({
            'keyword': keyword,
            'frequency': original_freq,
            'coverage': coverage,
            'files_containing': files_count,
            'strategic_score': score
        })
    
    return result

def save_analysis_result(analysis_id, urls_data, common_keywords):
    """Save analysis results to JSON file"""
    # common_keywords is now a list of dicts with enhanced metadata
    
    result = {
        'analysis_id': analysis_id,
        'timestamp': datetime.now().isoformat(),
        'urls_processed': len(urls_data),
        'urls': [data['url'] for data in urls_data],
        'common_keywords': common_keywords,  # Already in correct format
        'keyword_count': len(common_keywords),
        'url_details': urls_data
    }
    
    filename = f'data/analysis_{analysis_id}.json'
    with open(filename, 'w') as f:
        json.dump(result, f, indent=2)
    
    return result

def markdown_to_html(markdown_text):
    """Convert simple markdown to HTML"""
    html = markdown_text
    
    # Convert **text** to <strong>text</strong>
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    
    # Convert markdown tables to HTML tables
    lines = html.split('\n')
    in_table = False
    table_lines = []
    processed_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Check if this is a table line (starts with |)
        if line.startswith('|') and line.endswith('|'):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
        else:
            # If we were in a table and now we're not, process the table
            if in_table:
                processed_lines.append(convert_markdown_table_to_html(table_lines))
                in_table = False
                table_lines = []
            
            # Process non-table lines
            if line:
                # Convert - item to <li>item</li>
                if line.startswith('- '):
                    processed_lines.append(f'<li>{line[2:]}</li>')
                # If it's a header (starts with <strong>), add it as a paragraph
                elif line.startswith('<strong>'):
                    processed_lines.append(f'<p class="seo-header">{line}</p>')
                # If it's a list, add it as is
                elif line.startswith('<ul>') or line.startswith('<li>') or line.startswith('</ul>'):
                    processed_lines.append(line)
                # Otherwise, add as regular paragraph
                else:
                    processed_lines.append(f'<p>{line}</p>')
    
    # Handle case where table is at the end
    if in_table:
        processed_lines.append(convert_markdown_table_to_html(table_lines))
    
    # Wrap consecutive <li> elements in <ul>
    html = ''.join(processed_lines)
    html = re.sub(r'(<li>.*?</li>)+', lambda m: f'<ul>{m.group(0)}</ul>', html, flags=re.DOTALL)
    
    return html

def convert_markdown_table_to_html(table_lines):
    """Convert markdown table to HTML table"""
    if len(table_lines) < 2:
        return ''.join(table_lines)
    
    html_table = ['<table class="table table-striped table-bordered">']
    
    for i, line in enumerate(table_lines):
        # Remove leading/trailing | and split by |
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        
        if i == 0:
            # Header row
            html_table.append('<thead><tr>')
            for cell in cells:
                html_table.append(f'<th>{cell}</th>')
            html_table.append('</tr></thead>')
        elif i == 1 and all(cell.startswith('-') and cell.endswith('-') for cell in cells):
            # Separator row, skip it
            continue
        else:
            # Data row
            html_table.append('<tr>')
            for cell in cells:
                html_table.append(f'<td>{cell}</td>')
            html_table.append('</tr>')
    
    html_table.append('</table>')
    return ''.join(html_table)

def analyze_keywords_with_openai(keywords_list, product_title):
    """Analyze keywords with OpenAI for ecommerce SEO value and competitive insights"""
    try:
        # Prepare the keywords with their strategic information
        top_keywords = keywords_list[:40]  # Analyze top 40 keywords
        
        # Create detailed keyword context
        keyword_details = []
        for kw in top_keywords:
            coverage_pct = round(kw.get('coverage', 0) * 100)
            strategic_score = kw.get('strategic_score', kw['frequency'])
            keyword_details.append(f"{kw['keyword']} (freq: {kw['frequency']}, coverage: {coverage_pct}%, score: {strategic_score})")
        
        keywords_context = '\n'.join(keyword_details)
        
        # Enhanced prompt for ecommerce competitive analysis
        prompt = f"""You are an expert ecommerce SEO analyst conducting competitive keyword research for product detail pages (PDPs). 

CONTEXT: These keywords were extracted from competitive product pages for a product related to: "{product_title}"

KEYWORDS DATA (frequency = total occurrences, coverage = % of competitors using it, score = strategic importance):
{keywords_context}

ANALYSIS TASK:
Analyze each keyword for ecommerce SEO value considering:

1. **Search Intent**: 
   - Commercial (product research/comparison)
   - Transactional (ready to buy)
   - Informational (learning about features)
   - Navigational (brand/specific product)

2. **SEO Opportunity**:
   - High: Strong search volume + commercial intent + optimization potential
   - Medium: Good search potential but competitive or niche
   - Low: Limited search volume or too generic

3. **Competitive Strategy**:
   - Universal (all competitors use - must-have)
   - Majority (most competitors - important)
   - Gap (few competitors - opportunity)
   - Unique (valuable differentiator)

4. **PDP Optimization Value**:
   - Product attributes (size, color, material, features)
   - Search modifiers (best, top, premium, affordable)
   - Long-tail variations (specific use cases)
   - Brand/quality indicators

Return ONLY a markdown table sorted by SEO Opportunity (High first), then by Strategic Value:

| Keyword/Phrase | Search Intent | SEO Opportunity | Competitive Strategy | PDP Usage | Strategic Reason |
|----------------|---------------|----------------|---------------------|-----------|------------------|
| example keyword | Commercial | High | Universal | Product Title | Core product identifier used by all competitors |

Focus on keywords most valuable for product page optimization and organic traffic acquisition."""

        # Call OpenAI API with improved settings
        completion = client.chat.completions.create(
            model="gpt-4o",  # Use latest model for better analysis
            messages=[
                {"role": "system", "content": "You are a senior ecommerce SEO strategist with expertise in competitive keyword analysis and product page optimization. Provide actionable insights for PDP optimization."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.3  # Lower temperature for more consistent analysis
        )
        
        # Convert markdown to HTML before returning
        markdown_content = completion.choices[0].message.content.strip()
        return markdown_to_html(markdown_content)
        
    except Exception as e:
        return f"Error analyzing keywords: {str(e)}"

def extract_ecommerce_content(soup):
    """Extract ecommerce-specific content with prioritized weighting"""
    content_sections = {}
    
    # Product title (highest priority)
    product_title = ""
    title_selectors = [
        'h1.product-title', 'h1[class*="product"]', 'h1[class*="title"]',
        '.product-name h1', '.product-title', '.pdp-product-name',
        'h1[data-testid*="product"]', '[data-automation-id*="product-title"]'
    ]
    
    for selector in title_selectors:
        title_elem = soup.select_one(selector)
        if title_elem:
            product_title = title_elem.get_text().strip()
            break
    
    if not product_title:
        # Fallback to any h1 that might be product title
        h1_tags = soup.find_all('h1')
        if h1_tags:
            product_title = h1_tags[0].get_text().strip()
    
    content_sections['product_title'] = product_title
    
    # Product description (high priority)
    description = ""
    desc_selectors = [
        '.product-description', '.product-details', '.pdp-description',
        '[class*="description"]', '[class*="details"]', '.product-info',
        '[data-testid*="description"]', '.product-overview'
    ]
    
    for selector in desc_selectors:
        desc_elem = soup.select_one(selector)
        if desc_elem:
            description = desc_elem.get_text().strip()
            break
    
    content_sections['description'] = description
    
    # Product specifications/features (high priority)
    specs = ""
    spec_selectors = [
        '.specifications', '.product-specs', '.features', '.product-features',
        '[class*="spec"]', '[class*="feature"]', '.attributes', '.product-attributes',
        '.tech-specs', '.product-details-table'
    ]
    
    for selector in spec_selectors:
        spec_elem = soup.select_one(selector)
        if spec_elem:
            specs = spec_elem.get_text().strip()
            break
    
    content_sections['specifications'] = specs
    
    # Product categories/breadcrumbs (medium priority)
    breadcrumbs = ""
    breadcrumb_selectors = [
        '.breadcrumb', '.breadcrumbs', 'nav[aria-label*="breadcrumb"]',
        '[class*="breadcrumb"]', '.navigation-path', '.category-path'
    ]
    
    for selector in breadcrumb_selectors:
        breadcrumb_elem = soup.select_one(selector)
        if breadcrumb_elem:
            breadcrumbs = breadcrumb_elem.get_text().strip()
            break
    
    content_sections['breadcrumbs'] = breadcrumbs
    
    # Product reviews snippets (medium priority)
    reviews = ""
    review_selectors = [
        '.reviews-summary', '.review-highlights', '.customer-reviews',
        '[class*="review"]', '.ratings-reviews', '.product-reviews'
    ]
    
    for selector in review_selectors:
        review_elem = soup.select_one(selector)
        if review_elem:
            # Get first few review highlights, not all reviews
            review_text = review_elem.get_text().strip()
            reviews = review_text[:500] + "..." if len(review_text) > 500 else review_text
            break
    
    content_sections['reviews'] = reviews
    
    # Price and availability info (low priority but useful)
    price_info = ""
    price_selectors = [
        '.price', '.product-price', '[class*="price"]', '.cost',
        '.pricing', '.price-current', '.sale-price'
    ]
    
    for selector in price_selectors:
        price_elem = soup.select_one(selector)
        if price_elem:
            price_info = price_elem.get_text().strip()
            break
    
    content_sections['price_info'] = price_info
    
    return content_sections

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint that doesn't require CSRF"""
    return jsonify({'status': 'healthy', 'message': 'Ecommerce Content Analyzer is running'})

@app.route('/crawl', methods=['GET', 'POST'])
def crawl():
    if request.method == 'POST':
        try:
            # Get URLs from form
            urls = []
            for i in range(1, 11):  # Support up to 10 URLs
                url = request.form.get(f'url_{i}', '').strip()
                if url:
                    urls.append(url)
            
            if len(urls) < 2:
                flash('Please provide at least 2 URLs for analysis', 'error')
                return redirect(request.url)
            
            if len(urls) > 6:
                flash('Maximum 6 URLs allowed for analysis', 'error')
                return redirect(request.url)
            
            # Crawl URLs
            urls_data = []
            url_keywords_list = []
            failed_urls = []
            
            for url in urls:
                crawl_result, error = crawl_url(url)
                
                if crawl_result:
                    # Combine content with SEO metadata for analysis
                    combined_content = crawl_result['content']
                    
                    # Add title if available
                    if crawl_result['title']:
                        combined_content = f"{crawl_result['title']}\n\n{combined_content}"
                    
                    # Add description if available
                    if crawl_result['description']:
                        combined_content = f"{crawl_result['description']}\n\n{combined_content}"
                    
                    # Process combined content
                    tokens = tokenize_text(combined_content)
                    
                    urls_data.append({
                        'url': url,
                        'title': crawl_result['title'],
                        'description': crawl_result['description'],
                        'total_tokens': sum(tokens.values()),
                        'filtered_keywords': dict(tokens),
                        'keyword_count': len(tokens.keys()),
                        'status': 'success'
                    })
                    
                    url_keywords_list.append(tokens)
                else:
                    failed_urls.append(f"{url}: {error}")
                    urls_data.append({
                        'url': url,
                        'title': '',
                        'description': '',
                        'total_tokens': 0,
                        'filtered_keywords': {},
                        'keyword_count': 0,
                        'status': 'failed',
                        'error': error
                    })
            
            # Check if we have enough successful URLs
            successful_urls = [data for data in urls_data if data['status'] == 'success']
            if len(successful_urls) < 2:
                flash(f'Not enough URLs could be crawled successfully. Failed URLs: {", ".join(failed_urls)}', 'error')
                return redirect(request.url)
            
            # Find common keywords from successful URLs only
            successful_keywords_list = [data['filtered_keywords'] for data in successful_urls]
            common_keywords = find_common_keywords(successful_keywords_list)
            
            # Generate analysis ID and save results
            analysis_id = str(uuid.uuid4())[:8]
            result = save_analysis_result(analysis_id, urls_data, common_keywords)
            
            success_message = f'Analysis completed! Found {len(common_keywords)} common keywords from {len(successful_urls)} URLs.'
            if failed_urls:
                success_message += f' Failed URLs: {", ".join(failed_urls)}'
            
            flash(success_message, 'success')
            return redirect(url_for('results', analysis_id=analysis_id))
            
        except Exception as e:
            flash(f'Error processing URLs: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('crawl.html')

@app.route('/results/<analysis_id>')
def results(analysis_id):
    try:
        with open(f'data/analysis_{analysis_id}.json', 'r') as f:
            result = json.load(f)
        return render_template('results.html', result=result)
    except FileNotFoundError:
        flash('Analysis not found', 'error')
        return redirect(url_for('index'))

@app.route('/seo-analysis/<analysis_id>', methods=['GET', 'POST'])
def seo_analysis(analysis_id):
    try:
        with open(f'data/analysis_{analysis_id}.json', 'r') as f:
            result = json.load(f)
        
        # Get default product title from first URL title or domain
        default_title = ""
        if result['urls']:
            # Try to get title from first successful URL
            first_url_data = next((data for data in result['url_details'] if data['status'] == 'success'), None)
            if first_url_data and first_url_data['title']:
                default_title = first_url_data['title']
            else:
                # Fallback to domain name
                from urllib.parse import urlparse
                parsed_url = urlparse(result['urls'][0])
                default_title = parsed_url.netloc.replace('www.', '').replace('.com', '').replace('.', ' ')
                default_title = ' '.join(word.capitalize() for word in default_title.split())
        
        if request.method == 'POST':
            product_title = request.form.get('product_title', '').strip()
            
            if not product_title:
                flash('Please enter a product title', 'error')
                return render_template('seo_analysis.html', result=result, default_title=default_title)
            
            # Analyze keywords with OpenAI
            seo_analysis_result = analyze_keywords_with_openai(result['common_keywords'], product_title)
            
            return render_template('seo_analysis.html', 
                                 result=result, 
                                 seo_analysis=seo_analysis_result,
                                 product_title=product_title,
                                 default_title=default_title)
        
        return render_template('seo_analysis.html', result=result, default_title=default_title)
        
    except FileNotFoundError:
        flash('Analysis not found', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True) 