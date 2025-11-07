#!/usr/bin/env python3
import sys
import os
import pandas as pd
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Input, Button, Static, Select,
    Label, DataTable, LoadingIndicator
)
from textual.binding import Binding
from textual import on
from textual.reactive import reactive

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_FILE = "restaurants.index"
DATA_FILE = "restaurants.pkl"


class RestaurantCard(Static):

    def __init__(self, restaurant_data, rank, score):
        super().__init__()
        self.restaurant = restaurant_data
        self.rank = rank
        self.score = score

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

        info_line = " • ".join(info_parts)

        description = ""
        if pd.notna(row.get('description')):
            description = str(row['description'])[:200]

        reviews = ""
        if pd.notna(row.get('reviews_summary')):
            reviews = f"💬 {row['reviews_summary']}"

        contact_parts = []
        if pd.notna(row.get('phone')):
            contact_parts.append(f"📞 {row['phone']}")
        if pd.notna(row.get('website')):
            contact_parts.append(f"🌐 {row['website']}")
        contact_line = " • ".join(contact_parts)

        score_display = f"Score: {self.score:.3f}"

        content = f"[bold cyan]{title}[/bold cyan]"
        if distinction_display:
            content += f" {distinction_display}"
        content += f"\n[dim]{info_line}[/dim]"
        if description:
            content += f"\n{description}"
        if reviews:
            content += f"\n[italic]{reviews}[/italic]"
        if contact_line:
            content += f"\n[dim]{contact_line}[/dim]"
        content += f"\n[dim]{score_display}[/dim]"

        yield Static(content, classes="restaurant-card")


class RestaurantSearch:
    """Moteur de recherche FAISS"""

    def __init__(self):
        if not os.path.exists(INDEX_FILE) or not os.path.exists(DATA_FILE):
            raise FileNotFoundError(f"Files {INDEX_FILE} or {DATA_FILE} not found")

        self.index = faiss.read_index(INDEX_FILE)
        with open(DATA_FILE, 'rb') as f:
            self.df = pickle.load(f)
        self.model = SentenceTransformer(MODEL)

    def search(self, query, location=None, distinction=None, cuisine=None, price=None, limit=10):
        df_filtered = self.df.copy()

        if location and location != "All":
            df_filtered = df_filtered[df_filtered['location'] == location]

        if distinction and distinction != "All":
            df_filtered = df_filtered[
                df_filtered['distinction'].fillna('').str.lower().str.strip() == distinction.lower().strip()
                ]

        if cuisine and cuisine != "All":
            df_filtered = df_filtered[
                df_filtered['cuisine'].str.contains(cuisine, case=False, na=False)
            ]

        if price and price != "All":
            df_filtered = df_filtered[df_filtered['price'] == price]

        if len(df_filtered) == 0:
            return []

        filtered_indices = df_filtered.index.tolist()

        filtered_embeddings = []
        for idx in filtered_indices:
            embedding = self.index.reconstruct(int(idx))
            filtered_embeddings.append(embedding)

        filtered_embeddings = np.array(filtered_embeddings).astype('float32')

        temp_index = faiss.IndexFlatIP(filtered_embeddings.shape[1])
        temp_index.add(filtered_embeddings)

        query_embedding = self.model.encode([query])[0].astype('float32')
        query_embedding = query_embedding.reshape(1, -1)
        faiss.normalize_L2(query_embedding)

        k = min(len(filtered_indices), limit)
        distances, indices = temp_index.search(query_embedding, k)

        results = []
        for local_idx, dist in zip(indices[0], distances[0]):
            original_idx = filtered_indices[local_idx]
            results.append((original_idx, dist))

        return results

    def get_filter_options(self):
        locations = ["All"] + sorted([
            loc for loc in self.df['location'].unique() if pd.notna(loc)
        ])

        cuisines = ["All"] + sorted([
            c for c in self.df['cuisine'].unique() if pd.notna(c)
        ])[:20]

        prices = ["All"] + sorted([
            p for p in self.df['price'].unique() if pd.notna(p)
        ])

        distinctions = ["All", "3 star", "2 star", "1 star", "Bib Gourmand"]

        return {
            'locations': [(loc, loc) for loc in locations],
            'cuisines': [(c, c) for c in cuisines],
            'prices': [(p, p) for p in prices],
            'distinctions': [(d, d) for d in distinctions]
        }


class RestaurantSearchApp(App):

    CSS = """
    Screen {
        background: $surface;
    }

    #search-container {
        dock: top;
        height: auto;
        background: $panel;
        padding: 1;
        border-bottom: heavy $primary;
    }

    #filters-container {
        height: auto;
        layout: horizontal;
        padding: 1;
    }

    #filters-container Select {
        width: 1fr;
        margin-right: 1;
    }

    #search-input {
        width: 100%;
        margin-bottom: 1;
    }

    #search-button {
        margin-top: 1;
        width: 100%;
    }

    #results-container {
        height: 1fr;
        padding: 1;
    }

    .restaurant-card {
        border: solid $primary;
        padding: 1;
        margin: 1;
        background: $panel;
    }

    #stats {
        dock: bottom;
        height: 3;
        background: $panel;
        padding: 1;
        border-top: heavy $primary;
    }

    LoadingIndicator {
        height: 100%;
    }
    """

    TITLE = "🍽️  Michelin Restaurant Search"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+r", "reset", "Reset", show=True),
    ]

    results_count = reactive(0)

    def __init__(self):
        super().__init__()
        try:
            self.searcher = RestaurantSearch()
            self.filter_options = self.searcher.get_filter_options()
            self.total_restaurants = len(self.searcher.df)
        except Exception as e:
            print(f"Error loading data: {e}")
            sys.exit(1)

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="search-container"):
            yield Label(f"📊 Database: {self.total_restaurants} restaurants")
            yield Input(
                placeholder="🔍 Search: 'romantic dinner', 'best seafood', 'authentic thai'...",
                id="search-input"
            )

            with Horizontal(id="filters-container"):
                yield Select(
                    self.filter_options['locations'],
                    prompt="📍 Location",
                    id="location-filter"
                )
                yield Select(
                    self.filter_options['distinctions'],
                    prompt="🏆 Awards",
                    id="distinction-filter"
                )
                yield Select(
                    self.filter_options['cuisines'],
                    prompt="🍽️ Cuisine",
                    id="cuisine-filter"
                )
                yield Select(
                    self.filter_options['prices'],
                    prompt="💰 Price",
                    id="price-filter"
                )

            yield Button("🔍 Search", variant="primary", id="search-button")

        with ScrollableContainer(id="results-container"):
            yield Static("👋 Welcome! Enter a search query and press Search.", id="welcome")

        with Container(id="stats"):
            yield Label("Ready to search", id="stats-label")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-input").focus()

    @on(Input.Submitted, "#search-input")
    @on(Button.Pressed, "#search-button")
    async def perform_search(self) -> None:
        query_input = self.query_one("#search-input", Input)
        query = query_input.value.strip()

        if not query:
            self.update_stats("⚠️ Please enter a search query")
            return

        location = self.query_one("#location-filter", Select).value
        distinction = self.query_one("#distinction-filter", Select).value
        cuisine = self.query_one("#cuisine-filter", Select).value
        price = self.query_one("#price-filter", Select).value

        results_container = self.query_one("#results-container")
        await results_container.remove_children()
        await results_container.mount(LoadingIndicator())
        self.update_stats("🔄 Searching...")

        try:
            results = self.searcher.search(
                query=query,
                location=location if location != Select.BLANK else None,
                distinction=distinction if distinction != Select.BLANK else None,
                cuisine=cuisine if cuisine != Select.BLANK else None,
                price=price if price != Select.BLANK else None,
                limit=20
            )

            await results_container.remove_children()

            if results:
                for i, (idx, score) in enumerate(results, 1):
                    row = self.searcher.df.loc[idx]
                    card = RestaurantCard(row, i, score)
                    results_container.mount(card)

                self.update_stats(f"✅ Found {len(results)} restaurants for '{query}'")
            else:
                await results_container.mount(
                    Static("No results found. Try different filters or search terms.")
                )
                self.update_stats("No results found")

        except Exception as e:
            await results_container.remove_children()
            await results_container.mount(Static(f"Error: {str(e)}"))
            self.update_stats(f"Error: {str(e)}")

    def update_stats(self, message: str) -> None:
        stats_label = self.query_one("#stats-label", Label)
        stats_label.update(message)

    def action_reset(self) -> None:
        self.query_one("#search-input", Input).value = ""
        self.query_one("#location-filter", Select).clear()
        self.query_one("#distinction-filter", Select).clear()
        self.query_one("#cuisine-filter", Select).clear()
        self.query_one("#price-filter", Select).clear()
        self.query_one("#search-input").focus()
        self.update_stats("🔄 Filters reset")


def main():
    app = RestaurantSearchApp()
    app.run()


if __name__ == "__main__":
    main()