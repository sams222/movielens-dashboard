"""Counting rules for the four MovieLens questions.

The charts only display what these functions return. Definitions:

1. Genre breakdown counts distinct movies, once per genre tag. A movie
   tagged Drama|War adds one to each. The file is already ratings, so every
   movie in it was rated at least once.
2. Genre satisfaction defaults to the mean of individual ratings. Each
   rating is applied to every genre on that movie. The other option averages
   each movie's own mean, so a blockbuster weighs the same as a single rating.
3. Release-year trend uses the `year` column (when the movie came out), never
   `rating_year` or the timestamp. Ratings with no release year are excluded
   here only.
4. "Best" is the arithmetic mean rating. The floor is the number of ratings,
   not a Bayesian shrink. Ties go to the movie with more ratings, then title.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent / "movie_ratings.csv"
REQUIRED_COLUMNS = ("movie_id", "rating", "title", "year", "genres")


def load_ratings(path: Path = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"movie_ratings.csv is missing columns: {missing}")
    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["genres"] = df["genres"].fillna("").astype(str).str.strip()
    df["title"] = df["title"].astype(str)
    return df


def genre_names(df: pd.DataFrame) -> list[str]:
    names = (
        df["genres"].str.split("|").explode().str.strip().dropna().unique().tolist()
    )
    return sorted(name for name in names if name)


def filter_ratings(
    df: pd.DataFrame,
    genres: list[str],
    year_min: int,
    year_max: int,
    full_min: int,
    full_max: int,
) -> pd.DataFrame:
    """Keep movies that carry any selected genre.

    The year window drops undated movies only when it is narrower than the
    full release span. At the full span those movies stay in every chart
    except the release-year line, which has nowhere to put them.
    """
    if not genres:
        return df.iloc[0:0]
    pattern = r"(?:^|\|)(?:" + "|".join(re.escape(genre) for genre in genres) + r")(?:\||$)"
    out = df.loc[df["genres"].str.contains(pattern, regex=True)]
    narrowed = year_min > full_min or year_max < full_max
    if narrowed:
        out = out.loc[out["year"].between(year_min, year_max)]
    return out


def genre_breakdown(df: pd.DataFrame, selected: list[str]) -> tuple[pd.DataFrame, int, int]:
    movies = df.drop_duplicates("movie_id")
    tags = _explode_genres(movies, selected)
    counts = (
        tags.groupby("genre", as_index=False)
        .size()
        .rename(columns={"size": "n_movies"})
        .sort_values(["n_movies", "genre"], ascending=[False, True])
    )
    n_movies = int(movies["movie_id"].nunique())
    n_tags = int(counts["n_movies"].sum()) if not counts.empty else 0
    return counts, n_movies, n_tags


def genre_satisfaction(df: pd.DataFrame, selected: list[str], weight: str) -> pd.DataFrame:
    if weight == "movie":
        movies = df.groupby("movie_id", as_index=False).agg(
            score=("rating", "mean"),
            genres=("genres", "first"),
        )
        tags = _explode_genres(movies, selected)
        grouped = tags.groupby("genre", as_index=False).agg(
            mean_rating=("score", "mean"),
            support=("movie_id", "nunique"),
        )
        grouped["support_label"] = "movies"
    elif weight == "rating":
        tags = _explode_genres(df, selected)
        grouped = tags.groupby("genre", as_index=False).agg(
            mean_rating=("rating", "mean"),
            support=("rating", "size"),
        )
        grouped["support_label"] = "ratings"
    else:
        raise ValueError(f"Unknown weighting: {weight}")
    return grouped.sort_values(["mean_rating", "genre"], ascending=[False, True])


def ratings_by_release_year(df: pd.DataFrame, min_ratings: int) -> pd.DataFrame:
    dated = df.dropna(subset=["year"]).copy()
    dated["year"] = dated["year"].astype(int)
    grouped = dated.groupby("year", as_index=False).agg(
        mean_rating=("rating", "mean"),
        n_ratings=("rating", "size"),
        n_movies=("movie_id", "nunique"),
    )
    kept = grouped.loc[grouped["n_ratings"] >= min_ratings]
    return kept.sort_values("year")


def undated_ratings(df: pd.DataFrame) -> tuple[int, int]:
    missing = df.loc[df["year"].isna()]
    return int(missing["movie_id"].nunique()), int(len(missing))


def top_movies(df: pd.DataFrame, floor: int, k: int = 5) -> tuple[pd.DataFrame, int]:
    grouped = df.groupby(["movie_id", "title"], as_index=False).agg(
        mean_rating=("rating", "mean"),
        n_ratings=("rating", "size"),
    )
    eligible = grouped.loc[grouped["n_ratings"] >= floor]
    ranked = eligible.sort_values(
        ["mean_rating", "n_ratings", "title"],
        ascending=[False, False, True],
    )
    return ranked.head(k), int(len(eligible))


def _explode_genres(df: pd.DataFrame, selected: list[str]) -> pd.DataFrame:
    tags = df.assign(genre=df["genres"].str.split("|")).explode("genre")
    tags["genre"] = tags["genre"].str.strip()
    selected_set = set(selected)
    return tags.loc[tags["genre"].isin(selected_set) & tags["genre"].ne("")]


if __name__ == "__main__":
    ratings = load_ratings()
    names = genre_names(ratings)
    y0, y1 = int(ratings["year"].min()), int(ratings["year"].max())
    full = filter_ratings(ratings, names, y0, y1, y0, y1)
    counts, n_movies, n_tags = genre_breakdown(full, names)
    assert n_movies == 1682
    assert n_tags > n_movies
    assert counts.iloc[0]["genre"] == "Drama"
    assert int(counts.iloc[0]["n_movies"]) == 725

    by_rating = genre_satisfaction(full, names, "rating")
    by_movie = genre_satisfaction(full, names, "movie")
    assert by_rating.iloc[0]["genre"] == "Film-Noir"
    assert by_movie.iloc[0]["genre"] == "Film-Noir"
    assert list(by_rating["genre"]) != list(by_movie["genre"])

    yearly = ratings_by_release_year(full, 1)
    assert "rating_year" not in yearly.columns
    assert int(yearly["year"].min()) == 1922
    undated_movies, undated_rows = undated_ratings(full)
    assert undated_movies == 5
    assert undated_rows == 30

    top50, n50 = top_movies(full, 50)
    top150, n150 = top_movies(full, 150)
    assert top50.iloc[0]["title"] == "Close Shave, A (1995)"
    assert top150.iloc[0]["title"] == "Schindler's List (1993)"
    assert n50 > n150
    assert set(top50["title"]) != set(top150["title"])

    narrowed = filter_ratings(ratings, names, 1990, 1998, y0, y1)
    assert undated_ratings(narrowed) == (0, 0)
    print("analysis checks passed")
    print(counts.to_string(index=False))
    print(by_rating.to_string(index=False))
    print(top50.to_string(index=False))
    print(top150.to_string(index=False))
