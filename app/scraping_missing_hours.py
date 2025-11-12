#!/usr/bin/env python3
from datetime import datetime

import pandas as pd
import json
import time
from typing import Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import argparse
import json



import re
from typing import Dict


def normalize(s: str) -> str:
    """
    Normalizes a given string by removing specific Unicode characters, replacing dashes with a uniform format, separating
    AM/PM from numeric values, standardizing delimiters, and trimming excess whitespace.

    Args:
        s (str): The string to be normalized.

    Returns:
        str: The normalized string.

    Raises:
        TypeError: If the provided input is not a string.
    """
    if not isinstance(s, str):
        return s
    s = s.replace("\u202f", "").replace("\u2009", "").replace("\u2013", "-").replace("\u2014", "-").replace("–",
                                                                                                            "-").replace(
        "—", "-")
    s = re.sub(r'(?i)(am|pm)(?=\d)', r'\1 ', s)
    s = re.sub(r'\s*[,/\\|]\s*', ',', s)
    s = re.sub(r'\s*-\s*', '-', s)
    return s.strip()


def parse_time(token: str, ref_ampm: str = None) -> str:
    """
    Parses a time token and converts it into a standardized 24-hour format.

    This function takes a time token in various formats (e.g., "12 AM", "3 PM", "24:00")
    and optionally uses a reference AM/PM indicator to resolve ambiguities. If the
    token matches the format for a valid time, the function returns it converted
    to the "HH:mm" 24-hour format. If parsing fails, the original token is returned
    unchanged.

    Args:
        token (str): The time string to be parsed, which may include an optional AM/PM
            designation or colon-separated hour and minutes.
        ref_ampm (str, optional): A reference indicator for AM or PM ("AM" or "PM")
            that disambiguates time tokens without explicit AM/PM.

    Returns:
        str: A string representing the parsed and converted time in 24-hour "HH:mm"
            format, or the unaltered input token if parsing fails.
    """
    token = token.strip().upper()
    if token in {"24", "24:00"}:
        return "24:00"
    m = re.match(r'^(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>AM|PM)?$', token)
    if not m:
        return token
    h = int(m.group('h'))
    minute = int(m.group('m') or "0")
    ampm = m.group('ampm') or ref_ampm
    if ampm:
        if ampm == 'AM':
            if h == 12:
                h = 0
        else:
            if h != 12:
                h += 12
    return f"{h:02d}:{minute:02d}"


def extract_ranges(text: str):
    """
    Extracts time ranges from a given text using a predefined regex pattern.

    This function utilizes a regular expression to identify and extract all time ranges
    present in the input text. Time ranges are expected to follow the format `<start>-<end>`,
    where `<start>` and `<end>` are time values in either 12-hour or 24-hour format,
    optionally including "AM/PM" indicators. The function is case-insensitive and returns
    all matches as a list of tuples.

    Args:
        text (str): The input string containing potential time ranges.

    Returns:
        list[tuple[str, str]]: A list of tuples, where each tuple contains two strings,
            representing the start and end of a time range respectively.
    """
    pattern = re.compile(r'(?P<start>\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*-\s*(?P<end>\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)', re.IGNORECASE)
    return pattern.findall(text)


def convert_hours_dict_to_24h(hours_dict: Dict[str, str]) -> Dict[str, str]:
    """
    Converts a dictionary of opening hours into a standardized 24-hour format.

    This function processes a dictionary containing opening hours data for specific
    days and converts it into a 24-hour format. If the hour information cannot be
    processed or is invalid, it will return as-is. For instances where the day is
    closed, it standardizes to a "Closed" status.

    Args:
        hours_dict (Dict[str, str]): A dictionary where keys are day names (e.g.,
            "Monday") and values are the opening hours in various formats or
            a special "closed" indicator.

    Returns:
        Dict[str, str]: A new dictionary with days as keys and standardized 24-hour
            format opening hours or "Closed" where applicable.
    """
    out = {}
    for day, raw in hours_dict.items():
        if not isinstance(raw, str):
            out[day] = raw
            continue
        text = normalize(raw)
        if text.lower() in {"closed", "ferme", "fermé"}:
            out[day] = "Closed"
            continue

        parts = re.split(r'\s*(?:,|/)\s*', text)
        normalized_ranges = []

        for part in parts:
            part = part.strip()
            if not part:
                continue
            pairs = extract_ranges(part)
            ampm_regex_two = r'(?i)(AM|PM)'
            ampm_regex_one = r'(?i)\s*(AM|PM)\s*'

            if pairs:
                last_ampm = None
                for start_tok, end_tok in pairs:
                    start_tok = start_tok.strip()
                    end_tok = end_tok.strip()

                    start_ampm = re.search(ampm_regex_two, start_tok)
                    end_ampm = re.search(ampm_regex_two, end_tok)
                    s_amp = start_ampm.group(1).upper() if start_ampm else None
                    e_amp = end_ampm.group(1).upper() if end_ampm else None
                    if s_amp and not e_amp:
                        e_amp = s_amp
                    elif e_amp and not s_amp:
                        s_amp = e_amp
                    elif not s_amp and not e_amp:
                        s_amp = e_amp = last_ampm
                    s_clean = re.sub(ampm_regex_one, '', start_tok).strip()
                    e_clean = re.sub(ampm_regex_one, '', end_tok).strip()

                    s_24 = parse_time(s_clean, s_amp)
                    e_24 = parse_time(e_clean, e_amp)

                    if e_24 == "00:00" and e_amp == "AM":
                        e_24 = "24:00"

                    normalized_ranges.append(f"{s_24}-{e_24}")
                    last_ampm = e_amp or last_ampm
            else:
                m = re.match(r'^(?P<s>\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*[-–]\s*(?P<e>\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)$', part, re.IGNORECASE)
                if m:
                    s, e = m.group('s'), m.group('e')


                    s_amp = re.search(ampm_regex_two, s)
                    e_amp = re.search(ampm_regex_two, e)
                    s_amp_v = s_amp.group(1).upper() if s_amp else None
                    e_amp_v = e_amp.group(1).upper() if e_amp else None
                    if s_amp_v and not e_amp_v:
                        e_amp_v = s_amp_v
                    elif e_amp_v and not s_amp_v:
                        s_amp_v = e_amp_v
                    s_clean = re.sub(ampm_regex_one, '', s).strip()
                    e_clean = re.sub(ampm_regex_one, '', e).strip()
                    s_24 = parse_time(s_clean, s_amp_v)
                    e_24 = parse_time(e_clean, e_amp_v)
                    if e_24 == "00:00" and e_amp_v == "AM":
                        e_24 = "24:00"
                    normalized_ranges.append(f"{s_24}-{e_24}")
                else:
                    normalized_ranges.append(part)

        out[day] = ", ".join(normalized_ranges) if normalized_ranges else text
    return out


class GoogleMapsHoursScraper:
    """Scrapes opening hours from Google Maps"""

    def __init__(self, headless: bool = True, driver_timeout: int = 10):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, driver_timeout)
        self.driver_timeout = driver_timeout

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

    def search_restaurant(self, name: str, location: Optional[str] = None) -> bool | None:
        """
        Search for a restaurant on Google Maps by name and optional location.

        This method performs a search query for a given restaurant name and optional
        location, navigates to Google Maps, and attempts to retrieve the URL of the
        restaurant's place page.

        Args:
            name: The name of the restaurant to search for.
            location: Optional; the location of the restaurant for more specific search results.

        Returns:
            bool: True for the restaurant's place page if found; otherwise, None.
        """
        try:
            query = f"{name} {location or ''} restaurant"
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            print(f"Searching: {search_url}")
            self.driver.get(search_url)

            time.sleep(4)

            current_url = self.driver.current_url
            if "maps/place" in current_url:
                print(f"Redirected directly to place page: {current_url}")
                return True

            place_url = self.driver.execute_script("""
                const a = document.querySelector("a[href*='maps/place']");
                return a ? a.href : null;
            """)
            if place_url:
                print(f"Found via JS: {place_url}")
                self.driver.get(place_url)
                time.sleep(3)
                return True

            print("\tNo valid place URL extracted")
            return None

        except Exception as e:
            print(f"\tSearch error: {e}")
            return None

    def extract_opening_hours(self):
        """
        Extracts the opening hours from a webpage.

        This method tries to extract opening hours information from a webpage by parsing
        an HTML table element with a specific class name. If the information is not immediately
        available, it simulates user interactions by clicking on a button to load additional
        content. Extracted hours are converted to a 24-hour format for consistency.

        Raises:
            Exception: If any error occurs during the HTML parsing or WebDriver interaction.

        Returns:
            dict or None: A dictionary containing days of the week as keys and their corresponding
            opening hours (in 24-hour format) as values, or None if no valid opening hours could
            be extracted.
        """
        try:
            time.sleep(2)
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            table = soup.find('table', class_='eK4R0e')

            if not table:
                print("No table found (class='eK4R0e')")
                try:
                    button = self.driver.find_element(By.CSS_SELECTOR, "button.CsEnBe[data-item-id='oh']")
                    print("buton found")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", button)
                    print("loading...")
                    time.sleep(4)
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "table.eK4R0e tr.y0skZc"))
                        )
                        print("New content")
                    except TimeoutException:
                        print("Timeout")
                    html = self.driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')

                    tables = soup.find_all('table', class_='eK4R0e')
                    if not tables:
                        print("\tNot table found (class='eK4R0e')")
                    if tables:
                        print("\tTable found (class='eK4R0e')")
                        table = tables[0]
                        hours = {}
                        rows = table.find_all('tr', class_='y0skZc')
                        for row in rows:
                            day_cell = row.find('td', class_='ylH6lf')
                            hours_cell = row.find('td', class_='mxowUb')
                            if not day_cell or not hours_cell:
                                continue

                            day = day_cell.get_text(strip=True)
                            time_range = hours_cell.get_text(strip=True)
                            hours[day] = time_range

                        if hours:
                            print("Hours extracted:")
                            hours = convert_hours_dict_to_24h(hours)
                            for d, t in hours.items():
                                print(f"    {d}: {t}")
                            return hours

                    print("No Hours after clicked")
                    return None

                except NoSuchElementException:
                    print("Buton not found")
                    return None

            hours = {}
            rows = table.find_all('tr', class_='y0skZc')
            for row in rows:
                day_cell = row.find('td', class_='ylH6lf')
                hours_cell = row.find('td', class_='mxowUb')
                if not day_cell or not hours_cell:
                    continue

                day = day_cell.get_text(strip=True)
                time_range = hours_cell.get_text(strip=True)
                hours[day] = time_range

            if hours:
                print("Extracted hours :")
                hours = convert_hours_dict_to_24h(hours)
                for d, t in hours.items():
                    print(f"    {d}: {t}")


                return hours
            else:
                print("Table found, but invalid")

        except Exception as e:
            print(f"Error: {e}")
            return None

    def scrape_hours_for_restaurant(self, name, location=None, address=None) -> Optional[dict]:
        """
        Scrapes the opening hours for a specified restaurant using its name and optional
        location or address.

        Args:
            name (str): The name of the restaurant being searched.
            location (Optional[str]): The location where the restaurant is expected
                to be found. Defaults to None.
            address (Optional[str]): The address of the restaurant as an alternative
                to the location. Defaults to None.

        Returns:
            Optional[dict]: A dictionary representing the opening hours of the
                restaurant if found, otherwise None.
        """
        print(f"\n{'=' * 70}")
        print(f"Processing: {name}")
        if location:
            print(f"Location: {location}")

        # Search for the restaurant
        place_url = self.search_restaurant(name, location or address)

        if not place_url:
            print('not place_url')
            return None

        # Extract hours
        hours = self.extract_opening_hours()
        print(f'hours {hours}')
        return hours


def identify_missing_hours(csv_path='./data/michelin_thailand_details.csv'):
    """
    Identifies and analyzes rows in a CSV file that are missing or contain invalid
    data in the 'opening_hours' column.

    Args:
        csv_path (str): Path to the CSV file containing the data. Defaults to
            './data/michelin_thailand_details.csv'.

    Returns:
        pandas.DataFrame: A DataFrame containing rows with missing or invalid
        'opening_hours'. If the 'opening_hours' column is not found, returns the
        original DataFrame unchanged.

    Raises:
        FileNotFoundError: If the specified `csv_path` does not exist.
        pd.errors.EmptyDataError: If the file is empty or does not contain valid data.
    """
    print("=" * 70)
    print("ANALYZING CSV FOR MISSING HOURS")
    print("=" * 70)

    df = pd.read_csv(csv_path)
    print(f"\nTotal restaurants: {len(df)}")

    if 'opening_hours' not in df.columns:
        print("No 'opening_hours' column found in CSV")
        return df

    missing_mask = (
            df['opening_hours'].isna() |
            (df['opening_hours'] == 'N/A') |
            (df['opening_hours'] == '') |
            (df['opening_hours'] == '{}')
    )

    missing_df = df[missing_mask].copy()

    print(f"Restaurants without hours: {len(missing_df)}")
    print(f"Percentage: {len(missing_df) / len(df) * 100:.1f}%")

    if len(missing_df) > 0:
        print("Sample of restaurants without hours:")
        print("-" * 70)
        for idx, row in missing_df.head(10).iterrows():
            location = row.get('location', 'N/A')
            print(f"  • {row['name']} - {location}")

    return missing_df


def scrape_missing_hours(
        csv_path='./data/michelin_thailand_details.csv',
        output_path='./data/michelin_thailand_details_updated.csv',
        max_restaurants=None,
        start_index=0
):
    """
    Scrape missing restaurant opening hours from Google Maps and update a CSV file.

    This function identifies restaurants missing opening hours in the given CSV file, scrapes the hours
    using Google Maps, and updates the file with the retrieved information. It allows specifying limits
    on the number of restaurants to process and the starting index for the processing.

    Args:
        csv_path: str. Path to the CSV file containing restaurant details.
        output_path: str. Path to save the updated CSV file with scraped opening hours.
        max_restaurants: Optional[int]. Maximum number of restaurants to process. If not specified,
            all restaurants from the start index onward are processed.
        start_index: int. Index from which to start processing restaurants. Defaults to 0.

    Returns:
        pandas.DataFrame: The updated DataFrame containing restaurant details with updated opening
            hours.
    """
    missing_df = identify_missing_hours(csv_path)

    if len(missing_df) == 0:
        print("All restaurants have opening hours!")
        return

    if max_restaurants:
        missing_df = missing_df.iloc[start_index:start_index + max_restaurants]
    else:
        missing_df = missing_df.iloc[start_index:]

    print(f"\n{'=' * 70}")
    print("SCRAPING HOURS FROM GOOGLE MAPS")
    print(f"{'=' * 70}")
    print(f"Processing {len(missing_df)} restaurants (starting from index {start_index})")
    print("This may take several minutes...")

    scraper = GoogleMapsHoursScraper(headless=True)

    scraped_hours = {}

    for idx, (orig_idx, row) in enumerate(missing_df.iterrows(), 1):
        print(f"\n[{idx}/{len(missing_df)}] ", end='')

        name = row.get('name', '')
        location = row.get('location', None)
        location = location.split(',')[0] if isinstance(location, str) else location
        address = row.get('address', None)

        if not name:
            print("Skipping - no name")
            continue

        try:
            hours = scraper.scrape_hours_for_restaurant(name, location, address)

            if hours:
                scraped_hours[orig_idx] = hours
                print("Success")
            else:
                print("Failed")

        except Exception as e:
            print(f"Error: {e}")
            continue

    del scraper

    print(f"\n{'=' * 70}")
    print("UPDATING CSV")
    print(f"{'=' * 70}")

    df = pd.read_csv(csv_path)

    for idx, hours in scraped_hours.items():
        if isinstance(hours, dict):
            df.at[idx, 'opening_hours'] = json.dumps(hours)
        else:
            df.at[idx, 'opening_hours'] = str(hours)

    df.to_csv(output_path, index=False, encoding='utf-8')

    print(f"\n\n\nUpdated CSV saved to: {output_path}")
    print(f"Successfully scraped: {len(scraped_hours)} restaurants")

    still_missing = df['opening_hours'].isna() | (df['opening_hours'] == 'N/A') | (df['opening_hours'] == '')
    print(f"Still missing hours: {still_missing.sum()}")
    print(f"Coverage: {(1 - still_missing.sum() / len(df)) * 100:.1f}%")

    return df


def show_statistics(csv_path='michelin_thailand_details.csv'):
    """
    Displays statistics about restaurant opening hours from a CSV file.

    The function reads a CSV file containing restaurant details and computes statistics
    on the presence and format of the `opening_hours` column. It also samples and displays
    a few entries with detailed opening hours in dictionary format.

    Args:
        csv_path (str): Path to the CSV file containing restaurant data. Defaults to
            'michelin_thailand_details.csv'.
    """
    df = pd.read_csv(csv_path)

    print("\n" + "=" * 70)
    print("OPENING HOURS STATISTICS")
    print("=" * 70)

    if 'opening_hours' not in df.columns:
        print("No 'opening_hours' column found")
        return

    total = len(df)

    has_hours = ~(df['opening_hours'].isna() | (df['opening_hours'] == 'N/A') | (df['opening_hours'] == ''))
    has_dict_hours = df['opening_hours'].apply(lambda x: str(x).startswith('{') if pd.notna(x) else False)

    print(f"\nTotal restaurants: {total}")
    print(f"With hours: {has_hours.sum()} ({has_hours.sum() / total * 100:.1f}%)")
    print(f"With detailed hours (dict): {has_dict_hours.sum()} ({has_dict_hours.sum() / total * 100:.1f}%)")
    print(f"Without hours: {(~has_hours).sum()} ({(~has_hours).sum() / total * 100:.1f}%)")

    if has_dict_hours.sum() > 0:
        print("\nSample restaurants with hours:")
        print("-" * 70)
        for idx, row in df[has_dict_hours].head(3).iterrows():
            print(f"\n\t- {row['name']}")
            try:
                hours = json.loads(row['opening_hours'])
                for day, time in list(hours.items())[:3]:
                    print(f"\t{day}: {time}")
            except:
                print(f"\t{row['opening_hours'][:100]}")


def main():

    parser = argparse.ArgumentParser(description='Scrape missing opening hours from Google Maps')
    parser.add_argument(
        '--csv',
        default='./data/michelin_thailand_details.csv',
        help='Input CSV file path'
    )
    parser.add_argument(
        '--output',
        default='./data/michelin_thailand_details_updated.csv',
        help='Output CSV file path'
    )
    parser.add_argument(
        '--max',
        type=int,
        default=None,
        help='Maximum number of restaurants to scrape'
    )
    parser.add_argument(
        '--start',
        type=int,
        default=0,
        help='Start index for scraping'
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Only show statistics, do not scrape'
    )

    args = parser.parse_args()

    if args.stats_only:
        identify_missing_hours(args.csv)
        show_statistics(args.csv)
    else:
        scrape_missing_hours(
            csv_path=args.csv,
            output_path=args.output,
            max_restaurants=args.max,
            start_index=args.start
        )
        show_statistics(args.output)


if __name__ == "__main__":
    main()