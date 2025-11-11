#!/usr/bin/env python3
"""
Temporal and Location Detection Module using spaCy

Detects:
- Days of the week (Monday, Tuesday, etc.)
- Times (9am, 18:00, etc.)
- Meal periods (lunch, dinner, breakfast, brunch)
- Locations (Bangkok, Phuket, etc.)
"""

import re
from datetime import datetime, time
from typing import Dict, List, Tuple, Optional
import spacy

# Try to load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
    print("✓ spaCy model loaded successfully")
except OSError:
    print("⚠️  spaCy model not found. Installing...")
    import subprocess

    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


class TemporalLocationDetector:
    """
    Detects temporal expressions (days, times, meal periods) and locations in queries.

    Uses spaCy NER for location detection and pattern matching for temporal expressions.
    """

    # Day name mappings
    DAYS = {
        'monday': 'Monday', 'mon': 'Monday',
        'tuesday': 'Tuesday', 'tue': 'Tuesday', 'tues': 'Tuesday',
        'wednesday': 'Wednesday', 'wed': 'Wednesday',
        'thursday': 'Thursday', 'thu': 'Thursday', 'thur': 'Thursday', 'thurs': 'Thursday',
        'friday': 'Friday', 'fri': 'Friday',
        'saturday': 'Saturday', 'sat': 'Saturday',
        'sunday': 'Sunday', 'sun': 'Sunday',
    }

    # Meal period time ranges
    MEAL_PERIODS = {
        'breakfast': (time(6, 0), time(11, 0)),
        'brunch': (time(10, 0), time(14, 0)),
        'lunch': (time(11, 0), time(15, 0)),
        'dinner': (time(17, 0), time(23, 0)),
        'late night': (time(22, 0), time(2, 0)),
    }

    # Additional meal period keywords
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

        # Also detect "weekend", "weekday", "weekdays", "weekends"
        if re.search(r'\bweekend\b', query_lower):
            detected_days.extend(['Saturday', 'Sunday'])

        if re.search(r'\bweekday\b', query_lower):
            detected_days.extend(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])

        # Remove duplicates while preserving order
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

        # Pattern 1: 9am, 10pm
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

        # Pattern 2: 9:00, 18:00
        pattern2 = r'\b(\d{1,2}):(\d{2})\b'
        for match in re.finditer(pattern2, query):
            hour = int(match.group(1))
            minute = int(match.group(2))

            if 0 <= hour < 24 and 0 <= minute < 60:
                times.append(time(hour, minute))

        # Pattern 3: 9:30am, 6:30pm
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
            if ent.label_ in ['GPE', 'LOC', 'FAC']:  # Geopolitical entity, Location, Facility
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

        # Parse opening_hours if it's a string
        if isinstance(opening_hours, str):
            try:
                import json
                opening_hours = json.loads(opening_hours)
            except:
                return False, 0.0

        total_checks = 0
        matched_checks = 0

        # Check days
        if detected_days:
            total_checks += len(detected_days)
            for day in detected_days:
                if day in opening_hours:
                    hours_str = opening_hours[day]
                    if hours_str and hours_str.lower() not in ['closed', 'n/a']:
                        matched_checks += 1

        # Check times
        if detected_times:
            for detected_time in detected_times:
                total_checks += 1

                # Check all days or specific detected days
                days_to_check = detected_days if detected_days else opening_hours.keys()

                for day in days_to_check:
                    if day not in opening_hours:
                        continue

                    hours_str = opening_hours[day]
                    if not hours_str or hours_str.lower() in ['closed', 'n/a']:
                        continue

                    # Parse time range: "09:00-21:00"
                    if '-' in hours_str:
                        try:
                            start_str, end_str = hours_str.split('-')
                            start_hour, start_min = map(int, start_str.split(':'))
                            end_hour, end_min = map(int, end_str.split(':'))

                            start_time = time(start_hour, start_min)
                            end_time = time(end_hour, end_min)

                            # Check if detected time is within range
                            if start_time <= detected_time <= end_time:
                                matched_checks += 1
                                break
                        except:
                            continue

        # Check meal periods
        if detected_meal_periods:
            for meal_period in detected_meal_periods:
                total_checks += 1

                if meal_period not in self.MEAL_PERIODS:
                    continue

                meal_start, meal_end = self.MEAL_PERIODS[meal_period]

                # Check if restaurant is open during this meal period
                days_to_check = detected_days if detected_days else opening_hours.keys()

                for day in days_to_check:
                    if day not in opening_hours:
                        continue

                    hours_str = opening_hours[day]
                    if not hours_str or hours_str.lower() in ['closed', 'n/a']:
                        continue

                    # Parse time range
                    if '-' in hours_str:
                        try:
                            start_str, end_str = hours_str.split('-')
                            start_hour, start_min = map(int, start_str.split(':'))
                            end_hour, end_min = map(int, end_str.split(':'))

                            rest_start = time(start_hour, start_min)
                            rest_end = time(end_hour, end_min)

                            # Check if meal period overlaps with restaurant hours
                            if not (meal_end < rest_start or meal_start > rest_end):
                                matched_checks += 1
                                break
                        except:
                            continue

        if total_checks == 0:
            return False, 0.0

        confidence = matched_checks / total_checks
        is_match = confidence > 0.5  # At least 50% of checks must pass

        return is_match, confidence


if __name__ == "__main__":
    detector = TemporalLocationDetector()

    test_queries = [
        "Find me a lunch spot in Bangkok",
        "Dinner reservations for Friday at 7pm",
        "Open on Monday morning around 9am",
        "Weekend brunch in Phuket",
        "Late night dinner in Chiang Mai",
        "Looking for breakfast places on Tuesday",
    ]

    print("=" * 70)
    print("TEMPORAL AND LOCATION DETECTION EXAMPLES")
    print("=" * 70)

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        result = detector.detect_all(query)
        print(f"  Days: {result['days']}")
        print(f"  Times: {[t.strftime('%H:%M') for t in result['times']]}")
        print(f"  Meal periods: {result['meal_periods']}")
        print(f"  Locations: {result['locations']}")

    print("\n" + "=" * 70)
    print("OPENING HOURS MATCHING TEST")
    print("=" * 70)

    sample_hours = {
        "Monday": "09:00-21:00",
        "Tuesday": "09:00-21:00",
        "Wednesday": "09:00-21:00",
        "Thursday": "09:00-21:00",
        "Friday": "09:00-21:00",
        "Saturday": "09:00-22:00",
        "Sunday": "09:00-21:00"
    }

    test_cases = [
        ("lunch on Monday", sample_hours),
        ("dinner at 8pm Friday", sample_hours),
        ("breakfast on Sunday", sample_hours),
    ]

    for query, hours in test_cases:
        print(f"\nQuery: '{query}'")
        info = detector.detect_all(query)
        is_match, score = detector.check_restaurant_hours(
            hours,
            info['days'],
            info['times'],
            info['meal_periods']
        )
        print(f"  Match: {is_match}, Score: {score:.2f}")