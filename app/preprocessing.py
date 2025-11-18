#!/usr/bin/env python3
import argparse
import os

from global_scraper import MichelinThailandScraper
from details_scraper import MichelinDetailScraper
from google_reviews_scraper import GooglePlacesReviewsScraper


def print_header(text: str) -> None:
    """Print a formatted header for console output."""
    print(f"\n{'=' * 80}")
    print(f" {text}")
    print(f"{'=' * 80}\n")


def run_global_scraper(max_pages: int = 20, headless: bool = True) -> bool:
    """
    Run the global scraper to collect restaurant listings.

    :param max_pages: Maximum number of pages to scrape (default: 20)
    :param headless: Run Chrome in headless mode (default: True)
    :return: True if scraping was successful, False otherwise
    """
    print_header("STAGE 1: Scraping Restaurant Listings")

    try:
        scraper = MichelinThailandScraper(headless=headless)

        try:
            restaurants = scraper.scrape_all(max_pages=max_pages)

            if not restaurants:
                print("\nNo restaurants found. Please check the URL and try again.")
                return False

            # Save results
            scraper.save_to_json()
            scraper.save_to_csv()
            scraper.print_summary()

            print(f"\nStage 1 completed: {len(restaurants)} restaurants scraped")
            return True

        finally:
            del scraper

    except Exception as e:
        print(f"\nError during global scraping: {e}")
        return False


def run_details_scraper(max_restaurants: int | None = None, headless: bool = True) -> bool:
    """
    Run the details scraper to collect detailed restaurant information.

    :param max_restaurants: Maximum number of restaurants to scrape in detail (default: all)
    :param headless: Run Chrome in headless mode (default: True)
    :return: True if scraping was successful, False otherwise
    """
    print_header("STAGE 2: Scraping Detailed Restaurant Information")

    # Check if CSV exists
    csv_file = 'michelin_thailand.csv'
    if not os.path.exists(csv_file):
        print(f"\nError: {csv_file} not found.")
        print("Please run the global scraper first (Stage 1).")
        return False

    try:
        scraper = MichelinDetailScraper(headless=headless)

        try:
            restaurants = scraper.scrape_all_from_csv(
                csv_file=csv_file,
                start_index=0,
                max_restaurants=max_restaurants
            )

            if not scraper.restaurants_details:
                print("\nNo restaurant details collected.")
                return False

            # Save results
            scraper.save_to_json()
            scraper.save_to_csv()

            # Print summary
            print(f"\n{'=' * 80}")
            print("SUMMARY OF DETAILED SCRAPING")
            print(f"{'=' * 80}")
            print(f"Total restaurants with details: {len(scraper.restaurants_details)}")

            # Calculate statistics
            with_phone = len([r for r in scraper.restaurants_details if r.get('phone') != 'N/A'])
            with_address = len([r for r in scraper.restaurants_details if r.get('address') != 'N/A'])
            with_description = len([r for r in scraper.restaurants_details if r.get('description') != 'N/A'])
            with_website = len([r for r in scraper.restaurants_details if r.get('website') != 'N/A'])

            print(f"\nData Completeness:")
            print(
                f"  - Phone numbers: {with_phone}/{len(scraper.restaurants_details)} ({with_phone / len(scraper.restaurants_details) * 100:.1f}%)")
            print(
                f"  - Addresses: {with_address}/{len(scraper.restaurants_details)} ({with_address / len(scraper.restaurants_details) * 100:.1f}%)")
            print(
                f"  - Descriptions: {with_description}/{len(scraper.restaurants_details)} ({with_description / len(scraper.restaurants_details) * 100:.1f}%)")
            print(
                f"  - Websites: {with_website}/{len(scraper.restaurants_details)} ({with_website / len(scraper.restaurants_details) * 100:.1f}%)")

            print(f"\nStage 2 completed: {len(scraper.restaurants_details)} restaurants scraped in detail")
            return True

        finally:
            del scraper

    except Exception as e:
        print(f"\nError during detail scraping: {e}")
        return False

def run_google_reviews_scraper(api_key: str, max_restaurants: int | None = None) -> bool:
    print_header("STAGE 3: Scraping Google Reviews (Official API)")

    csv_file = 'michelin_thailand.csv'
    if not os.path.exists(csv_file):
        print(f"\nError: {csv_file} not found.")
        print("Please run Stage 1 first to generate it.")
        return False

    try:
        scraper = GooglePlacesReviewsScraper(api_key=api_key)

        results = scraper.scrape_from_csv(
            csv_file=csv_file,
            start_index=0,
            max_restaurants=max_restaurants
        )

        if not results:
            print("\nNo reviews collected.")
            return False

        scraper.save_to_json()
        scraper.save_reviews_only_csv()
        scraper.print_summary()

        print(f"\nStage 3 completed: Google reviews scraped")
        return True

    except Exception as e:
        print(f"\nError during Google reviews scraping: {e}")
        return False
