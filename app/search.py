import re
import os
from difflib import SequenceMatcher

import pandas as pd
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer


from tag_predictor import TagPredictor

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_FILE = "./model/restaurants.index"
DATA_FILE = "./model/restaurants.pkl"
ML_MODEL_PATH = "./model/michelin_model"

# Scoring weights
SEMANTIC_WEIGHT = 1.8
TAG_WEIGHT = 0.6
HOURS_WEIGHT = 1
FOOD_WEIGHT = 0.4


class RestaurantSearch:

    def __init__(self):
        if not os.path.exists(INDEX_FILE) or not os.path.exists(DATA_FILE):
            raise FileNotFoundError(f"Files {INDEX_FILE} or {DATA_FILE} not found")

        self.index = faiss.read_index(INDEX_FILE)
        with open(DATA_FILE, 'rb') as f:
            self.df = pickle.load(f)
        self.model = SentenceTransformer(MODEL)
        self.tag_predictor = TagPredictor()

        try:
            self.food_df = pd.read_csv("data/classified_food_names_clean.csv")
            self.food_df["food_name"] = self.food_df["food_name"].astype(str).str.lower()
            self.food_df["categories"] = self.food_df["categories"].astype(str)
            print(f"✓ Loaded {len(self.food_df)} classified food names.")
        except Exception as e:
            print(f"Could not load food classification file: {e}")
            self.food_df = pd.DataFrame(columns=["food_name", "categories"])

        print(f"✓ Loaded {len(self.df)} restaurants")


    def detect_food_from_query(self, query):
        """
        Detect a food name inside the query using regex / fuzzy string match.
        Returns (food_name, categories, confidence_score)
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

            # ✅ 1. Regex match (exact substring, word boundaries)
            if re.search(rf"\b{re.escape(food)}\b", query_lower):
                score = 1.0
            else:
                # ✅ 2. Fuzzy match fallback (partial ratio)
                ratio = SequenceMatcher(None, food, query_lower).ratio()
                score = ratio

            # Garde le meilleur match au-dessus d’un seuil
            if score > best_score and score >= 0.45:
                best_match = food
                best_categories = categories
                best_score = score

        if best_match:
            print(f"🍽 Detected food: '{best_match}' ({best_score:.2f}) → {best_categories}")
            return best_match, best_categories, best_score
        else:
            print("🍽 No food detected in query (regex).")
            return None, [], 0.0

    def search(self, query, location=None, distinction=None, cuisine=None, price=None,
               limit=10, use_ml_tags=True):
        """
        Hybrid search combining semantic similarity and ML tag prediction

        Final score = (semantic_score * SEMANTIC_WEIGHT) + (tag_score * TAG_WEIGHT)
        """
        # Step 1: Apply filters
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
                food_score = 1

            # TODO - Add hours
            final_score = (semantic_score * SEMANTIC_WEIGHT) + (tag_score * TAG_WEIGHT) + (food_score * FOOD_WEIGHT)

            results.append({
                'idx': original_idx,
                'final_score': final_score,
                'semantic_score': semantic_score,
                'tag_score': tag_score,
                'matched_tags': matched_tags,
                'food_score': food_score,
                'food_detected': detected_food,
                'food_category': food_categories,
            })

        results.sort(key=lambda x: x['final_score'], reverse=True)
        return results[:limit], predicted_tags

    def get_filter_options(self):
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
