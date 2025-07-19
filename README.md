# Ecommerce Content Analyzer

A Proof of Concept (POC) web application that analyzes ecommerce buyers guide content and extracts common keywords/phrases across multiple HTML files.

## Features

### Core Functionality
- **Multi-file Upload**: Upload 2 or more HTML files for analysis
- **HTML Processing**: Automatically removes HTML tags and cleans text content
- **Smart Tokenization**: Extracts 1, 2, and 3-word phrases from content
- **Ecommerce Keyword Filtering**: Filters for transactional and product search keywords
- **Intersection Analysis**: Finds keywords that appear in ALL uploaded files
- **Detailed Reporting**: Comprehensive analysis with file-by-file breakdown
- **AI-Powered SEO Analysis**: OpenAI integration for keyword SEO value assessment

### Technical Features
- **Flask Web Framework**: Python-based backend with RESTful API
- **CSRF Protection**: Secure form handling with CSRF tokens
- **Bootstrap UI**: Modern, responsive design with clean styling
- **JSON Storage**: All analysis results saved as JSON files
- **Export Options**: Download results as CSV or JSON
- **Drag & Drop**: Intuitive file upload interface
- **OpenAI Integration**: GPT-3.5-turbo for intelligent SEO analysis

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Setup Instructions

1. **Clone or download the project**
   ```bash
   cd dynEcomApp2
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables**
   Create a `.env` file in the project root with:
   ```bash
   # OpenAI API Configuration (required for SEO analysis)
   OPENAI_API_KEY=your_openai_api_key_here
   
   # Flask Configuration (optional)
   SECRET_KEY=your-secret-key-change-this-in-production
   ```
   
   **Note**: You'll need an OpenAI API key for the SEO analysis feature. Get one at [OpenAI Platform](https://platform.openai.com/api-keys).

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   Open your browser and navigate to `http://localhost:5000`

## Usage

### Step 1: Upload Files
1. Navigate to the "Analyze" page
2. Upload 2 or more HTML files containing ecommerce buyers guides
3. Use drag & drop or click to browse
4. Files must be HTML format (.html or .htm)

### Step 2: Analysis Process
The system automatically:
- Removes HTML tags and cleans text
- Tokenizes content into 1, 2, and 3-word phrases
- Filters for ecommerce-related keywords
- Finds keywords common to all files

### Step 3: View Results
- See summary statistics (files processed, keywords found)
- View common keywords with export options
- Examine detailed file-by-file breakdown
- Download results in CSV or JSON format

### Step 4: SEO Analysis (Optional)
- Click "Analyze SEO Value" button on results page
- Enter a product title for context
- Get AI-powered SEO analysis categorizing keywords by value
- Copy or export the SEO analysis results

## Keyword Categories

### Transactional Keywords
Words related to purchasing, payment, and shopping behavior:
- buy, purchase, order, checkout, cart, shopping
- price, cost, discount, sale, deal, offer
- shipping, delivery, return, refund, warranty
- payment, credit card, paypal, secure

### Product Search Keywords
Words related to product features, quality, and search intent:
- best, top, recommended, popular, trending
- quality, durable, reliable, efficient
- affordable, budget, luxury, premium
- smart, digital, wireless, portable

## API Endpoints

### GET /api/keywords
Returns current ecommerce keyword database.

### POST /api/keywords
Add new keywords to the database.
```json
{
  "category": "transactional",
  "keywords": ["new_keyword1", "new_keyword2"]
}
```

## File Structure

```
dynEcomApp2/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/            # HTML templates
│   ├── base.html         # Base template with layout
│   ├── index.html        # Home page
│   ├── upload.html       # File upload page
│   ├── results.html      # Analysis results page
│   └── seo_analysis.html # SEO analysis page
├── uploads/              # Temporary file storage
├── data/                 # Analysis results storage
└── samples/              # Sample HTML files for testing
```

## Configuration

### Environment Variables
- `OPENAI_API_KEY`: OpenAI API key for SEO analysis (required for SEO feature)
- `SECRET_KEY`: Flask secret key for CSRF protection (default: auto-generated)

### File Limits
- Maximum file size: 16MB per file
- Supported formats: HTML (.html, .htm)

## Sample Data

The `samples/` directory contains example HTML files for testing:
- `sample_guide_1.html`: Basic ecommerce product guide
- `sample_guide_2.html`: Comparison shopping guide
- `sample_guide_3.html`: Buyer's guide with features

## Improvements and Suggestions

### Potential Enhancements
1. **Keyword Management**: Web interface to add/edit keyword categories
2. **Advanced Filtering**: Custom keyword lists and exclusion rules
3. **Text Analysis**: Sentiment analysis and keyword importance scoring
4. **Database Integration**: Replace JSON storage with proper database
5. **User Authentication**: Multi-user support with analysis history
6. **API Rate Limiting**: Protect against abuse
7. **File Validation**: Better HTML validation and error handling
8. **Progress Indicators**: Real-time analysis progress
9. **Keyword Clustering**: Group similar keywords together
10. **Export Formats**: Additional export options (Excel, PDF)

### Technical Improvements
1. **Async Processing**: Use Celery for background processing
2. **Caching**: Redis for improved performance
3. **Logging**: Comprehensive logging system
4. **Testing**: Unit and integration tests
5. **Docker**: Containerization for easy deployment
6. **CI/CD**: Automated testing and deployment

## Troubleshooting

### Common Issues

1. **NLTK Data Not Found**
   ```
   LookupError: Resource punkt not found
   ```
   Solution: The app automatically downloads required NLTK data on first run.

2. **File Upload Errors**
   - Ensure files are HTML format
   - Check file size (max 16MB)
   - Verify file encoding (UTF-8 recommended)

3. **No Keywords Found**
   - Check if files contain ecommerce-related content
   - Consider expanding the keyword database
   - Verify HTML structure is parseable

### Performance Tips
- Use smaller HTML files for faster processing
- Ensure HTML files are well-formed
- Close browser tabs with large file uploads

## License

This is a POC application. Feel free to modify and extend for your needs.

## Support

For issues or questions, please check the troubleshooting section above or review the code comments for implementation details. 