#!/usr/bin/env python3
import re

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import pickle
from tqdm import tqdm

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_FILE = "restaurants.index"
DATA_FILE = "restaurants.pkl"


def load_data():
    """
    Load and prepare Michelin Thailand restaurant data with aggregated English reviews.

    Reads base, detail, and Google reviews CSVs; merges base and detail records on name; filters English reviews,
    cleans text, aggregates review texts per restaurant into a reviews_summary, and counts reviews. Merges these
    aggregates back to the restaurant dataframe, fills missing values, and prints basic stats.

    :return: Consolidated restaurant dataframe with reviews_summary and review_count columns.
    rtype pandas.DataFrame
    """
    df_basic = pd.read_csv('michelin_thailand.csv')
    df_details = pd.read_csv('michelin_thailand_details.csv')
    df_reviews = pd.read_csv('google_reviews.csv')

    print(f"\t{len(df_basic)} restaurants")
    print(f"\t{len(df_details)} details")
    print(f"\t{len(df_reviews)} reviews")

    df = pd.merge(df_basic, df_details, on='name', how='left', suffixes=('', '_dup'), validate="many_to_many")
    df = df[[c for c in df.columns if not c.endswith('_dup')]]

    df_reviews_en_raw = df_reviews[df_reviews['language'] == 'en'].copy()
    df_reviews_en = clean_text(df_reviews_en_raw)
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


def create_text(row) -> str:
    """
    Build a single text string from selected non-null fields in a row.

    :param row: Mapping or pandas.Series: A row-like object supporting .get and indexing for keys:
    'name', 'cuisine', 'description', and 'reviews_summary'.

    :return:str A space-joined string of available fields in the order: name, cuisine, description, reviews_summary.
    """
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


def clean_text(text) -> str:
    """
    Clean and normalize raw text for downstream processing.

    Performs emoji removal, strips URLs, mentions, and hashtags, replaces special characters while keeping basic
    punctuation, collapses multiple spaces, trims edges, and lowercases the result. Returns an empty string for
    NaN or empty inputs.

    :param text: Any input convertible to string.
    :return: The cleaned, normalized text.
    """
    if pd.isna(text) or text == '':
        return ''

    text = str(text)

    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001F900-\U0001F9FF"  # supplemental symbols
        u"\U0001FA00-\U0001FAFF"  # more symbols
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub(r'', text)

    text = re.sub(r'http\S+|www.\S+', '', text)

    text = re.sub(r'@\w+|#\w+', '', text)

    text = re.sub(r'[^\w\s.,!?;:\'-]', ' ', text)

    text = re.sub(r'\s+', ' ', text)

    text = text.strip()

    text = text.lower()

    return text

def build_index(df, model) -> tuple:
    """
    Build a FAISS inner-product index from sentence embeddings of restaurant records.

    Generates text per row via create_text, encodes texts in batches with the provided SentenceTransformer-like model,
    L2-normalizes embeddings, and adds them to a FAISS IndexFlatIP.

    :param df: pandas.DataFrame containing restaurant metadata used by create_text.
    :param model: Encoder with an .encode(list[str], show_progress_bar=bool) method producing float embeddings.
    :return: tuple: (index, embeddings) where index is a faiss.IndexFlatIP and embeddings is a float32 numpy.ndarray.
    """
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


def save_index(index, df) -> None:
    """
    Persist the FAISS index and associated dataframe to disk.

    Writes the in-memory faiss.Index to INDEX_FILE and pickles the given pandas.DataFrame
    to DATA_FILE for later retrieval.

    :param index: FAISS inner-product index (e.g., faiss.IndexFlatIP) to be saved.
    :param df: pandas.DataFrame containing restaurant metadata aligned with the index.
    :return: None
    """
    print("\nSaving...")

    faiss.write_index(index, INDEX_FILE)
    print(f"\tIndex saved: {INDEX_FILE}")

    with open(DATA_FILE, 'wb') as f:
        pickle.dump(df, f)
    print(f"\tData saved: {DATA_FILE}")


def print_stats(df) -> None:
    """
    Print summary statistics for a restaurant dataset.

    This function prints:
    - Total number of restaurants.
    - Counts of restaurants by star rating (descending, > 0).
    - Top 5 cities by number of restaurants.
    :param df: (pandas.DataFrame): DataFrame containing at least 'stars' and 'location' columns.
    :return: None
    """
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

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()