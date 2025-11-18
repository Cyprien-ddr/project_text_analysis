import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime, time

import spacy
import pandas as pd

try:
    nlp = spacy.load("en_core_web_sm")
    print("SpaCy model loaded successfully")
except OSError:
    print("spaCy model not found. Installing...")
    import subprocess

    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


def check_days(detected_days: list[str], opening_hours: dict[str, str], detected_times: list[time], detected_meal_periods: list[str], total_checks: int = 0, day_matched: int = 0):
    """
    Checks the given detected days against the provided opening hours to determine matches
    and accumulate total checks and matched days.

    This function evaluates if the provided detected days can be matched with the opening
    hours under the conditions where no detected times or meal periods are given. It
    increments the count for the total checks and, when a match is found, the day matched
    count is updated. A match occurs if the day's opening hours are not marked as 'closed'
    or 'n/a'.

    Args:
        detected_days (list[str]): List of detected days to be checked.
        opening_hours (dict[str, str]): Dictionary mapping days to their opening hours.
        detected_times (list[time]): List of times detected, which must be empty for this
            function to proceed with checking.
        detected_meal_periods (list[str]): List of meal periods detected, which must be
            empty for this function to proceed with checking.
        total_checks (int): Counter for the total number of checks performed. Defaults to 0.
        day_matched (int): Counter for the number of days matched. Defaults to 0.

    Returns:
        tuple: A tuple containing two integers:
            - The total number of checks performed.
            - The number of days matched.
    """
    if detected_days and not detected_times and not detected_meal_periods:
        total_checks += len(detected_days)
        for day in detected_days:
            if day in opening_hours:
                hours_str = opening_hours[day]
                if hours_str and hours_str.lower() not in ['closed', 'n/a']:
                    print('day matched')
                    day_matched += 1
    return total_checks, day_matched

def check_times(detected_times, opening_hours, detected_days, total_checks,
                day_matched):
    """
    Checks if the detected times fall within the opening hours for the specified days.

    This function iterates over the given detected times and checks if they fall
    within the specified opening hours for each day. It handles cases where
    opening hours are marked as 'closed' or 'n/a', and only evaluates days that
    exist within the opening hours. Days can either be explicitly provided in
    detected_days or default to all days in the opening_hours dictionary.
    The function increments the total number of checks performed and the count
    of times a match is found.

    Args:
        detected_times (list[datetime.time]): A list of detected time instances
            to be checked against opening hours.
        opening_hours (dict[str, str]): A dictionary mapping days of the week
            to their respective opening hours. Opening hours should be
            formatted as 'HH:MM-HH:MM'. A value of 'closed' or 'n/a' indicates
            the establishment is not open on that day.
        detected_days (list[str] | None): An optional list of days of the week
            to check. If None, checks all days in the opening_hours dictionary.
        total_checks (int): A counter for the total number of checks performed
            across all detected times and days.
        day_matched (int): A counter tracking the number of times a detected
            time falls within the specified opening hours.

    Returns:
        tuple[int, int]: A tuple containing the updated values of total_checks
            and day_matched. The first element (int) is the updated total_checks,
            and the second element (int) is the updated day_matched.
    """
    for detected_time in detected_times:
        total_checks += 1
        days_to_check = detected_days if detected_days else opening_hours.keys()
        for day in days_to_check:
            if day not in opening_hours:
                continue
            hours_str = opening_hours[day]
            if not hours_str or hours_str.lower() in ['closed', 'n/a']:
                continue
            if '-' in hours_str:
                try:
                    start_str, end_str = hours_str.split('-')
                    start_hour, start_min = map(int, start_str.split(':'))
                    end_hour, end_min = map(int, end_str.split(':'))
                    start_time = time(start_hour, start_min)
                    end_time = time(end_hour, end_min)
                    if start_time <= detected_time <= end_time:
                        day_matched += 1
                        break
                except:
                    continue
    return total_checks, day_matched

class TemporalLocationDetector:
    """
    Detects temporal expressions (days, times, meal periods) and locations in queries.

    Uses spaCy NER for location detection and pattern matching for temporal expressions.
    """

    DAYS = {
        'monday': 'Monday', 'mon': 'Monday',
        'tuesday': 'Tuesday', 'tue': 'Tuesday', 'tues': 'Tuesday',
        'wednesday': 'Wednesday', 'wed': 'Wednesday',
        'thursday': 'Thursday', 'thu': 'Thursday', 'thur': 'Thursday', 'thurs': 'Thursday',
        'friday': 'Friday', 'fri': 'Friday',
        'saturday': 'Saturday', 'sat': 'Saturday',
        'sunday': 'Sunday', 'sun': 'Sunday',
    }

    MEAL_PERIODS = {
        'breakfast': (time(6, 0), time(11, 0)),
        'brunch': (time(10, 0), time(14, 0)),
        'lunch': (time(11, 0), time(15, 0)),
        'dinner': (time(17, 0), time(23, 0)),
        'late night': (time(22, 0), time(2, 0)),
    }

    MEAL_KEYWORDS = {
        'breakfast': ['breakfast', 'morning'],
        'brunch': ['brunch'],
        'lunch': ['lunch', 'lunchtime', 'midday', 'noon'],
        'dinner': ['dinner', 'evening', 'supper'],
        'late night': ['late night', 'midnight'],
    }

    def __init__(self):
        """Initialize the detector with spaCy model."""
        self.nlp = nlp

    def detect_days(self, query: str) -> List[str]:
        """
        Detect day names in the query.

        Args:
            query: Input text

        Returns:
            List of detected day names (capitalized)
        """
        query_lower = query.lower()
        detected_days = []

        for key, day in self.DAYS.items():
            if re.search(rf'\b{key}\b', query_lower):
                if day not in detected_days:
                    detected_days.append(day)

        if re.search(r'\bweekend\b', query_lower):
            detected_days.extend(['Saturday', 'Sunday'])

        if re.search(r'\bweekday\b', query_lower):
            detected_days.extend(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])

        seen = set()
        result = []
        for day in detected_days:
            if day not in seen:
                seen.add(day)
                result.append(day)

        return result

    def detect_times(self, query: str) -> List[time]:
        """
        Detect time expressions in the query.

        Supports formats:
        - 9am, 10pm
        - 9:00, 18:00
        - 9:30am, 6:30pm

        Args:
            query: Input text

        Returns:
            List of time objects
        """
        times = []

        pattern1 = r'\b(\d{1,2})\s*([ap]m)\b'
        for match in re.finditer(pattern1, query.lower()):
            hour = int(match.group(1))
            period = match.group(2)

            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0

            if 0 <= hour < 24:
                times.append(time(hour, 0))

        pattern2 = r'\b(\d{1,2}):(\d{2})\b'
        for match in re.finditer(pattern2, query):
            hour = int(match.group(1))
            minute = int(match.group(2))

            if 0 <= hour < 24 and 0 <= minute < 60:
                times.append(time(hour, minute))

        pattern3 = r'\b(\d{1,2}):(\d{2})\s*([ap]m)\b'
        for match in re.finditer(pattern3, query.lower()):
            hour = int(match.group(1))
            minute = int(match.group(2))
            period = match.group(3)

            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0

            if 0 <= hour < 24 and 0 <= minute < 60:
                times.append(time(hour, minute))

        return times

    def detect_meal_periods(self, query: str) -> List[str]:
        """
        Detect meal period keywords in the query.

        Args:
            query: Input text

        Returns:
            List of meal periods (breakfast, lunch, dinner, etc.)
        """
        query_lower = query.lower()
        detected_periods = []

        for period, keywords in self.MEAL_KEYWORDS.items():
            for keyword in keywords:
                if re.search(rf'\b{keyword}\b', query_lower):
                    if period not in detected_periods:
                        detected_periods.append(period)
                    break

        return detected_periods

    def detect_locations(self, query: str) -> List[str]:
        """
        Detect location entities using spaCy NER.

        Args:
            query: Input text

        Returns:
            List of detected location names
        """
        doc = self.nlp(query)
        locations = []

        for ent in doc.ents:
            if ent.label_ in ['GPE',]:
                locations.append(ent.text)

        return locations

    def detect_all(self, query: str) -> Dict:
        """
        Detect all temporal and location information from query.

        Args:
            query: Input text

        Returns:
            Dictionary with detected information:
            {
                'days': list of day names,
                'times': list of time objects,
                'meal_periods': list of meal periods,
                'locations': list of location names
            }
        """
        return {
            'days': self.detect_days(query),
            'times': self.detect_times(query),
            'meal_periods': self.detect_meal_periods(query),
            'locations': self.detect_locations(query)
        }

    def check_restaurant_hours(
            self,
            opening_hours: dict[str, str],
            detected_days: list[str],
            detected_times: list[time],
            detected_meal_periods: list[str]
    ) -> Tuple[bool, float]:
        """
        Check if restaurant hours match the query requirements.

        Args:
            opening_hours: Restaurant opening hours dict {"Monday": "09:00-21:00", ...}
            detected_days: List of detected day names
            detected_times: List of detected time objects
            detected_meal_periods: List of meal periods

        Returns:
            Tuple of (is_match: bool, confidence_score: float)
        """
        if not opening_hours or opening_hours == 'N/A':
            return False, 0.0

        if isinstance(opening_hours, str):
            try:
                import json
                opening_hours = json.loads(opening_hours)
            except:
                return False, 0.0

        total_checks, day_matched = check_days(detected_days, opening_hours, detected_times, detected_meal_periods)
        if detected_times:
            total_checks, day_matched = check_times(detected_times, opening_hours, detected_days, total_checks, day_matched)
        if detected_meal_periods and not detected_times:
            total_checks, day_matched = self.check_periods(detected_meal_periods, opening_hours, detected_days, total_checks, day_matched)
        if total_checks == 0:
            return False, 0.0
        confidence = day_matched / total_checks
        return confidence > 0.5, confidence

    def check_periods(self, detected_meal_periods, opening_hours, detected_days, total_checks, day_matched):
        for meal_period in detected_meal_periods:
            total_checks += 1
            if meal_period not in self.MEAL_PERIODS:
                continue
            meal_start, meal_end = self.MEAL_PERIODS[meal_period]
            days_to_check = detected_days if detected_days else opening_hours.keys()
            for day in days_to_check:
                if day not in opening_hours:
                    continue
                hours_str = opening_hours[day]
                if not hours_str or hours_str.lower() in ['closed', 'n/a']:
                    continue
                if '-' in hours_str:
                    try:
                        start_str, end_str = hours_str.split('-')
                        start_hour, start_min = map(int, start_str.split(':'))
                        end_hour, end_min = map(int, end_str.split(':'))

                        rest_start = time(start_hour, start_min)
                        rest_end = time(end_hour, end_min)
                        if not (meal_end < rest_start or meal_start > rest_end):
                            day_matched += 1
                            break
                    except:
                        continue
        return total_checks, day_matched



import ast

if __name__ == "__main__":
    # detector = TemporalLocationDetector()
    #
    # test_queries = [
    #     "Find me a lunch spot in Bangkok",
    #     "Dinner reservations for Friday at 7pm",
    #     "Open on Monday morning around 9am",
    #     "Weekend brunch in Phuket",
    #     "Late night dinner in Chiang Mai",
    #     "Looking for breakfast places on Tuesday",
    # ]
    #
    # print("=" * 70)
    # print("TEMPORAL AND LOCATION DETECTION EXAMPLES")
    # print("=" * 70)
    #
    # for query in test_queries:
    #     print(f"\nQuery: '{query}'")
    #     result = detector.detect_all(query)
    #     print(f"  Days: {result['days']}")
    #     print(f"  Times: {[t.strftime('%H:%M') for t in result['times']]}")
    #     print(f"  Meal periods: {result['meal_periods']}")
    #     print(f"  Locations: {result['locations']}")
    #
    # print("\n" + "=" * 70)
    # print("OPENING HOURS MATCHING TEST")
    # print("=" * 70)
    #
    # sample_hours = {
    #     "Monday": "09:00-21:00",
    #     "Tuesday": "09:00-21:00",
    #     "Wednesday": "09:00-21:00",
    #     "Thursday": "09:00-21:00",
    #     "Friday": "09:00-21:00",
    #     "Saturday": "12:00-22:00",
    #     "Sunday": "closed"
    # }
    #
    # test_cases = [
    #     ("lunch on Monday", sample_hours),
    #     ("dinner at 8pm Friday", sample_hours),
    #     ("breakfast on Sunday", sample_hours),
    #     ("breakfast on Sat", sample_hours),
    # ]
    #
    # for query, hours in test_cases:
    #     print(f"\nQuery: '{query}'")
    #     info = detector.detect_all(query)
    #     is_match, score = detector.check_restaurant_hours(
    #         hours,
    #         info['days'],
    #         info['times'],
    #         info['meal_periods']
    #     )
    #     print(f"  Match: {is_match}, Score: {score:.2f}")

    temporal_detector = TemporalLocationDetector()

    temporal_info = temporal_detector.detect_all("regional rustic and immersive thai food tuesday dinner")
    detected_days = temporal_info['days']
    detected_times = temporal_info['times']
    detected_meal_periods = temporal_info['meal_periods']
    detected_locations = temporal_info['locations']
    hours_score = -1.0
    hours_match = False
    df = pd.read_csv('./data/michelin_thailand_details.csv')

    # Trouver la ligne où name == 'AKKEE'
    akkee_row = df[df['name'] == 'La Voi']

    print(temporal_detector.detect_locations(akkee_row.iloc[0]['address']))
    for idx in range(len(df)):
        adresse = df.loc[idx, 'address']
        match = re.search(r",\s*([^,]+),\s*\d{3,10},\s*[^,]+$", adresse)
        if match:
            df.loc[idx, 'city'] = match.group(1).strip()
            print(df.loc[idx, 'city'])
        else:
            df.loc[idx, 'city'] = None
        # if match:
        #     city = match.group(1).strip()
        #     print(city)
    # match = re.search(r",\s*([^,]+),\s*\d{5},\s*[^,]+$", akkee_row.iloc[0]['address'])
    # if match:
    #     ville = match.group(1).strip()
    #     print(ville)
    # # Extraire opening_hours (première occurrence si plusieurs)
    # opening_hours = None
    # if not akkee_row.empty:
    #     opening_hours = akkee_row.iloc[0]['opening_hours']
    #
    # print(opening_hours)
    # print(type(opening_hours))
    # opening_hours = ast.literal_eval(opening_hours)
    # print(opening_hours)
    # print(type(opening_hours))
    # if detected_days or detected_times or detected_meal_periods:
    #     # opening_hours = row.get('opening_hours', 'N/A')
    #     # opening_hours = {""Monday"": ""17:30-23:00"", ""Tuesday"": ""17:30-23:00"", ""Wednesday"": ""closed"", ""Thursday"": ""17:30-23:00"", ""Friday"": ""17:30-23:00"", ""Saturday"": ""12:00-15:00, 17:30-23:00"", ""Sunday"": ""12:00-15:00, 17:30-23:00""}
    #     if opening_hours and opening_hours != 'N/A':
    #         print("in")
    #         if isinstance(opening_hours, str):
    #             print("str")
    #             import json
    #
    #             try:
    #                 opening_hours = json.loads(opening_hours.replace('""', '"'))
    #             except:
    #                 opening_hours = None
    #         # if opening_hours is dict:
    #         if isinstance(opening_hours, dict):
    #             print("dict")
    #             print(f'opening_hours: {opening_hours}')
    #             hours_match, hours_score = temporal_detector.check_restaurant_hours(
    #                 opening_hours,
    #                 detected_days,
    #                 detected_times,
    #                 detected_meal_periods
    #             )
    #             hours_score = 1 if hours_match == True else -1
    #         else:
    #             print(f"else: {type(opening_hours)}")
    # print(hours_score, hours_match)
    # print(detected_days, detected_times, detected_meal_periods, detected_locations)
    # print(
    #     f"Is match: {hours_match}, Score: {hours_score:.2f}"
    # )