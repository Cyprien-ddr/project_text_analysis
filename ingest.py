#!/usr/bin/env python3
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import pickle
import os
from tqdm import tqdm

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_FILE = "restaurants.index"
DATA_FILE = "restaurants.pkl"


def load_data():
    df_basic = pd.read_csv('michelin_thailand.csv')
    df_details = pd.read_csv('michelin_thailand_details.csv')
    df_reviews = pd.read_csv('google_reviews.csv')

    print(f"\t{len(df_basic)} restaurants")
    print(f"\t{len(df_details)} details")
    print(f"\t{len(df_reviews)} reviews")

    df = pd.merge(df_basic, df_details, on='name', how='left', suffixes=('', '_dup'), validate="many_to_many")
    df = df[[c for c in df.columns if not c.endswith('_dup')]]

    df_reviews_en = df_reviews[df_reviews['language'] == 'en'].copy()
    print(f"\t{len(df_reviews_en)} reviews in english out of {len(df_reviews)})")

    reviews_agg = df_reviews_en.groupby('restaurant_name').agg({
        'review_text': lambda x: ' '.join(x.astype(str).tolist())
    }).rename(columns={'review_text': 'reviews_summary'})

    reviews_count = df_reviews_en.groupby('restaurant_name').size().rename('review_count')

    df = pd.merge(df, reviews_agg, left_on='name', right_index=True, how='left', validate="many_to_many")
    df = pd.merge(df, reviews_count, left_on='name', right_index=True, how='left', validate="many_to_many")

    df['reviews_summary'] = df['reviews_summary'].fillna('')
    df['review_count'] = df['review_count'].fillna(0).astype(int)

    print(f"{len(df)} restaurants after fusion")
    print(f"{df['review_count'].sum()} reviews")
    return df


def create_text(row):
    parts = []

    if pd.notna(row.get('name')):
        parts.append(str(row['name']))
    if pd.notna(row.get('cuisine')):
        parts.append(str(row['cuisine']))
    if pd.notna(row.get('description')):
        parts.append(str(row['description']))
    if pd.notna(row.get('reviews_summary')):
        parts.append(str(row['reviews_summary']))

    return " ".join(parts)


def build_index(df, model):
    print("\nGenerating embeddings...")

    texts = [create_text(row) for _, row in df.iterrows()]

    embeddings = []
    batch_size = 32

    for i in tqdm(range(0, len(texts), batch_size), desc="Embeddings"):
        batch = texts[i:i + batch_size]
        batch_embeddings = model.encode(batch, show_progress_bar=False)
        embeddings.extend(batch_embeddings)

    embeddings = np.array(embeddings).astype('float32')

    print(f"\t{len(embeddings)} embeddings generated")
    print(f"\tDim: {embeddings.shape[1]}")

    print("\nBuilding FAISS index...")
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)

    faiss.normalize_L2(embeddings)

    index.add(embeddings)

    print(f"\tIndex created with {index.ntotal} vectors")

    return index, embeddings


def save_index(index, df):
    print("\nSaving...")

    faiss.write_index(index, INDEX_FILE)
    print(f"\tIndex saved: {INDEX_FILE}")

    with open(DATA_FILE, 'wb') as f:
        pickle.dump(df, f)
    print(f"\tData saved: {DATA_FILE}")


def print_stats(df):
    print(f"\n{'=' * 60}")
    print("STATS")
    print(f"{'=' * 60}")
    print(f"Total restaurants: {len(df)}")

    print("\n By Stars:")
    for stars in sorted(df['stars'].unique(), reverse=True):
        if stars > 0:
            count = len(df[df['stars'] == stars])
            print(f"   {int(stars)} stars: {count}")

    print("Top 5 city:")
    top_cities = df['location'].value_counts().head(5)
    for city, count in top_cities.items():
        print(f"   {city}: {count}")

    print(f"{'=' * 60}")


def main():
    print("\n" + "=" * 60)
    print("INDEXATION FAISS")
    print("=" * 60)

    try:
        df = load_data()

        print("\nLoading the model")
        model = SentenceTransformer(MODEL)
        print('Model loaded')

        index, embeddings = build_index(df, model)

        save_index(index, df)

        print_stats(df)

        print("\nNext step:\n$ python search_faiss.py 'french restaurant'")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()