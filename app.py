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
        
        # Extract main content - focus on common content areas
        main_content = ""
        
        # Try to find main content areas
        content_selectors = [
            'main',
            'article',
            '[role="main"]',
            '.content',
            '.main-content',
            '#content',
            '#main',
            '.post-content',
            '.entry-content',
            '.article-content'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                main_content = content_elem.get_text()
                break
        
        # If no main content found, use body content but exclude navigation, footer, etc.
        if not main_content:
            # Remove navigation, header, footer, sidebar elements
            for elem in soup(['nav', 'header', 'footer', 'aside', '.sidebar', '.navigation', '.menu']):
                elem.decompose()
            
            body = soup.find('body')
            if body:
                main_content = body.get_text()
            else:
                main_content = soup.get_text()
        
        # Clean the content
        clean_text = clean_html(main_content)
        
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

def tokenize_text(text, max_ngram=3):
    """Tokenize text into 1, 2, and 3 word phrases with filtering"""
    # Clean and normalize text
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    words = word_tokenize(text)
    
    # Filter out common stop words, single letters, and short words
    stop_words = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he', 
        'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'will', 'with',
        'i', 'you', 'your', 'we', 'they', 'them', 'this', 'these', 'those', 'or', 'but',
        'if', 'then', 'else', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now','add cart','account',
        'com','login','order','price','checkout','cart','shopping','shop','store','price','cost','discount',
        'item','items','product','products','category','categories','brand','brands','search','search for','search for',
        'currently','available','add to cart','add to cart','add to cart','add to cart','add to cart','add to cart','add to cart',
        'shipping','delivery','free shipping','return','refund','warranty','guarantee','secure','payment','credit card','paypal',
        'please','please click','please click here','please click here to','please click here to','please click here to','please click here to',
        'order now','order now','order now','order now','order now','order now','order now','order now','order now','order now','order now','order now',
        'returns','policy','terms','conditions','privacy','policy','terms','conditions','privacy','policy','terms','conditions','privacy','policy','terms','conditions','privacy',
        'view','view all','view more','view details','view product','view products','view category','view categories','view brand','view brands','view search','view search for','view search for',
        'reorder','edit','reviews','see','per','use','with','within','inc','log','must','ordered','option','yes','no','also','cancel','password','create','get'
    }
    
    # Filter words: remove stop words, single letters, and words shorter than 3 characters
    filtered_words = [
        word for word in words 
        if word not in stop_words 
        and len(word) >= 3 
        and not word.isdigit()
    ]
    
    tokens = {}
    
    # Add single words (already filtered)
    for word in filtered_words:
        tokens[word] = tokens.get(word, 0) + 1
    
    # Add bigrams and trigrams (only if all words in the n-gram meet criteria)
    for n in range(2, min(max_ngram + 1, len(filtered_words) + 1)):
        n_grams = list(ngrams(filtered_words, n))
        for gram in n_grams:
            # Only add n-grams where all words are valid
            if all(len(word) >= 3 and word not in stop_words for word in gram):
                phrase = ' '.join(gram)
                tokens[phrase] = tokens.get(phrase, 0) + 1
    
    return tokens

def find_common_keywords(file_keywords_list):
    """Find keywords that appear in all files with frequency tracking"""
    if not file_keywords_list:
        return []
    
    # Get all unique keywords that appear in at least one file
    all_keywords = set()
    for keywords_dict in file_keywords_list:
        all_keywords.update(keywords_dict.keys())
    
    # Calculate total frequency for each keyword across all files
    keyword_frequency = {}
    for keyword in all_keywords:
        total_freq = sum(keywords_dict.get(keyword, 0) for keywords_dict in file_keywords_list)
        keyword_frequency[keyword] = total_freq
    
    # Filter keywords with frequency 2 and higher
    filtered_keywords = {kw: freq for kw, freq in keyword_frequency.items() if freq >= 5}
    
    # Sort by frequency (descending) and then alphabetically
    sorted_keywords = sorted(
        filtered_keywords.items(), 
        key=lambda x: (-x[1], x[0].lower())
    )
    
    return sorted_keywords

def save_analysis_result(analysis_id, urls_data, common_keywords):
    """Save analysis results to JSON file"""
    # Convert common_keywords from list of tuples to list of dicts for JSON serialization
    keyword_list = [{'keyword': kw, 'frequency': freq} for kw, freq in common_keywords]
    
    result = {
        'analysis_id': analysis_id,
        'timestamp': datetime.now().isoformat(),
        'urls_processed': len(urls_data),
        'urls': [data['url'] for data in urls_data],
        'common_keywords': keyword_list,
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
    
    # Convert - item to <li>item</li>
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    
    # Wrap consecutive <li> elements in <ul>
    html = re.sub(r'(<li>.*?</li>)+', lambda m: f'<ul>{m.group(0)}</ul>', html, flags=re.DOTALL)
    
    # Remove extra blank lines and normalize spacing
    html = re.sub(r'\n\s*\n', '\n', html)  # Remove multiple consecutive newlines
    
    # Split into lines and process
    lines = html.split('\n')
    processed_lines = []
    
    for line in lines:
        line = line.strip()
        if line:
            # If it's a header (starts with <strong>), add it as a paragraph
            if line.startswith('<strong>'):
                processed_lines.append(f'<p class="seo-header">{line}</p>')
            # If it's a list, add it as is
            elif line.startswith('<ul>') or line.startswith('<li>') or line.startswith('</ul>'):
                processed_lines.append(line)
            # Otherwise, skip empty lines
            elif line:
                processed_lines.append(line)
    
    # Join with minimal spacing
    html = ''.join(processed_lines)
    
    return html

def analyze_keywords_with_openai(keywords_list, product_title):
    """Analyze keywords with OpenAI for SEO value"""
    try:
        # Prepare the keywords list
        keywords_text = ', '.join([kw['keyword'] for kw in keywords_list[:50]])  # Limit to top 50 keywords
        
        # Create the prompt
        prompt = f"""Identify the SEO value keywords from this list as it relates to: {product_title}

Keywords: {keywords_text}

Output two category lists in markdown format:
**High SEO Value (Strong Relevance + Buyer Intent)**
- List keywords here

**Medium SEO Value (Supporting Modifiers or Adjacent Terms)**
- List keywords here

Please analyze each keyword for its SEO potential and categorize accordingly."""

        # Create OpenAI client
        client = OpenAI()
        
        # Call OpenAI API using the new format
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an SEO expert specializing in ecommerce keyword analysis. Provide clear, actionable insights about keyword SEO value."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        # Convert markdown to HTML before returning
        markdown_content = completion.choices[0].message.content.strip()
        return markdown_to_html(markdown_content)
        
    except Exception as e:
        return f"Error analyzing keywords: {str(e)}"

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
            
            if len(urls) > 3:
                flash('Maximum 3 URLs allowed for analysis', 'error')
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