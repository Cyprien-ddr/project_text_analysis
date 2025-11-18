#!/usr/bin/env python3
import json
import csv
import time
import os

import requests
import pandas as pd
from typing import List, Dict, Optional


class GooglePlacesReviewsScraper:
    """
    Scrapes Google reviews using the official Places API (New).
    
    This uses Google's official API which provides:
    - Full, untruncated review text
    - Up to 5 most relevant reviews per place (API limitation)
    - Reliable data without scraping issues
    
    Attributes:
        api_key: Google Places API key
        base_url: Base URL for Places API (New)
        reviews_data: List of collected review data
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the scraper with Google API key.
        
        :param api_key: Your Google Places API key
        """
        self.api_key = api_key
        self.base_url = "https://places.googleapis.com/v1"
        self.reviews_data = []
        
        if not api_key:
            raise ValueError("Google API key is required!")
    
    def search_place_by_text(self, restaurant_name: str, location: str) -> Optional[str]:
        """
        Search for a place and get its Place ID.
        
        :param restaurant_name: Name of the restaurant
        :param location: Location/city of the restaurant
        :return: Place ID if found, None otherwise
        """
        url = f"{self.base_url}/places:searchText"
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName"
        }
        
        data = {
            "textQuery": f"{restaurant_name} {location} Thailand restaurant"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                if 'places' in result and len(result['places']) > 0:
                    place_id = result['places'][0]['id']
                    display_name = result['places'][0].get('displayName', {}).get('text', 'N/A')
                    print(f"  Found: {display_name} (ID: {place_id})")
                    return place_id
                else:
                    print(f"  Not found on Google Maps")
                    return None
            else:
                print(f"  Search error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"  Search exception: {e}")
            return None
    
    def get_place_reviews(self, place_id: str) -> Dict:
        """
        Get full reviews for a place using Place ID.
        
        :param place_id: Google Place ID
        :return: Dictionary with place info and reviews
        """
        url = f"{self.base_url}/places/{place_id}?fields=displayName,rating,userRatingCount,reviews"
        headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": self.api_key
        }
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                
                place_info = {
                    'display_name': result.get('displayName', {}).get('text', 'N/A'),
                    'overall_rating': result.get('rating', 'N/A'),
                    'total_reviews': result.get('userRatingCount', 0),
                    'reviews': []
                }
                
                if 'reviews' in result:
                    for review in result['reviews']:
                        review_data = {
                            'author': review.get('authorAttribution', {}).get('displayName', 'Anonymous'),
                            'rating': review.get('rating', 'N/A'),
                            'text': review.get('text', {}).get('text', ''),
                            'original_language': review.get('originalText', {}).get('languageCode', 'N/A'),
                            'publish_time': review.get('publishTime', 'N/A'),
                            'relative_time': review.get('relativePublishTimeDescription', 'N/A')
                        }
                        place_info['reviews'].append(review_data)
                
                print(f" Extracted {len(place_info['reviews'])} reviews (rating: {place_info['overall_rating']})")
                return place_info
                
            else:
                print(f" Reviews error: {response.status_code} - {response.text}")
                return {
                    'display_name': 'N/A',
                    'overall_rating': 'N/A',
                    'total_reviews': 0,
                    'reviews': []
                }
                
        except Exception as e:
            print(f" Reviews exception: {e}")
            return {
                'display_name': 'N/A',
                'overall_rating': 'N/A',
                'total_reviews': 0,
                'reviews': []
            }
    
    def scrape_restaurant_reviews(self, restaurant_name: str, location: str) -> Dict:
        """
        Scrape reviews for a single restaurant.
        
        :param restaurant_name: Name of the restaurant
        :param location: Location of the restaurant
        :return: Dictionary with restaurant info and reviews
        """
        print(f"\n{'='*70}")
        print(f"Processing: {restaurant_name}")
        print(f"{'='*70}")
        
        place_id = self.search_place_by_text(restaurant_name, location)
        
        if not place_id:
            return {
                'restaurant_name': restaurant_name,
                'location': location,
                'status': 'not_found',
                'google_display_name': 'N/A',
                'overall_rating': 'N/A',
                'total_reviews': 0,
                'reviews': []
            }
        
        place_info = self.get_place_reviews(place_id)
        
        return {
            'restaurant_name': restaurant_name,
            'location': location,
            'status': 'success',
            'google_display_name': place_info['display_name'],
            'overall_rating': place_info['overall_rating'],
            'total_reviews': place_info['total_reviews'],
            'reviews': place_info['reviews']
        }
    
    def scrape_from_csv(
        self, 
        csv_file: str, 
        start_index: int = 0, 
        max_restaurants: Optional[int] = None
    ) -> List[Dict]:
        """
        Scrape reviews for restaurants from CSV file.
        
        :param csv_file: Path to the Michelin CSV file
        :param start_index: Starting index in the CSV
        :param max_restaurants: Maximum number of restaurants to process
        :return: List of results
        """
        try:
            df = pd.read_csv(csv_file)
            print(f"\nLoaded {len(df)} restaurants from {csv_file}")
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return []
        
        if 'name' not in df.columns or 'location' not in df.columns:
            print("Error: CSV must have 'name' and 'location' columns")
            return []
        
        total = len(df)
        end_index = min(start_index + max_restaurants, total) if max_restaurants else total
        
        print(f"\n{'='*70}")
        print(f"Starting scraping: {end_index - start_index} restaurants")
        print(f"(Index {start_index} to {end_index - 1})")
        print(f"{'='*70}")
        
        processed_names = set()
        
        for idx, row in df.iloc[start_index:end_index].iterrows():
            name = row.get('name', 'N/A')
            location = row.get('location', 'N/A')
            
            if name == 'N/A' or location == 'N/A':
                print(f"\n[{idx + 1}/{total}] ⏭️  Skipping - missing name or location")
                continue
            
            if name in processed_names:
                print(f"\n[{idx + 1}/{total}] ⏭️  Skipping duplicate: {name}")
                continue
            
            processed_names.add(name)
            
            print(f"\n[{idx + 1}/{total}] Processing: {name}")
            
            result = self.scrape_restaurant_reviews(
                restaurant_name=name,
                location=location
            )
            
            result['michelin_stars'] = row.get('stars', 0)
            result['michelin_distinction'] = row.get('distinction', 'N/A')
            result['cuisine'] = row.get('cuisine', 'N/A')
            result['price'] = row.get('price', 'N/A')
            
            self.reviews_data.append(result)
            
            time.sleep(0.5)
        
        print(f"\n{'='*70}")
        print(f"Scraping completed: {len(self.reviews_data)} restaurants processed")
        print(f"{'='*70}")
        
        return self.reviews_data
    
    def save_to_json(self, filename: str = './data/google_reviews_api.json') -> None:
        """Save reviews data to JSON file."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.reviews_data, f, ensure_ascii=False, indent=2)
        print(f"\nData saved to {filename}")
    
    def save_reviews_only_csv(self, filename: str = './data/google_reviews.csv') -> None:
        """
        Save ONLY the review texts to CSV (one row per review).
        No duplicates, clean format.
        """
        if not self.reviews_data:
            print("No data to save")
            return
        
        all_reviews = []
        seen_reviews = set()
        
        for restaurant in self.reviews_data:
            rest_name = restaurant['restaurant_name']
            location = restaurant['location']
            rating = restaurant['overall_rating']
            total = restaurant['total_reviews']
            cuisine = restaurant.get('cuisine', 'N/A')
            stars = restaurant.get('michelin_stars', 0)
            
            for review in restaurant.get('reviews', []):
                review_text = review.get('text', '').strip()
                
                if not review_text:
                    continue
                
                review_key = f"{rest_name}|{review_text[:50]}"
                if review_key in seen_reviews:
                    continue
                
                seen_reviews.add(review_key)
                
                all_reviews.append({
                    'restaurant_name': rest_name,
                    'location': location,
                    'cuisine': cuisine,
                    'michelin_stars': stars,
                    'google_rating': rating,
                    'total_google_reviews': total,
                    'reviewer': review.get('author', 'Anonymous'),
                    'rating': review.get('rating', 'N/A'),
                    'review_text': review_text,
                    'date': review.get('relative_time', 'N/A'),
                    'language': review.get('original_language', 'N/A')
                })
        
        if not all_reviews:
            print("No reviews to save")
            return
        
        keys = all_reviews[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_reviews)
        
        print(f"Saved {len(all_reviews)} unique reviews to {filename}")
    
    def print_summary(self) -> None:
        """Print summary statistics of scraped data."""
        if not self.reviews_data:
            print("No data to summarize")
            return
        
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        
        total = len(self.reviews_data)
        successful = len([r for r in self.reviews_data if r['status'] == 'success'])
        not_found = len([r for r in self.reviews_data if r['status'] == 'not_found'])
        
        all_review_texts = set()
        for r in self.reviews_data:
            for review in r.get('reviews', []):
                text = review.get('text', '').strip()
                if text:
                    all_review_texts.add(text)
        
        total_unique_reviews = len(all_review_texts)
        
        print(f"Total restaurants processed: {total}")
        print(f" Successfully found: {successful}")
        print(f" Not found on Google Maps: {not_found}")
        print(f"\nTotal unique reviews collected: {total_unique_reviews}")
        
        ratings = []
        for r in self.reviews_data:
            rating = r.get('overall_rating', 'N/A')
            if rating != 'N/A' and rating:
                try:
                    ratings.append(float(rating))
                except:
                    pass
        
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            print(f"Average Google rating: {avg_rating:.2f}/5.0")
        
        languages = {}
        for r in self.reviews_data:
            for review in r.get('reviews', []):
                lang = review.get('original_language', 'unknown')
                languages[lang] = languages.get(lang, 0) + 1
        
        if languages:
            print(f"\nReviews by language:")
            for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
                print(f"  {lang}: {count}")
        
        print(f"{'='*70}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Scrape Google Reviews using official Places API',
        epilog="""
Examples:
  python google_reviews_scraper.py --api-key YOUR_API_KEY
  python google_reviews_scraper.py --api-key YOUR_KEY --max-restaurants 20
  python google_reviews_scraper.py --api-key YOUR_KEY --csv michelin_thailand_details.csv

Note: Get your API key from https://console.cloud.google.com/
      Enable "Places API (New)" in your Google Cloud project
        """
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        required=False,
        help='Google Places API key (or set GOOGLE_API_KEY env variable)'
    )
    parser.add_argument(
        '--csv',
        type=str,
        default='michelin_thailand.csv',
        help='Path to the Michelin CSV file (default: michelin_thailand.csv)'
    )
    parser.add_argument(
        '--max-restaurants',
        type=int,
        default=None,
        help='Maximum number of restaurants to scrape (default: all)'
    )
    parser.add_argument(
        '--start-index',
        type=int,
        default=0,
        help='Starting index in CSV (default: 0)'
    )
    
    args = parser.parse_args()
    
    # Get API key from argument or environment variable
    api_key = args.api_key or os.environ.get('GOOGLE_API_KEY')
    
    if not api_key:
        print("Error: Google API key required!")
        print("\nProvide it via:")
        print("  1. --api-key argument")
        print("  2. GOOGLE_API_KEY environment variable")
        print("\nGet your API key from: https://console.cloud.google.com/")
        print("Enable 'Places API (New)' in your project")
        exit(1)
    
    print("GOOGLE REVIEWS SCRAPER (Official API)")
    print(f"CSV file: {args.csv}")
    print(f"Max restaurants: {args.max_restaurants or 'All'}")
    print(f"Starting index: {args.start_index}")
    print(f"API: Google Places API (New)")
    
    scraper = GooglePlacesReviewsScraper(api_key=api_key)
    
    try:
        # Scrape reviews
        scraper.scrape_from_csv(
            csv_file=args.csv,
            start_index=args.start_index,
            max_restaurants=args.max_restaurants
        )
        
        # Save results
        if scraper.reviews_data:
            scraper.save_to_json()
            scraper.save_reviews_only_csv()
            scraper.print_summary()
        else:
            print("\nNo data collected")
    
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()