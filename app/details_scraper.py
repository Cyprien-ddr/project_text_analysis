#!/usr/bin/env python3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import csv
import time
import pandas as pd


def load_restaurants_from_csv(csv_file: str) -> pd.DataFrame | None:
    """
    Load a CSV of restaurant records into a DataFrame.
    """
    try:
        df = pd.read_csv(csv_file)
        print(f"Load {len(df)} restaurants from {csv_file}")
        return df
    except Exception as e:
        print(f"Error while loading the CSV: {e}")
        return None


class MichelinDetailScraper:
    """
    Scrapes detailed restaurant data from the Michelin Guide using Selenium.
    Now includes extraction of "Good for" tags.
    """

    def __init__(self, headless=True):
        self.base_url = "https://guide.michelin.com"
        # Chrome config
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
        self.restaurants_details = []

    def __del__(self) -> None:
        """Clean up resources when the scraper is garbage-collected."""
        if hasattr(self, 'driver'):
            self.driver.quit()

    def extract_tags(self) -> list:
        """
        Extract "Good for" tags from the restaurant page.

        Looks for the tag section on the page and extracts all applicable tags
        such as Chef's Table, Date night, Family Friendly, etc.

        :return: List of "Good for" tag names, or empty list if none found.
        :rtype: list
        """
        try:
            # Try to find the tags section
            tags = []

            # Method 1: Look for tag elements in the page
            try:
                tag_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "span.tag--pills"
                )

                for tag in tag_elements:
                    tag_text = tag.text.strip()
                    if tag_text:
                        tags.append(tag_text)

                if tags:
                    print(f"  Found tags (Method 1): {tags}")
                    return tags
            except Exception as e:
                print(f"  Method 1 failed: {e}")

            # Method 2: Look for specific data attributes or classes
            try:
                tag_containers = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div.restaurant-details__services ul li, div[class*='service'] li"
                )

                for container in tag_containers:
                    tag_text = container.text.strip()
                    if tag_text:
                        tags.append(tag_text)

                if tags:
                    print(f"  Found tags (Method 2): {tags}")
                    return tags
            except Exception as e:
                print(f"  Method 2 failed: {e}")

            # Method 3: Look in the data-sheet area
            try:
                service_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div.data-sheet__block--list li"
                )

                for elem in service_elements:
                    tag_text = elem.text.strip()
                    if tag_text and not any(x in tag_text.lower() for x in ['credit', 'cash', 'wheelchair', 'parking']):
                        tags.append(tag_text)

                if tags:
                    print(f"  Found tags (Method 3): {tags}")
                    return tags
            except Exception as e:
                print(f"  Method 3 failed: {e}")

            print("  No 'Good for' tags found")
            return []

        except Exception as e:
            print(f"  Error extracting Good for tags: {e}")
            return []

    def extract_address(self) -> str:
        """
        Extract the restaurant's address from the current Michelin page using Selenium.

        Tries a CSS selector targeting the primary address block, then falls back to an
        XPath lookup for a maps-linked list item. Returns a cleaned string or 'N/A' if
        no address is found.

        :return: Address text or 'N/A'.
        :rtype: str
        """
        try:
            address = self.driver.find_element(By.CSS_SELECTOR,"div.data-sheet__detail-info div.data-sheet__block > div.data-sheet__block--text:nth-of-type(1) ").text

            return address.strip()
        except NoSuchElementException:
            try:
                address_li = self.driver.find_element(By.XPATH,
                                                      "//li[contains(@class, 'restaurant-details__heading--list-item')]//a[contains(@href, 'maps')]")
                return address_li.text.strip()
            except:
                return 'N/A'

    def extract_phone(self) -> str:
        """
        Extract the restaurant's phone number from the current Michelin page.

        Attempts a CSS selector for tel links and CTA, then falls back to an XPath lookup.
        Returns a trimmed string or 'N/A' if no phone is found.

        :return: Phone number text or 'N/A'.
        :rtype: str
        """
        try:
            phone = self.driver.find_element(By.CSS_SELECTOR, "a[href^='tel:'], a[data-event='CTA_tel']").text
            return phone.strip()
        except NoSuchElementException:
            try:
                phone_li = self.driver.find_element(By.XPATH,
                                                    "//li[contains(@class, 'restaurant-details__heading--list-item')]//a[contains(@href, 'tel:')]")
                return phone_li.text.strip()
            except:
                return 'N/A'

    def extract_description(self) -> str:
        """
        Extract the restaurant's description from the current Michelin page.

        Tries a primary CSS selector targeting the details or data-sheet description,
        then falls back to a legacy description block. Returns trimmed text or 'N/A'
        when no description element is found.

        :return: Description text or 'N/A'.
        :rtype: str
        """
        try:
            desc = self.driver.find_element(By.CSS_SELECTOR,
                                            "div.restaurant-details__description--text, div.data-sheet__description").text
            return desc.strip()
        except NoSuchElementException:
            try:
                desc = self.driver.find_element(By.CSS_SELECTOR, "div.restaurant-details__description").text
                return desc.strip()
            except:
                return 'N/A'

    def extract_opening_hours(self) -> dict | str:
        """
        Extract opening hours from the current restaurant page.

        Parses cards containing day and hours using CSS selectors and builds a
        mapping of day -> hours. Returns a dict when data is found or 'N/A' when
        elements are missing or not present.

        :return: Dictionary of opening hours by day, or 'N/A' if unavailable.
        :rtype: dict | str
        """
        try:
            hours_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.restaurant-details__components, section.section section-main:nth-of-type(3), div.card-borderline")
            if not hours_cards:
                return 'N/A'
            hours_dict = {}
            for card in hours_cards:
                try:
                    day = card.find_element(By.CSS_SELECTOR, "div.card--title").text.strip()
                    hours_elements = card.find_elements(By.CSS_SELECTOR, "div.card--content")

                    if day and hours_elements:
                        hours_list = [h.text.strip() for h in hours_elements if h.text.strip()]
                        hours_dict[day] = ", ".join(hours_list) if hours_list else "closed"

                except NoSuchElementException:
                    continue
            return hours_dict if hours_dict else 'N/A'

        except NoSuchElementException:
            return 'N/A'

    def extract_nearby_restaurants(self) -> list | str:
        """
        Extract up to 10 nearby restaurants from the current Michelin page.

        Scrolls to the bottom, locates the nearby restaurants section, and parses
        card elements to collect name and URL pairs.

        :return: A list of dicts with keys 'name' and 'url' when found, or 'N/A' if the section/cards are missing.
        :rtype: list | str
        """
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            try:
                nearby_heading = self.driver.find_element(By.XPATH, "//h2[contains(text(), 'Nearby Restaurants')]")
                nearby_container = nearby_heading.find_element(By.XPATH,
                                                               "./ancestor::div[contains(@class, 'container')]")
            except NoSuchElementException:
                return 'N/A'

            nearby_cards = nearby_container.find_elements(By.CSS_SELECTOR, "div.card__menu.selection-card")

            if not nearby_cards:
                return 'N/A'

            nearby_list = []
            for card in nearby_cards[:9]:
                try:
                    name_element = card.find_element(By.CSS_SELECTOR, "h3.card__menu-content--title a")
                    name = name_element.get_attribute('textContent').strip()
                    url = name_element.get_attribute('href')

                    try:
                        location_elements = card.find_elements(By.CSS_SELECTOR, "div.card__menu-footer--score")
                        location = location_elements[0].get_attribute('textContent').strip() if location_elements else 'N/A'
                    except:
                        location = 'N/A'
                    try:
                        price_cuisine_elements = card.find_elements(By.CSS_SELECTOR, "div.card__menu-footer--score")
                        if len(price_cuisine_elements) > 1:
                            price_cuisine = price_cuisine_elements[1].get_attribute('textContent').strip()
                            if '·' in price_cuisine:
                                parts = price_cuisine.split('·')
                                price = parts[0].strip()
                                cuisine = parts[1].strip()
                            else:
                                price = 'N/A'
                                cuisine = price_cuisine
                        else:
                            price = 'N/A'
                            cuisine = 'N/A'
                    except:
                        price = 'N/A'
                        cuisine = 'N/A'

                    try:
                        distinction_div = card.find_element(By.CSS_SELECTOR, "div.card__menu-content--distinction")
                        award_imgs = distinction_div.find_elements(By.CSS_SELECTOR, "img.michelin-award")

                        star_count = 0
                        distinction = 'None'

                        for img in award_imgs:
                            src = img.get_attribute('src')
                            if '1star' in src:
                                star_count += 1
                            elif 'bib-gourmand' in src:
                                distinction = 'Bib Gourmand'

                        if star_count > 0:
                            distinction = f'{star_count} star(s)'
                    except:
                        star_count = 0
                        distinction = 'None'

                    nearby_list.append({
                        'name': name,
                        'url': url,
                        'location': location,
                        'price': price,
                        'cuisine': cuisine,
                        'stars': star_count,
                        'distinction': distinction
                    })

                except Exception as e:
                    print(f"Erreur extraction restaurant nearby: {e}")
                    continue

            return nearby_list if nearby_list else 'N/A'

        except Exception as e:
            print(f"Erreur section nearby: {e}")
            return 'N/A'

    def extract_price_range(self) -> str:
        """
        Extract the restaurant's price range from the current Michelin page.

        Uses a CSS selector targeting the price element and returns trimmed text.
        Falls back to 'N/A' if the element is not found or any error occurs.

        :return: Price range text or 'N/A'.
        :rtype: str
        """
        try:
            price = self.driver.find_element(By.CSS_SELECTOR,"div.data-sheet__detail-info div.data-sheet__block > div.data-sheet__block--text:nth-of-type(2)").text
            price = price.split(" · ")
            return price[0]
        except:
            return 'N/A'

    def extract_cuisine_type(self) -> str:
        """
        Extract the cuisine type from the current Michelin restaurant page.

        Uses a CSS selector targeting the data-sheet content.
        Returns trimmed text if found, otherwise 'N/A'.

        :return: Cuisine type text or 'N/A'.
        :rtype: str
        """
        try:
            cuisine = self.driver.find_element(By.CSS_SELECTOR,"div.data-sheet__detail-info div.data-sheet__block > div.data-sheet__block--text:nth-of-type(2)").text
            cuisine = cuisine.split(" · ")
            return cuisine[1]
        except:
            return 'N/A'

    def extract_website(self) -> str:
        """
        Extract the restaurant's external website URL from the current Michelin page.

        :return: Website URL or 'N/A'.
        :rtype: str
        """
        try:
            website_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Visit Website')]")
            website_url = website_link.get_attribute('href')
            return website_url if website_url else 'N/A'
        except NoSuchElementException:
            try:
                website_link = self.driver.find_element(By.CSS_SELECTOR, "a[data-event='CTA_website']")
                website_url = website_link.get_attribute('href')
                return website_url if website_url else 'N/A'
            except:
                return 'N/A'

    def scrape_restaurant_details(self, url: str) -> dict:
        """
        Scrape detailed data for a single Michelin restaurant URL.

        Navigates to the given page with Selenium, waits briefly, and aggregates fields
        (address, phone, description, opening_hours, price_range, cuisine_type, website,
        facilities, nearby_restaurants) using dedicated extractors. Returns a dictionary
        with the collected data or an error payload if scraping fails.

        :param url: Restaurant page URL to scrape.
        :type url: str
        :return: Dictionary of scraped fields or {'url': url, 'error': message} on failure.
        :rtype: dict
        """
        print(f"\nScraping: {url}")

        try:
            self.driver.get(url)
            # time.sleep(3)

            details = {
                'url': url,
                'address': self.extract_address(),
                'phone': self.extract_phone(),
                'description': self.extract_description(),
                'opening_hours': self.extract_opening_hours(),
                'price_range': self.extract_price_range(),
                'cuisine_type': self.extract_cuisine_type(),
                'website': self.extract_website(),
                'tags': self.extract_tags(),
                'nearby_restaurants': self.extract_nearby_restaurants()
            }

            print(f"phone: {details.get('phone', 'N/A')}...")
            print(f"address: {details.get('address', 'N/A')[:50]}...")
            print(f"description: {details.get('description', 'N/A')[:50]}...")
            print(f"opening hours: {details.get('opening_hours', 'N/A')}...")
            print(f"price_range: {details.get('price_range', 'N/A')}...")
            print(f"cuisine_type: {details.get('cuisine_type', 'N/A')}...")
            print(f"tags: {details.get('tags', 'N/A')}")
            print(f"nearby_restaurants: {len(details.get('nearby_restaurants', ''))}")
            print(f"website: {details.get('website', 'N/A')}")
            return details

        except Exception as e:
            print(f"✗✗✗ Error: {e}")
            return {
                'url': url,
                'error': str(e)
            }

    def scrape_all_from_csv(self, csv_file: str, start_index: int=0, max_restaurants: int | None =None) -> list | None:
        """
        Batch-scrape restaurant details from a CSV of Michelin URLs.

        Reads the CSV via load_restaurants_from_csv, validates the presence of a 'url' column,
        filters invalid URLs, and iterates a slice defined by start_index and max_restaurants.
        For each URL, calls scrape_restaurant_details, enriches the result with CSV fields
        (name, location, stars, distinction), appends to restaurants_details, and throttles
        requests. Prints progress and returns the aggregated list.

        :param csv_file: Path to the input CSV containing at least a 'url' column.
        :type csv_file: str
        :param start_index: Zero-based index to start scraping from.
        :type start_index: int
        :param max_restaurants: Maximum number of rows to scrape; scrapes all if None.
        :type max_restaurants: int | None
        :return: List of scraped restaurant dictionaries; empty list if input invalid.
        :rtype: list | None
        """
        df = load_restaurants_from_csv(csv_file)

        if df is None or 'url' not in df.columns:
            print("Error: the CSV must have a column 'url'")
            return []

        df = df[df['url'].notna() & (df['url'] != 'N/A')]

        total = len(df)
        end_index = min(start_index + max_restaurants, total) if max_restaurants else total

        print(f"\n{'=' * 70}")
        print(f"Scraping of {end_index - start_index} restaurants (index {start_index} to {end_index - 1})")
        print(f"{'=' * 70}")

        for idx, row in df.iloc[start_index:end_index].iterrows():
            url = row['url']
            print(f"\n[{idx + 1}/{total}] ", end='')

            details = self.scrape_restaurant_details(url)
            details['name'] = row.get('name', 'N/A')
            details['location'] = row.get('location', 'N/A')
            details['stars'] = row.get('stars', 0)
            details['distinction'] = row.get('distinction', 'N/A')

            self.restaurants_details.append(details)
            # time.sleep(2)

        print(f"\n{'=' * 70}")
        print(f"Scraping finished: {len(self.restaurants_details)} restaurants")
        return self.restaurants_details

    def save_to_json(self, filename: str ='michelin_thailand_details.json') -> None:
        """
        Persist the aggregated restaurant details to a JSON file.

        Writes the in-memory restaurants_details list to the specified filename
        using UTF-8 encoding and pretty-printed JSON.

        :param filename: Output path for the JSON file. Defaults to 'michelin_thailand_details.json'.
        :type filename: str
        :return: None
        :rtype: None
        """
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.restaurants_details, f, ensure_ascii=False, indent=2)
        print(f"Data saved in {filename}")

    def save_to_csv(self, filename:str ='michelin_thailand_details.csv') -> None:
        """
        Export the aggregated restaurant details to a CSV file.

        Transforms nested fields for CSV compatibility:
        - opening_hours dict -> JSON string
        - facilities list -> semicolon-separated string
        - nearby_restaurants list -> JSON string

        Writes headers from the first record and saves using UTF-8 encoding. Prints a message
        and returns early if no data is available.

        :param filename: Output path for the CSV file. Defaults to 'michelin_thailand_details.csv'.
        :type filename: str
        :return: None
        :rtype: None
        """
        if not self.restaurants_details:
            print("No data to save")
            return

        flat_data = []
        for restaurant in self.restaurants_details:
            flat_restaurant = restaurant.copy()

            if isinstance(flat_restaurant.get('opening_hours'), dict):
                flat_restaurant['opening_hours'] = json.dumps(flat_restaurant['opening_hours'], ensure_ascii=False)
            if isinstance(flat_restaurant.get('tags'), list):
                flat_restaurant['tags'] = '; '.join(flat_restaurant['tags'])
            if isinstance(flat_restaurant.get('nearby_restaurants'), list):
                flat_restaurant['nearby_restaurants'] = json.dumps(flat_restaurant['nearby_restaurants'],
                                                                   ensure_ascii=False)

            flat_data.append(flat_restaurant)

        all_keys = set()
        for restaurant in flat_data:
            all_keys.update(restaurant.keys())

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            writer.writerows(flat_data)
        print(f"Saved in {filename}")


if __name__ == "__main__":
    scraper = MichelinDetailScraper(headless=True)

    try:
        restaurants = scraper.scrape_all_from_csv(
            csv_file='michelin_thailand.csv',
            start_index=0,
            max_restaurants=None
        )
        if scraper.restaurants_details:
            scraper.save_to_json()
            scraper.save_to_csv()

            print(f"\n{'=' * 70}")
            print(f"SUMMARY")
            print(f"{'=' * 70}")
            print(f"Total restaurants with details: {len(scraper.restaurants_details)}")

            with_tags = len([r for r in scraper.restaurants_details if
                             r.get('good_for_tags') and len(r.get('good_for_tags', [])) > 0])
            print(f"  - Restaurants with 'Good for' tags: {with_tags}")

    finally:
        del scraper