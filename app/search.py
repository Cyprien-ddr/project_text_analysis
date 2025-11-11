import ast
import re
import os
import sys
from difflib import SequenceMatcher

import pandas as pd
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer

from tag_predictor import TagPredictor
from temporal_location_detector import TemporalLocationDetector

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_FILE = "./model/restaurants.index"
DATA_FILE = "./model/restaurants.pkl"
ML_MODEL_PATH = "./model/michelin_model"

# Scoring weights
SEMANTIC_WEIGHT = 1.8
TAG_WEIGHT = 0.6
HOURS_WEIGHT = 1.0
LOCATION_WEIGHT = 0.8
FOOD_WEIGHT = 0.4


class RestaurantSearch:
    """
    Facilitates restaurant search using combined approaches of semantic similarity, machine
    learning tags, temporal matching, location detection, and contextual data about food items.

    This class is designed to perform detailed restaurant searches by integrating semantic
    search methodologies, machine learning-predicted tags, temporal/location detection via spaCy,
    and auxiliary datasets like classified food categories. It provides comprehensive functionality
    for detecting time-based queries (lunch, dinner, specific days/times) and location-based
    queries, then executing a hybrid search that refines results based on given filters
    (e.g., location, cuisine, price). It allows users to retrieve precisely ranked results
    tailored to their preferences.

    Attributes:
        index: A FAISS index loaded for performing similarity searches on restaurant
            embeddings.
        df: A DataFrame containing the restaurant data, used as the search database.
        model: An instantiated SentenceTransformer model for embedding queries or text
            inputs to match against restaurant embeddings in the index.
        tag_predictor: A helper class for predicting tags from queries, used to refine
            search results.
        temporal_detector: A TemporalLocationDetector instance for extracting temporal
            and location information from queries.
        food_df: A DataFrame loaded with pre-classified food and category data, used for
            detecting food in user queries.
    """

    def __init__(self):
        if not os.path.exists(INDEX_FILE) or not os.path.exists(DATA_FILE):
            raise FileNotFoundError(f"Files {INDEX_FILE} or {DATA_FILE} not found")

        self.index = faiss.read_index(INDEX_FILE)
        with open(DATA_FILE, 'rb') as f:
            self.df = pickle.load(f)
        self.model = SentenceTransformer(MODEL)
        self.tag_predictor = TagPredictor()
        self.temporal_detector = TemporalLocationDetector()

        try:
            self.food_df = pd.read_csv("data/classified_food_names_clean.csv")
            self.food_df["food_name"] = self.food_df["food_name"].astype(str).str.lower()
            self.food_df["categories"] = self.food_df["categories"].astype(str)
            print(f"✓ Loaded {len(self.food_df)} classified food names.")
        except Exception as e:
            print(f"Could not load food classification file: {e}")
            self.food_df = pd.DataFrame(columns=["food_name", "categories"])

        print(f"✓ Loaded {len(self.df)} restaurants")

    def detect_food_from_query(self, query) -> tuple[None | str, list[str], float]:
        """
        Detect a food name inside a query string using regex or fuzzy string matching.

        Evaluates potential matches against a dataset and returns the best match, the
        associated categories, and a confidence score based on match quality. The
        process includes direct keyword matching via regex and fuzzy comparison using
        a similarity ratio. Specially tuned to return results only if the confidence
        score surpasses a threshold, ensuring relevance and accuracy of detection.

        Args:
            query (str): The input string where the function searches for potential
                         food items.

        Returns:
            tuple[str, list[str], float]: A tuple consisting of the detected food name
                                          (`str`), a list of associated categories
                                          (`list`), and the confidence score (`float`).
                                          If no match is found, returns (`None`, `[]`,
                                          `0.0`).
        """
        if self.food_df.empty:
            return None, [], 0.0

        query_lower = query.lower()

        best_match = None
        best_score = 0.0
        best_categories = []

        for _, row in self.food_df.iterrows():
            food = str(row["food_name"]).strip().lower()
            categories = [c.strip() for c in str(row["categories"]).split(";") if c.strip()]

            if re.search(rf"\b{re.escape(food)}\b", query_lower):
                score = 1.0
            else:
                ratio = SequenceMatcher(None, food, query_lower).ratio()
                score = ratio

            if score > best_score and score >= 0.45:
                best_match = food
                best_categories = categories
                best_score = score

        if best_match:
            print(f"🍽 Detected food: '{best_match}' ({best_score:.2f}) → {best_categories}")
            return best_match, best_categories, best_score
        else:
            print("🍽 No food detected in query.")
            return None, [], 0.0

    def search(self, query, location=None, distinction=None, cuisine=None, price=None,
               limit=10, use_ml_tags=True) -> tuple[list, dict]:
        """
        Hybrid search combining semantic similarity, ML tag prediction, temporal matching,
        and location detection.

        This method performs a detailed search by combining multiple signals:
        1. Semantic similarity via FAISS
        2. ML-predicted tags matching
        3. Food detection and category matching
        4. Temporal matching (days, times, meal periods)
        5. Location matching from query

        Args:
            query: A string representing the query text for the search.
            location: Optional location filter for narrowing down the search results.
            distinction: Optional string to filter by distinction (e.g., Michelin star).
            cuisine: Optional string specifying cuisine type to filter results.
            price: Optional price level filter for the search.
            limit: Maximum number of search results to return (default is 10).
            use_ml_tags: Boolean indicating whether to use ML-predicted tags in the
                scoring.

        Returns:
            A tuple containing:
            - A list of dictionaries, each representing search results with various
              scores (final_score, semantic_score, tag_score, food_score, hours_score,
              location_score), and other related information (e.g., detected food,
              matched tags, temporal info).
            - A dictionary of predicted tags with their respective scores if 'use_ml_tags'
              is True.
        """
        # Detect temporal and location information
        temporal_info = self.temporal_detector.detect_all(query)
        detected_days = temporal_info['days']
        detected_times = temporal_info['times']
        detected_meal_periods = temporal_info['meal_periods']
        detected_locations = temporal_info['locations']

        # Print detection results
        if detected_days:
            print(f"📅 Detected days: {detected_days}")
        if detected_times:
            print(f"🕐 Detected times: {[t.strftime('%H:%M') for t in detected_times]}")
        if detected_meal_periods:
            print(f"🍴 Detected meal periods: {detected_meal_periods}")
        if detected_locations:
            print(f"📍 Detected locations: {detected_locations}")

        df_filtered = self.df.copy()

        if location and location != "All":
            df_filtered = df_filtered[df_filtered['location'] == location]
        # elif detected_locations:
        #     # Try to match detected locations with restaurant locations
        #     location_mask = df_filtered['location'].str.lower().apply(
        #         lambda x: any(loc.lower() in str(x).lower() for loc in detected_locations)
        #     )
        #     df_filtered = df_filtered[location_mask]

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
            return [], {}

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

        k = min(len(filtered_indices), limit * 3)
        distances, indices = temp_index.search(query_embedding, k)

        predicted_tags = {}
        if use_ml_tags and self.tag_predictor.available:
            predicted_tags = self.tag_predictor.predict_tags(query)

        detected_food, food_categories, food_sim = self.detect_food_from_query(query)
        if detected_food:
            print(f"🍽 Detected food: '{detected_food}' ({food_sim:.2f}) with categories {food_categories}")
        else:
            print("🍽 No food detected in query.")

        results = []
        for local_idx, semantic_score in zip(indices[0], distances[0]):
            original_idx = filtered_indices[local_idx]
            row = self.df.loc[original_idx]

            tag_score = 0.
            matched_tags = {}
            restaurant_tags = []

            if predicted_tags and pd.notna(row.get('tags')):
                restaurant_tags_str = str(row['tags'])
                restaurant_tags = [t.strip() for t in restaurant_tags_str.split(';') if t.strip()]
                for pred_tag, pred_score in predicted_tags.items():
                    if pred_tag in restaurant_tags:
                        tag_score += pred_score
                        matched_tags[pred_tag] = pred_score

                if len(predicted_tags) > 0:
                    tag_score = tag_score / len(predicted_tags)

            food_score = 0.0
            cuisine_text = str(row.get("cuisine_type", "")).lower()
            if detected_food and food_categories and cuisine_text and any(
                    cat.lower() in cuisine_text for cat in food_categories):
                food_score = 1.0


            hours_score = -1.0
            hours_match = False
            if detected_days or detected_times or detected_meal_periods:
                opening_hours = row.get('opening_hours', 'N/A')
                if opening_hours and opening_hours != 'N/A':
                    try :
                        opening_hours = ast.literal_eval(opening_hours)
                    except:
                        if isinstance(opening_hours, str):
                            import json
                            try:
                                opening_hours = json.loads(opening_hours.replace('""', '"'))
                            except:
                                opening_hours = None
                    if isinstance(opening_hours, dict):
                        hours_match, hours_score = self.temporal_detector.check_restaurant_hours(
                            opening_hours,
                            detected_days,
                            detected_times,
                            detected_meal_periods
                        )
                        hours_score = 1 if hours_match == True else -1

            final_score = (
                    (semantic_score * SEMANTIC_WEIGHT) +
                    (tag_score * TAG_WEIGHT) +
                    (food_score * FOOD_WEIGHT) +
                    (hours_score * HOURS_WEIGHT)
                    # (location_score * LOCATION_WEIGHT)
            )

            results.append({
                'idx': original_idx,
                'final_score': final_score,
                'semantic_score': semantic_score,
                'tag_score': tag_score,
                'matched_tags': matched_tags,
                'food_score': food_score,
                'food_detected': detected_food,
                'food_category': food_categories,
                'hours_score': hours_score,
                'hours_match': hours_match,
                'temporal_info': {
                    'days': detected_days,
                    'times': [t.strftime('%H:%M') for t in detected_times],
                    'meal_periods': detected_meal_periods
                },
                # 'location_score': location_score,
                # 'detected_locations': detected_locations,
            })

        results.sort(key=lambda x: x['final_score'], reverse=True)
        return results[:limit], predicted_tags

    def get_filter_options(self):
        """
        Retrieves various filter options based on restaurant attributes.

        The method extracts unique values for locations, cuisines, prices,
        and predefined distinctions. It ensures that the options are sorted
        and formatted for utilization in filtering processes. Each category
        has an 'All' option added for comprehensive selection criteria.

        Returns:
            dict: A dictionary containing filter options for each category:
            'locations', 'cuisines', 'prices', and 'distinctions'. Each option
            is represented as a list of tuples, where each tuple contains a
            display value and the corresponding value for filtering purposes.
        """
        locations = ["All"] + sorted([
            loc for loc in self.df['location'].unique() if pd.notna(loc)
        ])

        cuisines = ["All"] + sorted([
            c for c in self.df['cuisine'].unique() if pd.notna(c)
        ])[:100]

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
