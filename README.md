# 🍽️ Michelin Thailand Restaurant Scraper

A comprehensive web scraping tool for collecting detailed information about Michelin-starred and Bib Gourmand restaurants in Thailand from the official Michelin Guide website.

## 📋 Features

- **Two-stage scraping process:**
  - **Stage 1 (Global):** Scrapes restaurant listings with basic info (name, stars, location, price, cuisine)
  - **Stage 2 (Details):** Scrapes detailed information for each restaurant (address, phone, description, opening hours, nearby restaurants, etc.)
- Selenium-based web scraping with headless Chrome support
- Automatic pagination handling
- Duplicate detection and prevention
- Export to both JSON and CSV formats
- Comprehensive error handling and logging
- Progress tracking during scraping

## 🛠️ Prerequisites

- Python 3.8 or higher
- Google Chrome browser installed
- ChromeDriver (will be managed automatically by Selenium)

## 📦 Installation

1. Clone or download this repository

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## 🚀 Quick Start

### Option 1: Run Everything (Recommended)

Use the main script to run both scraping stages automatically:

```bash
python main.py
```

This will:
1. Scrape all restaurant listings from Michelin Thailand
2. Save basic info to `michelin_thailand.json` and `michelin_thailand.csv`
3. Scrape detailed information for each restaurant
4. Save detailed data to `michelin_thailand_details.json` and `michelin_thailand_details.csv`

### Option 2: Run Stages Separately

#### Stage 1: Scrape Restaurant Listings

```bash
python global_scraper.py
```

**Output files:**
- `michelin_thailand.json` - Complete restaurant list in JSON format
- `michelin_thailand.csv` - Complete restaurant list in CSV format

**Data collected:**
- Restaurant name
- Michelin Guide URL
- Star rating (0-3 stars)
- Distinction (Bib Gourmand, 1/2/3 stars, or None)
- Location/City
- Price range
- Cuisine type

#### Stage 2: Scrape Detailed Information

⚠️ **Important:** You must run Stage 1 first to generate the CSV file.

```bash
python details_scraper.py
```

**Output files:**
- `michelin_thailand_details.json` - Detailed restaurant info in JSON format
- `michelin_thailand_details.csv` - Detailed restaurant info in CSV format

**Additional data collected:**
- Full address
- Phone number
- Restaurant description
- Opening hours (day by day)
- Price range details
- Specific cuisine type
- Official website URL
- Nearby restaurants (up to 9)

## 📊 Output Examples

### Basic Restaurant Info (from global_scraper.py)
```json
{
  "name": "Gaggan Anand",
  "url": "https://guide.michelin.com/th/en/bangkok-region/bangkok/restaurant/gaggan-anand",
  "stars": 2,
  "distinction": "2 star",
  "location": "Bangkok",
  "price": "฿฿฿฿",
  "cuisine": "Indian"
}
```

### Detailed Restaurant Info (from details_scraper.py)
```json
{
  "name": "Gaggan Anand",
  "url": "https://guide.michelin.com/th/en/bangkok-region/bangkok/restaurant/gaggan-anand",
  "stars": 2,
  "distinction": "2 star",
  "location": "Bangkok",
  "address": "68/1 Soi Langsuan, Bangkok 10330",
  "phone": "+66 2 652 2700",
  "description": "Chef Gaggan Anand's progressive Indian cuisine...",
  "opening_hours": {
    "Tuesday": "18:00-23:00",
    "Wednesday": "18:00-23:00"
  },
  "price_range": "฿฿฿฿",
  "cuisine_type": "Indian",
  "website": "https://www.gaggan.com",
  "nearby_restaurants": [...]
}
```

## ⚙️ Configuration Options

### Global Scraper (global_scraper.py)

```python
scraper = MichelinThailandScraper(headless=True)

# Scrape all pages (default: max 20 pages)
restaurants = scraper.scrape_all(max_pages=20)

# Or scrape a single specific page
restaurants = scraper.scrape_single_page(page_number=1)
```

### Details Scraper (details_scraper.py)

```python
scraper = MichelinDetailScraper(headless=True)

# Scrape all restaurants from CSV
restaurants = scraper.scrape_all_from_csv(
    csv_file='michelin_thailand.csv',
    start_index=0,           # Start from first restaurant
    max_restaurants=None     # Scrape all (or set a number to limit)
)

# Or scrape a single restaurant URL
details = scraper.scrape_restaurant_details('https://guide.michelin.com/...')
```

## 🔍 Troubleshooting

### ChromeDriver Issues
If you encounter ChromeDriver errors:
- Ensure Google Chrome is installed
- Selenium 4.x automatically manages ChromeDriver, but you can manually install it if needed

### Timeout Errors
If pages are timing out:
- Check your internet connection
- Increase timeout in WebDriverWait (default: 15 seconds)
- Try running without headless mode to see what's happening:
  ```python
  scraper = MichelinThailandScraper(headless=False)
  ```

### Missing Data
Some restaurants may have incomplete information:
- The scrapers mark missing fields as 'N/A'
- This is expected as not all restaurants provide complete information

## 📝 Data Fields Reference

### Global Scraper Fields
| Field | Type | Description |
|-------|------|-------------|
| name | string | Restaurant name |
| url | string | Michelin Guide page URL |
| stars | integer | Star rating (0-3) |
| distinction | string | Award type (Bib Gourmand, X star, None) |
| location | string | City/area |
| price | string | Price range (฿ symbols) |
| cuisine | string | Cuisine type |

### Details Scraper Fields
All fields from global scraper, plus:

| Field | Type | Description |
|-------|------|-------------|
| address | string | Full address |
| phone | string | Contact number |
| description | string | Restaurant description |
| opening_hours | dict/string | Opening hours by day |
| price_range | string | Detailed price information |
| cuisine_type | string | Specific cuisine type |
| website | string | Official website URL |
| nearby_restaurants | list/string | List of nearby restaurants |
