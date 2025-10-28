#!/usr/bin/env python3
from typing import Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import csv
import time


def extract_restaurant_info(element) -> dict[Any, Any] | None:
    """
    Extract structured restaurant details from a listing WebElement.

    Parses name, URL, star count and distinction (including Bib Gourmand), location,
    price, and cuisine using Selenium CSS selectors. Missing fields default to 'N/A'
    (or 0 for stars). Returns None if the name cannot be found.

    :param element: Selenium WebElement representing a restaurant card/link.
    :type element: selenium.webdriver.remote.webelement.WebElement
    :return: Dict with keys: name, url, stars, distinction, location, price, cuisine; or None on failure.
    :rtype: dict | None
    """
    try:
        info = {}

        try:
            name = element.find_element(By.CSS_SELECTOR, "h3.card__menu-title--text, h3[class*='title']").text
            info['name'] = name.strip()
        except NoSuchElementException:
            info['name'] = 'N/A'

        try:
            link = element.find_element(By.CSS_SELECTOR, "a[href*='/restaurant']")
            info['url'] = link.get_attribute('href')
        except NoSuchElementException:
            info['url'] = 'N/A'

        try:
            distinction_div = element.find_element(By.CSS_SELECTOR, "div.card__menu-content--distinction")
            award_imgs = distinction_div.find_elements(By.CSS_SELECTOR, "img.michelin-award")

            star_count = 0
            has_bib_gourmand = False

            for img in award_imgs:
                src = img.get_attribute('src')
                if '1star.svg' in src:
                    star_count += 1
                elif 'bib-gourmand.svg' in src:
                    has_bib_gourmand = True

            info['stars'] = star_count
            info['distinction'] = 'Bib Gourmand' if has_bib_gourmand else (
                f'{star_count} star' if star_count > 0 else 'None')

        except NoSuchElementException:
            info['stars'] = 0
            info['distinction'] = 'None'

        try:
            score_divs = element.find_elements(By.CSS_SELECTOR, "div.card__menu-footer--score")

            if len(score_divs) > 0:
                info['location'] = score_divs[0].text.strip()
            else:
                info['location'] = 'N/A'

            if len(score_divs) > 1:
                price_cuisine = score_divs[1].text.strip()

                if '·' in price_cuisine:
                    parts = price_cuisine.split('·')
                    info['price'] = parts[0].strip()
                    info['cuisine'] = parts[1].strip() if len(parts) > 1 else 'N/A'
                else:
                    info['price'] = 'N/A'
                    info['cuisine'] = price_cuisine
            else:
                info['price'] = 'N/A'
                info['cuisine'] = 'N/A'

        except NoSuchElementException:
            info['location'] = 'N/A'
            info['price'] = 'N/A'
            info['cuisine'] = 'N/A'

        return info if info['name'] != 'N/A' else None

    except Exception as e:
        print(f"Error while extracting: {e}")
        return None


class MichelinThailandScraper:
    """
    Scrapes restaurant data from the Michelin Guide Thailand website using Selenium.

    Features:
    - Configures a Chrome WebDriver (headless by default) with anti-automation options.
    - Waits for restaurant cards to load and extracts structured info (name, URL, stars/distinction,
      location, price, cuisine) from each listing.
    - Supports scraping a single page or iterating through multiple pages.
    - Persists collected data to JSON/CSV and prints a summary of results.

    Attributes:
    - base_url: Base URL of the Michelin Guide site.
    - thailand_url: Entry URL for Thailand restaurant listings.
    - restaurants: Accumulated list of extracted restaurant dictionaries.
    - driver: Selenium WebDriver instance.
    - wait: WebDriverWait instance for element synchronization.
    """
    def __init__(self, headless=True):
        self.base_url = "https://guide.michelin.com"
        self.thailand_url = f"{self.base_url}/th/en/selection/thailand/restaurants"
        self.restaurants = []

        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 15)

    def __del__(self) -> None:
        """
        Clean up resources when the scraper is garbage-collected.

        If a Selenium WebDriver was initialized, gracefully quits the driver to
        close the browser session and free system resources.

        :return: None
        """
        if hasattr(self, 'driver'):
            self.driver.quit()

    def wait_for_restaurants(self) -> bool:
        """
        Wait for restaurant listing elements to appear on the page.

        Uses the WebDriverWait instance to block until at least one restaurant card/link
        is present, identified by CSS selectors for menu cards or tracked restaurant links.

        :return: True if elements are found before timeout; False if a TimeoutException occurs.
        :rtype: bool
        """
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[class*='card__menu'], a[data-track*='restaurant']"))
            )
            return True
        except TimeoutException:
            print("Timeout: restaurants can't be loaded")
            return False

    def scrape_single_page(self, page_number: int) -> list:
        """
        Scrape a single Michelin Thailand results page and return newly extracted restaurants.

        Builds the page URL, navigates with the Selenium driver, waits for listings, scrolls to load content,
        collects restaurant elements, extracts structured info, and deduplicates by name against self.restaurants.

        :param page_number: 1-based page index to scrape; 1 uses the base Thailand URL, otherwise paginated path.
        :type page_number: int
        :return: List of newly extracted restaurant dictionaries from the page; empty list on failure or no results.
        :rtype: list[dict]
        """
        print(f"\nScraping of the page {page_number}...")

        if page_number == 1:
            url = self.thailand_url
        else:
            url = f"{self.thailand_url}/page/{page_number}"

        print(f"URL: {url}")

        try:
            self.driver.get(url)

            if not self.wait_for_restaurants():
                return []

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            restaurant_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.card__menu, div[class*='card__menu']")
            print(restaurant_elements)
            if not restaurant_elements:
                print("no restaurant element")
                restaurant_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[data-track*='restaurant']")

            print(f"Find {len(restaurant_elements)} resto in this page")

            page_restaurants = []
            existing_names = {r['name'] for r in self.restaurants}
            for idx, element in enumerate(restaurant_elements, 1):
                info = extract_restaurant_info(element)
                if info:
                    if info['name'] and info['name'] not in existing_names:
                        page_restaurants.append(info)
                        self.restaurants.append(info)
                        existing_names.add(info['name'])
                        print(f"  {idx}. {info['name']} - {info['location']} - {info['distinction']} / {info['stars']}\n{info['cuisine']} : {info['price']}, {info['location']}")
                    else:
                        print(f"  {idx}. [Twice ignored] {info['name']}")
            print(f"\nTotal extract: {len(page_restaurants)} restaurants")
            return page_restaurants

        except Exception as e:
            print(f"Error while scraping: {e}")
            return []

    def scrape_all(self, max_pages=20) -> list:
        """
        Iterate through Michelin Thailand result pages and accumulate restaurants.

        Calls scrape_single_page for pages 1..max_pages, stopping early when a page
        yields no results. Prints progress and returns the full list collected in
        self.restaurants.

        :param max_pages: Maximum number of pages to traverse (inclusive). Defaults to 20.
        :type max_pages: int
        :return: All collected restaurant dictionaries across visited pages.
        :rtype: list[dict]
        """
        print("Start of the scraping")

        for page in range(1, max_pages + 1):
            restaurants = self.scrape_single_page(page)

            if not restaurants:
                print(f"No restaurant on this page {page}")
                break

        print(f"\n{'=' * 60}")
        print(f"Scraping finished: {len(self.restaurants)} restaurants")
        return self.restaurants

    def save_to_json(self, filename='michelin_thailand.json') -> None:
        """
        Write the collected restaurants to a JSON file.

        Serializes self.restaurants with UTF-8 encoding, preserving non-ASCII characters
        and pretty-printing with an indent of 2. Prints a confirmation message on success.

        :param filename: Output JSON file path. Defaults to 'michelin_thailand.json'.
        :return: None
        """
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.restaurants, f, ensure_ascii=False, indent=2)
        print(f"Data saved in {filename}")

    def save_to_csv(self, filename='michelin_thailand.csv')-> None:
        """
        Write collected restaurants to a CSV file.

        If no restaurants have been scraped, prints a message and returns early.
        Writes UTF-8 encoded CSV with header inferred from the first restaurant dict's keys.

        :param filename: Output CSV file path. Defaults to 'michelin_thailand.csv'.
        :type filename: str

        :return: None
        """
        if not self.restaurants:
            print("No data to save")
            return

        keys = self.restaurants[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.restaurants)
        print(f"Data saved in {filename}")

    def print_summary(self) -> None:
        """
        Print a concise summary of scraped restaurants.

        Displays:
        - Total count of restaurants in self.restaurants.
        - Count of starred restaurants, broken down by 3, 2, and 1 star.
        - Count placeholder for Bib Gourmand entries.
        - Top 10 cities by number of restaurants.

        :return: None
        """
        print(f"\n{'=' * 60}")
        print(f"TLDR")
        print(f"{'=' * 60}")
        print(f"Total restaurants: {len(self.restaurants)}")

        starred = [r for r in self.restaurants if r.get('stars', 0) > 0]
        print(f"Stars Restaurants: {len(starred)}")

        if starred:
            for stars in [3, 2, 1]:
                count = len([r for r in starred if r.get('stars') == stars])
                if count > 0:
                    print(f"  {stars} star: {count}")

        print(f"Bib gourmand: {len([r for r in self.restaurants if r.get('distinction') == 'Bib Gourmand'])}")
        cities = {}
        for r in self.restaurants:
            city = r.get('location', 'Unknown')
            cities[city] = cities.get(city, 0) + 1

        print(f"\nTop 10 city:")
        for city, count in sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {city}: {count}")


if __name__ == "__main__":
    scraper = MichelinThailandScraper(headless=True)

    try:
        # Option 1: Scrap  only une page
        # restaurants = scraper.scrape_single_page(page_number=3)

        # Option 2: Scrap every pages
        restaurants = scraper.scrape_all(max_pages=20)

        if restaurants:
            scraper.save_to_json()
            scraper.save_to_csv()
            scraper.print_summary()
        else:
            print("\nAny result check the url")

    finally:
        del scraper