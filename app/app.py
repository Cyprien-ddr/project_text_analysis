import sys
import os
import csv
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Input, Button, Static, Select,
    Label, DataTable, LoadingIndicator, Checkbox
)
from textual.binding import Binding
from textual import on
from textual.reactive import reactive

from card import RestaurantCard
from search import RestaurantSearch


class RestaurantSearchApp(App):
    """
    The RestaurantSearchApp class is a graphical user interface (GUI) application for
    searching Michelin-rated restaurants. Users can perform searches based on various
    filters including location, awards, cuisine, and price. The application is designed
    to facilitate intuitive and efficient restaurant discovery. It provides features like
    search input, selectable filters, a display of search results, and detailed logging
    for search statistics.

    The class integrates dynamic UI components for user interactions, handles reactive
    elements to reflect state changes, and provides loading indicators for asynchronous
    operations.

    Attributes:
        CSS (str): The CSS string for styling the GUI elements of the application.
        TITLE (str): The title of the application displayed in the header.
        BINDINGS (list): The keyboard shortcuts bindings for the application with actions
            like quitting or resetting.
        results_count (int): A reactive attribute indicating the number of search results.
    """
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
        """
        Constructs and yields components required to display a user interface with search
        functionality, filters, and results.

        The composed interface includes:
        - A header section.
        - A search container with a database summary, input field, filter options, and a search button.
        - A scrollable container to display search results.
        - A footer section along with a stats container to display search status.

        Returns:
            ComposeResult: A generator that yields interface components in sequence.
        """
        yield Header()

        with Container(id="search-container"):
            yield Label(f"📊 Database: {self.total_restaurants} restaurants")
            yield Input(
                placeholder="🔍 Search: 'romantic dinner with beautiful pizza', 'best seafood', 'family friendly'...",
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
        """
        Handles the search functionality in the application. Triggered when either the search input is submitted
        or the search button is pressed. Retrieves and applies user-specified filters, executes the search query,
        and displays the results or an appropriate message.

        Args:
            None

        Raises:
            Exception: If an error occurs during the search process it gracefully
            handles the exception with an appropriate error message being displayed
            for the user.

        Returns:
            None
        """
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
            results, predicted_tags= self.searcher.search(
                query=query,
                location=location if location != Select.BLANK else None,
                distinction=distinction if distinction != Select.BLANK else None,
                cuisine=cuisine if cuisine != Select.BLANK else None,
                price=price if price != Select.BLANK else None,
                limit=20
            )
            self.log_search_results(
                query=query,
                filters={
                    "location": location,
                    "distinction": distinction,
                    "cuisine": cuisine,
                    "price": price
                },
                results=results,
                predicted_tags=predicted_tags,
            )


            await results_container.remove_children()

            if results:
                for i, result in enumerate(results, 1):
                    row = self.searcher.df.loc[result['idx']]
                    card = RestaurantCard(
                        row,
                        i,
                        result['final_score'],
                        semantic_score=result['semantic_score'],
                        tag_score=result['tag_score'],
                        matched_tags=result['matched_tags'],
                        food_detected=result.get('food_detected'),
                        food_score=result.get('food_score'),
                    )
                    await results_container.mount(card)

                self.update_stats(f"Found {len(results)} restaurants for '{query}')")
            else:
                await results_container.mount(
                    Static("No results found. Try different filters or search terms.")
                )
                self.update_stats("No results found")

        except Exception as e:
            await results_container.remove_children()
            await results_container.mount(Static(f"Error: {str(e)}"))
            self.update_stats(f"Error: {str(e)}")

    def log_search_results(self, query, filters, results, predicted_tags=None):
        """
        Logs detailed search results into a CSV file for record-keeping and analytics purposes. This
        includes timestamp, query details, filters applied, retrieved results, and predicted tags.

        Args:
            query (str): The search query entered by the user.
            filters (dict): A dictionary containing applied filters such as location, distinction,
                cuisine, or price.
            results (list): A list of dictionaries containing search result details. Each dictionary
                includes attributes like 'idx', 'final_score', 'semantic_score', 'tag_score',
                'food_detected', 'food_category', 'food_score', and 'matched_tags'.
            predicted_tags (dict, optional): A dictionary of predicted tags and their associated scores
                (e.g., {"tag_name": score}). Defaults to None.
        """
        log_file = "search_logs_detailed.csv"
        file_exists = os.path.exists(log_file)

        with open(log_file, "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "timestamp", "query", "predicted_tags",
                    "location", "distinction", "cuisine", "price",
                    "num_results", "details"
                ])

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if predicted_tags:
                predicted_tags_str = ", ".join([
                    f"{tag}({score:.2f})" for tag, score in predicted_tags.items()
                ])
            else:
                predicted_tags_str = "None"

            if results:
                details = []
                for r in results:
                    row = self.searcher.df.loc[r['idx']]
                    name = row.get('name', 'Unknown')
                    matched = ", ".join([
                        f"{tag}({score:.2f})" for tag, score in r['matched_tags'].items()
                    ]) if r['matched_tags'] else "None"

                    details.append(
                        f"{name} [Total={r['final_score']:.3f} | Sem={r['semantic_score']:.3f} | Tag={r['tag_score']:.3f} | Terms={r['food_detected']} | FoodCate={r['food_category']} | TermScore={r['food_score']}| Matched={matched}]"
                    )

                details_str = " ; ".join(details)
            else:
                details_str = "No results"

            writer.writerow([
                timestamp,
                query,
                predicted_tags_str,
                filters.get("location"),
                filters.get("distinction"),
                filters.get("cuisine"),
                filters.get("price"),
                len(results),
                details_str
            ])


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

