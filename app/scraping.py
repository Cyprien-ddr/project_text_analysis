import argparse

from app.details_scraper import MichelinDetailScraper
from app.global_scraper import MichelinThailandScraper
from app.google_reviews_scraper import GooglePlacesReviewsScraper
from app.scraping_missing_hours import scrape_missing_hours


def scraping():
    parser = argparse.ArgumentParser(description='Scrape data from Michelin Guide, Google Maps, and Missing Hours')

    parser.add_argument('--all', action="store_true", help="Enable all scraping steps")
    parser.add_argument(
        '--reviews',
        action="store_true",
        help="Enable scraping review, NB: only use for the model training",
    )
    parser.add_argument(
        '--api-key',
        type=str,
        required=False,
        help='Google Places API key (or set GOOGLE_API_KEY env variable)'
    )
    parser.add_argument(
        '--globals',
        action="store_true",
        help="Enable 1st scraping steps, global restaurants",
    )
    parser.add_argument(
        '--details',
        action="store_true",
        help="Enable 2nd scraping steps, details restaurants",
    )
    parser.add_argument(
        '--hours',
        action="store_true",
        help="Enable 3rd scraping steps, details restaurants",
    )
    parser.add_argument(
        '--output',
        default='./data/michelin_thailand_details_updated.csv',
        help='Output CSV file path'
    )

    args = parser.parse_args()

    if args.all:
        if not args.api_key:
            raise Exception("Please set GOOGLE_API_KEY env variable")
        scraper = MichelinThailandScraper(headless=True)
        restaurants = scraper.scrape_all(max_pages=20)
        if not restaurants:
            raise Exception("No restaurants found")
        scraper.save_to_csv('./data/tmp.csv')
        scraper.print_summary()
        scraper = MichelinDetailScraper(headless=True)
        scraper.scrape_all_from_csv(
            csv_file='./data/tmp.csv',
            start_index=0,
            max_restaurants=None
        )
        if not scraper.restaurants_details:
            raise Exception("No restaurants details found")

        scraper.save_to_csv('./data/tmp_bis.csv')
        scrape_missing_hours(csv_path='./data/tmp_bis.csv')

        scraper = GooglePlacesReviewsScraper(api_key=args.api_key)
        scraper.scrape_from_csv(csv_file='./data/tmp_bis.csv')
        if scraper.reviews_data:
            scraper.save_reviews_only_csv()
            scraper.print_summary()
        return

    if args.globals:
        pass


if __name__ == '__main__':
    scraping()