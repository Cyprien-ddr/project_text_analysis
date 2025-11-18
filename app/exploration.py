import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np


def explore_stars(df) -> None:
    if 'stars' in df.columns:
        stars_counts = df['stars'].value_counts().sort_index()
        plt.bar(stars_counts.index, stars_counts.values, color='gold', edgecolor='black')
        plt.xlabel('Nbr of Stgars', fontsize=12)
        plt.ylabel('Nbr of Restaurants', fontsize=12)
        plt.title('Distribution of stars', fontsize=14, fontweight='bold')
        plt.grid(axis='y', alpha=0.3)

def explore_cuisine(df) -> None:
    if 'cuisine_type' in df.columns:
        cuisine_counts = df['cuisine_type'].value_counts().head(10)
        plt.barh(cuisine_counts.index, cuisine_counts.values, color='steelblue')
        plt.xlabel('N° of  restaurants', fontsize=12)
        plt.ylabel('Cuisine type', fontsize=12)
        plt.title('Top 10 cuisine type', fontsize=14, fontweight='bold')
        plt.gca().invert_yaxis()
        plt.grid(axis='x', alpha=0.3)

def explore_price(df) -> None:
    if 'price_range' in df.columns:
        price_counts = df['price_range'].value_counts()
        colors = ['green', 'orange', 'red', 'darkred']
        plt.pie(price_counts.values, labels=price_counts.index, autopct='%1.1f%%',
                startangle=90, colors=colors[:len(price_counts)])
        plt.title('Price Range', fontsize=14, fontweight='bold')

def explore_locations(df) -> None:
    if 'location' in df.columns:
        location_counts = df['location'].value_counts().head(10)
        plt.bar(range(len(location_counts)), location_counts.values, color='coral')
        plt.xticks(range(len(location_counts)), location_counts.index, rotation=45, ha='right')
        plt.xlabel('Localisation', fontsize=12)
        plt.ylabel('Nbr° of  restaurants', fontsize=12)
        plt.title('Top 10 localisations', fontsize=14, fontweight='bold')
        plt.grid(axis='y', alpha=0.3)

def explore_tags(df) -> None:
    if 'tags' in df.columns:
        cuisine_counts = df['tags'].value_counts().head(10)
        plt.barh(cuisine_counts.index, cuisine_counts.values, color='coral')
        plt.xlabel('Nomber of restaurants', fontsize=12)
        plt.ylabel('Ambiance', fontsize=12)
        plt.title('Top 10 ambiances', fontsize=14, fontweight='bold')
        plt.gca().invert_yaxis()
        plt.grid(axis='x', alpha=0.3)

def explore_distinction(df) -> None:
    if 'distinction' in df.columns:
        has_distinction = df['distinction'].notna().sum()
        no_distinction = df['distinction'].isna().sum()

        labels = ['With distinction', 'Without distinction']
        sizes = [has_distinction, no_distinction]
        colors = ['#ff9999', '#66b3ff']

        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
        plt.title('Restaurants With/out distinction', fontsize=14, fontweight='bold')

def save_exploration() -> None:
    plt.tight_layout()
    plt.savefig('./data/restaurant_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()


def heatmap(df) -> None:
    fig2 = plt.figure(figsize=(10, 8))
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 1:
        correlation_matrix = df[numeric_cols].corr()
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0,
                    square=True, linewidths=1, cbar_kws={"shrink": 0.8})
        plt.tight_layout()
        plt.savefig('./data/correlation_heatmap.png', dpi=300, bbox_inches='tight')
        plt.show()


def exploration() -> None:
    plt.style.use('seaborn-v0_8-darkgrid')
    sns.set_palette("husl")
    df = pd.read_csv('./data/michelin_thailand_details_updated.csv')

    fig = plt.figure(figsize=(20, 20))
    plt.subplot(2, 3, 1)
    explore_stars(df)
    plt.subplot(2, 3, 2)
    explore_cuisine(df)
    plt.subplot(2, 3, 3)
    explore_price(df)
    plt.subplot(2, 3, 4)
    explore_locations(df)
    plt.subplot(2, 3, 5)
    explore_tags(df)
    plt.subplot(2, 3, 6)
    explore_distinction(df)
    save_exploration()
    fig2 = plt.figure(figsize=(10, 8))
    heatmap(df)

if __name__ == "__main__":
    exploration()

