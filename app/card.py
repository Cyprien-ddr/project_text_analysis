import pandas as pd

from textual.app import App, ComposeResult
from textual.widgets import Static


class RestaurantCard(Static):
    """
    Represents a visual display card for restaurant information.

    This class is responsible for creating detailed and visually styled information cards
    for restaurants. The cards include various details such as rank, name, awards, location,
    cuisine type, pricing, description, predicted tags, contact information, temporal matching
    info, and score metrics.

    Attributes:
        restaurant (dict): A dictionary of restaurant data containing metadata such as name,
            location, cuisine details, pricing, etc.
        rank (int): The ranking position of the restaurant.
        score (float): The overall score assigned to the restaurant based on various factors.
        semantic_score (float, optional): A sub-score measuring semantic relevance.
        tag_score (float, optional): A sub-score representing the relevance of matched tags.
        matched_tags (dict, optional): A dictionary of predicted tags with associated relevance scores.
        food_detected (bool, optional): Indicates if food-related features were detected.
        food_score (float, optional): A sub-score representing food-related attributes.
        hours_score (float, optional): A sub-score for temporal matching (days/times/meal periods).
        hours_match (bool, optional): Whether the restaurant matches temporal requirements.
        temporal_info (dict, optional): Detected temporal information (days, times, meal periods).
        location_score (float, optional): A sub-score for location matching.
        detected_locations (list, optional): List of detected location names from query.
    """

    def __init__(
            self,
            restaurant_data,
            rank,
            score,
            semantic_score=None,
            tag_score=None,
            matched_tags=None,
            food_detected=None,
            food_score=None,
            hours_score=None,
            hours_match=None,
            temporal_info=None,
            location_score=None,
            detected_locations=None
    ):
        super().__init__()
        self.restaurant = restaurant_data
        self.rank = rank
        self.score = score
        self.semantic_score = semantic_score
        self.tag_score = tag_score
        self.matched_tags = matched_tags or {}
        self.food_detected = food_detected
        self.food_score = food_score
        self.hours_score = hours_score
        self.hours_match = hours_match
        self.temporal_info = temporal_info or {}
        self.location_score = location_score
        self.detected_locations = detected_locations or []

    def compose(self) -> ComposeResult:
        """
        Generates a styled information card about a restaurant.

        This method constructs a composable result object to display detailed information about a
        restaurant based on its attributes such as rank, name, distinctions (e.g., Michelin stars),
        location, cuisine, pricing, description, tags, contact details, temporal matching info,
        and associated scores. The output is visually enhanced with symbols and icons for better
        readability.

        Returns:
            ComposeResult: A composable result instance representing the formatted content of the
                restaurant's details, styled for display purposes.
        """
        row = self.restaurant

        title = f"{self.rank}. {row['name']}"

        distinction = row.get('distinction', '')
        distinction_display = ''
        if pd.notna(distinction):
            dist_str = str(distinction).lower()
            if '3 star' in dist_str:
                distinction_display = '⭐⭐⭐ 3 stars'
            elif '2 star' in dist_str:
                distinction_display = '⭐⭐ 2 stars'
            elif '1 star' in dist_str:
                distinction_display = '⭐ 1 star'
            elif 'bib gourmand' in dist_str:
                distinction_display = '🍴 Bib Gourmand'

        info_parts = []
        if pd.notna(row.get('location')):
            info_parts.append(f"📍 {row['location']}")
        if pd.notna(row.get('cuisine')):
            info_parts.append(f"🍽️ {row['cuisine']}")
        if pd.notna(row.get('price')):
            info_parts.append(f"💰 {row['price']}")
        if pd.notna(row.get('tags')):
            info_parts.append(f'🏷️ {row["tags"]}')

        info_line = " • ".join(info_parts)

        description = ""
        if pd.notna(row.get('description')):
            description = str(row['description'])[:200]

        tags_display = ""
        if self.matched_tags:
            tag_list = [f"{tag} ({score:.2f})" for tag, score in
                        sorted(self.matched_tags.items(), key=lambda x: x[1], reverse=True)]
            tags_display = f"\n🎯 Predicted: {', '.join(tag_list[:5])}"

        temporal_display = ""
        if self.temporal_info:
            temporal_parts = []
            if self.temporal_info.get('days'):
                temporal_parts.append(f"📅 {', '.join(self.temporal_info['days'])}")
            if self.temporal_info.get('times'):
                temporal_parts.append(f"🕐 {', '.join(self.temporal_info['times'])}")
            if self.temporal_info.get('meal_periods'):
                temporal_parts.append(f"🍴 {', '.join(self.temporal_info['meal_periods'])}")

            if temporal_parts:
                match_indicator = "✓" if self.hours_match else "✗"
                temporal_display = f"\n{match_indicator} Temporal: {' | '.join(temporal_parts)}"
        location_display = ""
        if self.detected_locations and self.location_score > 0:
            location_display = f"\n📍 Location match: {', '.join(self.detected_locations)}"

        contact_parts = []
        if pd.notna(row.get('phone')):
            contact_parts.append(f"📞 {row['phone']}")
        if pd.notna(row.get('website')):
            contact_parts.append(f"🌐 {row['website']}")
        contact_line = " • ".join(contact_parts)

        score_parts = [f"Total: {self.score:.3f}"]
        if self.semantic_score is not None:
            score_parts.append(f"Semantic: {self.semantic_score:.3f}")
        if self.tag_score is not None and self.tag_score != 0:
            score_parts.append(f"Tags: {self.tag_score:.3f}")
        if self.food_score is not None and self.food_score != 0:
            score_parts.append(f"Food: {self.food_score:.3f}")
        if self.hours_score != 0:
            score_parts.append(f"Hours: {self.hours_score:.3f}")
        if self.location_score is not None and self.location_score != 0:
            score_parts.append(f"Location: {self.location_score:.3f}")

        score_display = " | ".join(score_parts)

        content = f"[bold cyan]{title}[/bold cyan]"
        if distinction_display:
            content += f" {distinction_display}"
        content += f"\n[dim]{info_line}[/dim]"
        if description:
            content += f"\n{description}"
        if tags_display:
            content += f"{tags_display}"
        if temporal_display:
            content += f"{temporal_display}"
        if location_display:
            content += f"{location_display}"
        if contact_line:
            content += f"\n[dim]{contact_line}[/dim]"
        content += f"\n[dim]📊 {score_display}[/dim]"

        yield Static(content, classes="restaurant-card")
