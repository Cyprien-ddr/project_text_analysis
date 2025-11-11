

import pandas as pd


from textual.app import App, ComposeResult
from textual.widgets import Static


class RestaurantCard(Static):

    def __init__(self, restaurant_data, rank, score, semantic_score=None, tag_score=None, matched_tags=None, food_detected=None, food_score=None):
        super().__init__()
        self.restaurant = restaurant_data
        self.rank = rank
        self.score = score
        self.semantic_score = semantic_score
        self.tag_score = tag_score
        self.matched_tags = matched_tags or {}
        self.food_detected = food_detected
        self.food_score = food_score

    def compose(self) -> ComposeResult:
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
            tags_display = f"\nPredicted: {', '.join(tag_list[:5])}"

        contact_parts = []
        if pd.notna(row.get('phone')):
            contact_parts.append(f"📞 {row['phone']}")
        if pd.notna(row.get('website')):
            contact_parts.append(f"🌐 {row['website']}")
        contact_line = " • ".join(contact_parts)

        # Enhanced score display
        score_parts = [f"Total: {self.score:.3f}"]
        if self.semantic_score is not None:
            score_parts.append(f"Semantic: {self.semantic_score:.3f}")
        if self.tag_score is not None and self.tag_score > 0:
            score_parts.append(f"Tags: {self.tag_score:.3f}")
        if self.food_score is not None and self.food_score > 0:
            score_parts.append(f"Food: {self.food_score:.3f}")

        score_display = " | ".join(score_parts)

        content = f"[bold cyan]{title}[/bold cyan]"
        if distinction_display:
            content += f" {distinction_display}"
        content += f"\n[dim]{info_line}[/dim]"
        if description:
            content += f"\n{description}"
        if tags_display:
            content += f"{tags_display}"
        if contact_line:
            content += f"\n[dim]{contact_line}[/dim]"
        content += f"\n[dim]📊 {score_display}[/dim]"

        yield Static(content, classes="restaurant-card")

