#!/usr/bin/env python3

"""
Main script to orchestrate the complete Michelin Thailand scraping process.

This script runs both stages of the scraping pipeline:
1. Global scraper: Collects basic restaurant listings
2. Details scraper: Extracts detailed information for each restaurant

Usage:
    python main.py [--max-pages MAX_PAGES] [--max-restaurants MAX_RESTAURANTS] [--headless]
"""

import argparse
import os
import sys
from global_scraper import MichelinThailandScraper
from details_scraper import MichelinDetailScraper


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


def main():
    """
    Main entry point for the Michelin Thailand scraper.

    Parses command line arguments and runs both scraping stages sequentially.
    """
    parser = argparse.ArgumentParser(
        description='Scrape restaurant data from Michelin Guide Thailand',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape everything in headless mode (default)
  python main.py

  # Scrape first 5 pages, then details for first 10 restaurants
  python main.py --max-pages 5 --max-restaurants 10

  # Run with visible browser for debugging
  python main.py --no-headless

  # Scrape only restaurant listings (Stage 1)
  python main.py --stage global

  # Scrape only details (requires existing CSV)
  python main.py --stage details
        """
    )

    parser.add_argument(
        '--max-pages',
        type=int,
        default=20,
        help='Maximum number of pages to scrape in Stage 1 (default: 20)'
    )

    parser.add_argument(
        '--max-restaurants',
        type=int,
        default=None,
        help='Maximum number of restaurants to scrape details for in Stage 2 (default: all)'
    )

    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Run Chrome in visible mode (useful for debugging)'
    )

    parser.add_argument(
        '--stage',
        choices=['global', 'details', 'both'],
        default='both',
        help='Which stage to run: global (listings), details, or both (default: both)'
    )

    args = parser.parse_args()

    headless = not args.no_headless

    print_header("🍽️  MICHELIN THAILAND RESTAURANT SCRAPER")
    print(f"Configuration:")
    print(f"  - Max pages (Stage 1): {args.max_pages}")
    print(f"  - Max restaurants (Stage 2): {args.max_restaurants if args.max_restaurants else 'All'}")
    print(f"  - Headless mode: {headless}")
    print(f"  - Stage to run: {args.stage}")

    stage1_success = False
    stage2_success = False

    if args.stage in ['global', 'both']:
        stage1_success = run_global_scraper(
            max_pages=args.max_pages,
            headless=headless
        )

        if not stage1_success:
            print("\nStage 1 failed. Aborting.")
            sys.exit(1)

    if args.stage in ['details', 'both']:
        stage2_success = run_details_scraper(
            max_restaurants=args.max_restaurants,
            headless=headless
        )

        if not stage2_success:
            print("\nStage 2 failed.")
            if args.stage == 'both':
                print("Note: Basic restaurant data was still collected in Stage 1.")
            sys.exit(1)

    print_header("SCRAPING COMPLETED SUCCESSFULLY")

    if args.stage == 'both' or args.stage == 'global':
        print(f"Basic restaurant listings: michelin_thailand.json / michelin_thailand.csv")

    if args.stage == 'both' or args.stage == 'details':
        print(f"Detailed restaurant info: michelin_thailand_details.json / michelin_thailand_details.csv")

    print("\nYou can now use the CSV or JSON files for further analysis!")
    print("Thank you for using Michelin Thailand Scraper! 🍜✨")


if __name__ == "__main__":
    main()