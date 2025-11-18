# 🍽️ Michelin Thailand Restaurant Search & Scraper

A comprehensive system for scraping, indexing, and intelligently searching Michelin-starred and Bib Gourmand restaurants in Thailand. Features hybrid semantic search with ML-powered tag prediction and an interactive terminal interface.

## ✨ Key Features

### 🔍 Intelligent Search System
- **Hybrid Search Engine**: Combines semantic similarity (FAISS) + ML tag prediction + food detection
- **Smart Scoring**: Weighted scoring system balancing relevance across multiple dimensions
- **ML Tag Prediction**: RoBERTa-based multi-label classifier predicting restaurant attributes
- **Food Detection**: Automatic detection of food items in queries with category matching
- **Interactive TUI**: Beautiful terminal interface built with Textual

### 🕷️ Comprehensive Web Scraper
- **Three-Stage Pipeline**:
  - Stage 1: Restaurant listings (name, stars, location, price, cuisine)
  - Stage 2: Detailed info (address, phone, description, hours, tags)
  - Stage 3: Google reviews via official Places API
- Selenium-based with headless Chrome support
- Automatic pagination and duplicate prevention
- Exports to JSON and CSV

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Scraping Data](#scraping-data)
- [Building the Search Index](#building-the-search-index)
- [Using the Search Interface](#using-the-search-interface)
- [ML Tag Prediction](#ml-tag-prediction)
- [Architecture](#architecture)
- [Output Files](#output-files)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## 🛠️ Prerequisites

- Python 3.8+
- Google Chrome browser
- Google Places API key (for Stage 3 only)

## 📦 Installation

```bash
# Clone the repository
git clone git@github.com:Cyprien-ddr/project_text_analysis.git michelin-thailand-search
cd michelin-thailand-search

# Install dependencies
pip install -r requirements.txt
```

**Required packages:**
- `selenium` - Web scraping
- `pandas` - Data manipulation
- `transformers` - ML models
- `sentence-transformers` - Semantic embeddings
- `faiss-cpu` - Vector similarity search
- `torch` - Deep learning
- `textual` - Terminal UI
- `scikit-learn` - ML utilities

## 🚀 Quick Start

### 1. Scrape Restaurant Data

```bash
# Run all scraping stages
python main.py --max-pages 20

# Or run specific stages
python main.py --stage global           # Stage 1 only
python main.py --stage details          # Stage 2 only
python main.py --stage reviews --google-api-key YOUR_KEY  # Stage 3 only
```

### 2. Build the Search Index

```bash
python ingest.py
```

This creates:
- `restaurants.index` - FAISS vector index
- `restaurants.pkl` - Processed restaurant data

### 3. Train ML Tag Predictor (Optional)

```bash
python processing.py
```

Or the model will auto-train on first use if missing.

### 4. Launch Search Interface

```bash
python search_faiss.py
```

## 🕷️ Scraping Data

### Stage 1: Restaurant Listings

```bash
python global_scraper.py
```

**Collects:**
- Restaurant names
- Star ratings (0-3 stars)
- Distinctions (Bib Gourmand)
- Locations
- Price ranges
- Cuisine types
- Michelin Guide URLs

**Output:** `michelin_thailand.json`, `michelin_thailand.csv`

### Stage 2: Detailed Information

```bash
python details_scraper.py
```

**Collects:**
- Full addresses
- Phone numbers
- Descriptions
- Opening hours
- "Good for" tags (Date night, Family friendly, etc.)
- Websites
- Nearby restaurants (up to 9)

**Output:** `michelin_thailand_details.json`, `michelin_thailand_details.csv`

### Stage 3: Google Reviews

```bash
python google_reviews_scraper.py --api-key YOUR_API_KEY
```

**Collects:**
- Review texts (up to 5 per restaurant)
- Ratings
- Author names
- Publish dates
- Language codes

**Output:** `google_reviews.csv`, `google_reviews_api.json`

**Getting an API Key:**
1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Enable "Places API (New)"
3. Create credentials → API Key

### Complete Pipeline

```bash
python main.py \
  --max-pages 20 \
  --max-restaurants 100 \
  --google-api-key YOUR_KEY
```

## 🏗️ Building the Search Index

```bash
python ingest.py
```

**Process:**
1. Loads data from `michelin_thailand.csv`, `michelin_thailand_details.csv`, `google_reviews.csv`
2. Merges datasets on restaurant names
3. Creates searchable text combining: name + cuisine + description + English reviews
4. Generates embeddings using `sentence-transformers/all-MiniLM-L6-v2`
5. Builds FAISS index with inner product similarity
6. Saves index and processed data

**Output:**
- `restaurants.index` - FAISS vector index
- `restaurants.pkl` - Pickled DataFrame

## 🔍 Using the Search Interface

### Launch the TUI

```bash
python search_faiss.py
```

### Features

**Search Capabilities:**
- Natural language queries: `"romantic dinner with views"`
- Food-specific: `"best pad thai"`
- Occasion-based: `"family friendly brunch spot"`

**Filters:**
- 📍 Location (Bangkok, Phuket, Chiang Mai, etc.)
- 🏆 Awards (3 star, 2 star, 1 star, Bib Gourmand)
- 🍽️ Cuisine (Italian, Thai, Japanese, etc.)
- 💰 Price range

**Keyboard Shortcuts:**
- `Ctrl+Q` - Quit
- `Ctrl+R` - Reset filters
- `Enter` - Search

**Results Display:**
Each result shows:
- Rank and restaurant name
- Michelin distinction (⭐⭐⭐ or 🍴)
- Location, cuisine, price
- Description preview
- Predicted tags with confidence scores
- Contact info (phone, website)
- Score breakdown (total, semantic, tags, food)

## 🤖 ML Tag Prediction

### Training the Model

```bash
python processing.py
```

**Process:**
1. Extracts tags from `michelin_thailand_details.csv` ("Good for" tags)
2. Builds multi-label dataset from descriptions
3. Trains RoBERTa-base classifier with class balancing
4. Optimizes classification threshold via F1-macro
5. Saves model, tokenizer, labels, and threshold

**Model:** `./model/michelin_model/`
- `pytorch_model.bin` - Trained weights
- `config.json` - Model config
- `tokenizer` files
- `labels.csv` - Tag vocabulary
- `best_threshold.txt` - Optimal classification threshold

**Tags Predicted:**
- Date night
- Family friendly
- Chef's table
- Trending
- Counter seating
- Local favorite
- Outdoor dining
- Group dining
- Solo dining
- And more...

### Using the Predictor

```python
from tag_predictor import TagPredictor

predictor = TagPredictor()
tags = predictor.predict_tags("Perfect for romantic evenings")
# Returns: {'Date night': 0.87, 'Trending': 0.65}
```

## 🏛️ Architecture
```
┌─────────────────────────────────────────────────────┐
│                 User Query                          │
│         "romantic pizza place in Bangkok"           │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│              RestaurantSearch                       │
│  ┌───────────────────────────────────────────────┐  │
│  │ 1. Apply Filters (location, cuisine, price)   │  │
│  │ 2. Generate Query Embedding (Sentence-BERT)   │  │
│  │ 3. FAISS Semantic Search (top K)              │  │
│  │ 4. Detect ML Tags (TagPredictor)              │  │
│  │ 5. Detect Food (Food Regex / Dataset)         │  │
│  │ 6. Temporal & Location Detection              │  │
│  └───────────────────────────────────────────────┘  │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
      ┌───────────────────────────────┐
      │      Weighted Scoring         │
      │ 1.8×Semantic                  │
      │ 0.6×Tags                      │
      │ 0.4×Food                      │
      │ 1.0×Hours                     │
      │ 0.8×Location                  │
      └───────────┬───────────────────┘
                  ▼
      ┌───────────────────────┐
      │   Ranked Results      │
      │   Display in TUI      │
      └───────────────────────┘
```

### Scoring Weights

```python
SEMANTIC_WEIGHT = 1.8  # Vector similarity
TAG_WEIGHT = 0.6       # ML predicted tags
FOOD_WEIGHT = 0.4      # Food term detection
```

## 📂 Output Files

### Scraping Outputs

| File | Description |
|------|-------------|
| `michelin_thailand.json` | Basic listings (JSON) |
| `michelin_thailand.csv` | Basic listings (CSV) |
| `michelin_thailand_details.json` | Detailed info (JSON) |
| `michelin_thailand_details.csv` | Detailed info (CSV) |
| `google_reviews.csv` | All reviews (CSV) |
| `google_reviews_api.json` | Review API responses (JSON) |

### Index & Model Outputs

| File | Description |
|------|-------------|
| `restaurants.index` | FAISS vector index |
| `restaurants.pkl` | Processed DataFrame |
| `model/michelin_model/` | ML tag prediction model |
| `search_logs_detailed.csv` | Search history with scores |

## ⚙️ Configuration

### Search Weights

Edit `search.py`:

```python
SEMANTIC_WEIGHT = 1.8  # Adjust semantic importance
TAG_WEIGHT = 0.6       # Adjust tag matching weight
FOOD_WEIGHT = 0.4      # Adjust food detection weight
```

### Embedding Model

Change in `search.py` and `ingest.py`:

```python
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Alternative: "paraphrase-multilingual-mpnet-base-v2"
```

### Classification Threshold

Auto-optimized during training, or manually set in `tag_predictor.py`:

```python
self.threshold = 0.5  # Default threshold
```

## 🔧 Troubleshooting

### ChromeDriver Issues

```bash
# Selenium 4.x auto-manages ChromeDriver
# But if issues persist:
pip install --upgrade selenium
```

### FAISS Not Working

```bash
# Use CPU version
pip install faiss-cpu

# Or GPU version (if CUDA available)
pip install faiss-gpu
```

### Model Not Loading

```bash
# Train from scratch
python processing.py

# Or download pre-trained (if available)
# Place in ./model/michelin_model/
```

### Out of Memory

Reduce batch size in `processing.py`:

```python
batch_size = 4  # Default is 8
```

Or use smaller embedding model:

```python
MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Smaller
# Instead of: "paraphrase-multilingual-mpnet-base-v2"
```

### Search Returns No Results

1. Check if index exists: `ls restaurants.index`
2. Rebuild index: `python ingest.py`
3. Try broader query or fewer filters

## 📊 Data Fields Reference

### Basic Fields (Stage 1)

| Field | Type | Description |
|-------|------|-------------|
| name | string | Restaurant name |
| url | string | Michelin Guide URL |
| stars | int | Star rating (0-3) |
| distinction | string | Award (Bib Gourmand, X star) |
| location | string | City/area |
| price | string | Price range (฿ symbols) |
| cuisine | string | Cuisine type |

### Detailed Fields (Stage 2)

| Field | Type | Description |
|-------|------|-------------|
| address | string | Full address |
| phone | string | Phone number |
| description | string | Full description |
| opening_hours | dict | Hours by day |
| tags | list | "Good for" tags |
| website | string | Official URL |
| nearby_restaurants | list | 9 nearby spots |

### Review Fields (Stage 3)

| Field | Type | Description |
|-------|------|-------------|
| restaurant_name | string | Restaurant name |
| reviewer | string | Reviewer name |
| rating | float | Review rating |
| review_text | string | Full review text |
| date | string | Publish date |
| language | string | Language code |

## 📝 Search Logs

All searches are logged to `search_logs_detailed.csv`:

```csv
timestamp,query,predicted_tags,location,distinction,cuisine,price,num_results,details
2024-01-15 14:30:22,"romantic dinner","Date night(0.87), Trending(0.65)",Bangkok,All,Italian,All,5,"Ristorante [Total=2.456 | Sem=0.892 | Tag=0.523 | ...] ; ..."
```

## 🎯 Example Queries

```
"romantic dinner with beautiful views"
"best pad thai in Bangkok"
"family friendly Italian restaurant"
"chef's table experience"
"affordable street food"
"trending Japanese omakase"
"outdoor dining for groups"
"solo dining with counter seating"
"local favorite breakfast spot"
```

## 📄 License

This project is for educational purposes. Respect Michelin Guide's terms of service and robots.txt when scraping.
