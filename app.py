"""MovieLens dashboard for the four assigned questions.

Definitions live in analysis.py. In short:
- Question 1 counts movies, once per genre tag. Overlapping tags are not a pie.
- Question 2 defaults to the mean of ratings, not the mean of movie means.
- Question 3 uses the release-year column, never the year the rating was filed.
- Question 4 ranks by mean rating among movies with enough ratings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis import (
    filter_ratings,
    genre_breakdown,
    genre_names,
    genre_satisfaction,
    load_ratings,
    ratings_by_release_year,
    top_movies,
    undated_ratings,
)

INK = "#1c1917"
MUTED = "#57534e"
BLUE = "#1e4d8c"
AMBER = "#c45c26"
GRID = "#e7e5e4"


@st.cache_data
def ratings() -> pd.DataFrame:
    return load_ratings()


def main() -> None:
    st.set_page_config(
        page_title="MovieLens Ratings",
        page_icon="🎬",
        layout="wide",
    )
    df = ratings()
    names = genre_names(df)
    full_min = int(df["year"].min())
    full_max = int(df["year"].max())
    max_ratings = int(df.groupby("movie_id").size().max())
    _init_state(names, full_min, full_max, max_ratings)

    st.title("MovieLens ratings")
    st.caption(
        "1,682 movies and 100,000 ratings, scored from 1 to 5 stars. "
        "The controls start on the full dataset, which is what the four questions ask about."
    )

    with st.sidebar:
        st.header("Filters")
        st.multiselect(
            "Genres",
            options=names,
            key="genres",
            help="A movie stays in if it has any checked genre. Each checked genre it carries is counted on its own.",
        )
        st.slider(
            "Release year",
            min_value=full_min,
            max_value=full_max,
            key="years",
            help="The full span keeps movies with no release year. Narrowing the span drops them.",
        )
        st.button("Reset to the full dataset", on_click=_reset, args=(names, full_min, full_max))
        st.caption(
            "Genre and year limit every chart. The average, the thin-year cutoff, "
            "and the two rating floors sit next to the chart they change."
        )

    selected = st.session_state.genres
    year_min, year_max = st.session_state.years
    view = filter_ratings(df, selected, year_min, year_max, full_min, full_max)

    if view.empty:
        st.warning("Nothing matches these filters. Reset them, or choose at least one genre.")
        return

    n_movies = int(view["movie_id"].nunique())
    n_ratings = int(len(view))
    mean_rating = float(view["rating"].mean())
    c1, c2, c3 = st.columns(3)
    c1.metric("Movies in view", f"{n_movies:,}")
    c2.metric("Ratings in view", f"{n_ratings:,}")
    c3.metric("Average rating", f"{mean_rating:.2f}")

    _genre_breakdown(view, selected)
    _genre_satisfaction(view, selected, mean_rating)
    _over_time(view)
    _best_movies(view, max_ratings)

    st.caption("Source: GroupLens MovieLens ratings extract used for this assignment.")


def _genre_breakdown(view: pd.DataFrame, selected: list[str]) -> None:
    st.header("1. What's the distribution of genres among the movies that were rated?")
    st.markdown(
        "A movie is counted **once for each genre tag** on it. "
        "Drama|War adds one movie to Drama and one to War. "
        "The bars overlap, so they are not shares of a whole and a pie chart would not add up."
    )
    counts, n_movies, n_tags = genre_breakdown(view, selected)
    if counts.empty:
        st.info("No genre tags in this view.")
        return
    top = counts.iloc[0]
    share = top["n_movies"] / n_movies if n_movies else 0
    st.markdown(
        f"**{top['genre']}** is on {int(top['n_movies']):,} of {n_movies:,} movies "
        f"({share:.0%}). The tags together are listed {n_tags:,} times."
    )
    frame = counts.sort_values(["n_movies", "genre"], ascending=[True, False])
    fig = go.Figure(
        go.Bar(
            x=frame["n_movies"],
            y=frame["genre"],
            orientation="h",
            marker_color=BLUE,
            text=frame["n_movies"].map(lambda n: f"{int(n):,}"),
            textposition="outside",
            cliponaxis=False,
            customdata=frame["n_movies"] / n_movies,
            hovertemplate=(
                "<b>%{y}</b><br>%{x:,} movies<br>%{customdata:.1%} of movies in view"
                "<extra></extra>"
            ),
        )
    )
    fig.update_yaxes(categoryorder="array", categoryarray=frame["genre"].tolist())
    fig.update_xaxes(title="Movies", range=[0, frame["n_movies"].max() * 1.18])
    _style(fig, bar_height(len(frame)))
    st.plotly_chart(fig, width="stretch", key="genre-breakdown")


def _genre_satisfaction(view: pd.DataFrame, selected: list[str], overall: float) -> None:
    st.header("2. Which genres have the highest average rating? Which have the lowest?")
    weight = st.radio(
        "How to average",
        options=["rating", "movie"],
        format_func=lambda option: (
            "Each rating equally" if option == "rating" else "Each movie equally"
        ),
        horizontal=True,
        key="weight",
    )
    if weight == "rating":
        st.markdown(
            "Each star rating counts once, toward **every genre on that movie**. "
            "A title with 300 ratings pulls its genres harder than a title with one."
        )
    else:
        st.markdown(
            "Each movie counts once: take that movie's average, then average those. "
            "A title with 300 ratings weighs the same as a title with one."
        )
    table = genre_satisfaction(view, selected, weight)
    if table.empty:
        st.info("No genre ratings in this view.")
        return
    unit = table["support_label"].iloc[0]
    best = table.iloc[0]
    worst = table.iloc[-1]
    st.markdown(
        f"Highest is **{best['genre']}** at {best['mean_rating']:.2f} "
        f"({int(best['support']):,} {unit}). "
        f"Lowest is **{worst['genre']}** at {worst['mean_rating']:.2f} "
        f"({int(worst['support']):,} {unit}). "
        f"All ratings in view average {overall:.2f}."
    )
    thin_cut = 50 if weight == "rating" else 10
    if int(worst["support"]) < thin_cut:
        solid = table.loc[table["support"] >= thin_cut]
        if not solid.empty:
            low = solid.iloc[-1]
            st.caption(
                f"{worst['genre']} rests on only {int(worst['support']):,} {unit}. "
                f"The lowest genre with at least {thin_cut:,} {unit} is "
                f"{low['genre']} at {low['mean_rating']:.2f}."
            )
    frame = table.sort_values(["mean_rating", "genre"], ascending=[True, False])
    fig = go.Figure(
        go.Bar(
            x=frame["mean_rating"],
            y=frame["genre"],
            orientation="h",
            marker_color=AMBER,
            text=frame["mean_rating"].map(lambda value: f"{value:.2f}"),
            textposition="outside",
            cliponaxis=False,
            customdata=list(
                zip(frame["support"].astype(int), frame["support_label"], strict=True)
            ),
            hovertemplate=(
                "<b>%{y}</b><br>Average %{x:.3f}<br>%{customdata[0]:,} %{customdata[1]}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_yaxes(categoryorder="array", categoryarray=frame["genre"].tolist())
    fig.update_xaxes(title="Average rating (1 to 5)", range=[0, 5.45])
    _style(fig, bar_height(len(frame)))
    st.plotly_chart(fig, width="stretch", key="genre-satisfaction")


def _over_time(view: pd.DataFrame) -> None:
    st.header("3. How has the mean rating changed across movie release years?")
    st.markdown(
        "The year on the axis is the movie's **release year**, not the year someone "
        "submitted the rating. The file also has a rating-year column, and this chart does not use it."
    )
    min_ratings = st.slider(
        "Hide release years with fewer ratings than",
        min_value=1,
        max_value=200,
        key="min_year_n",
        help="1926 has 2 ratings. Raise this if those thin years are swamping the line.",
    )
    undated_movies, undated_rows = undated_ratings(view)
    if undated_movies:
        st.caption(
            f"{undated_movies} movies ({undated_rows} ratings) have no release year, "
            "so they are left off this line only."
        )
    yearly = ratings_by_release_year(view, min_ratings)
    dated = view.dropna(subset=["year"])
    if yearly.empty:
        st.info("No release year in this view has that many ratings.")
        return
    supported = yearly.loc[yearly["n_ratings"] >= 50]
    if not supported.empty:
        high = supported.loc[supported["mean_rating"].idxmax()]
        low = supported.loc[supported["mean_rating"].idxmin()]
        st.markdown(
            f"Among release years with at least 50 ratings, **{int(high['year'])}** "
            f"is highest at {high['mean_rating']:.2f} ({int(high['n_ratings']):,} ratings) "
            f"and **{int(low['year'])}** is lowest at {low['mean_rating']:.2f} "
            f"({int(low['n_ratings']):,} ratings)."
        )
    reference = float(dated["rating"].mean()) if len(dated) else float("nan")
    size = 8 + 16 * np.sqrt(yearly["n_ratings"] / yearly["n_ratings"].max())
    fig = go.Figure(
        go.Scatter(
            x=yearly["year"],
            y=yearly["mean_rating"],
            mode="lines+markers",
            line=dict(color=BLUE, width=2),
            marker=dict(size=size, color=BLUE),
            customdata=np.column_stack(
                [yearly["mean_rating"], yearly["n_ratings"], yearly["n_movies"]]
            ),
            hovertemplate=(
                "<b>%{x}</b><br>Mean %{customdata[0]:.3f}<br>"
                "%{customdata[1]:,} ratings<br>%{customdata[2]:,} movies<extra></extra>"
            ),
        )
    )
    fig.add_hline(y=reference, line_dash="dot", line_color=AMBER)
    pad = 0.12
    fig.update_yaxes(
        title="Mean rating",
        range=[yearly["mean_rating"].min() - pad, yearly["mean_rating"].max() + pad],
    )
    fig.update_xaxes(title="Release year", dtick=10)
    _style(fig, 460)
    st.plotly_chart(fig, width="stretch", key="release-years")
    st.caption(
        f"Marker area grows with the number of ratings behind that year. "
        f"The dotted line is the mean of ratings that have a release year ({reference:.2f}). "
        "The vertical scale is tightened around the yearly means so the change is readable. "
        "It is not the full 1-to-5 star range."
    )


def _best_movies(view: pd.DataFrame, max_ratings: int) -> None:
    st.header("4. What are the top 5 best-rated movies, with a ratings floor?")
    st.markdown(
        "Best means the plain average of the stars. The floor is how many ratings "
        "a movie needs before it can rank. A tie goes to the movie with more ratings."
    )
    left, right = st.columns(2)
    with left:
        floor_a = st.number_input(
            "Minimum ratings",
            min_value=1,
            max_value=max_ratings,
            step=1,
            key="floor_a",
        )
    with right:
        floor_b = st.number_input(
            "Compare with a second floor",
            min_value=1,
            max_value=max_ratings,
            step=1,
            key="floor_b",
        )
    top_a, n_a = top_movies(view, int(floor_a))
    top_b, n_b = top_movies(view, int(floor_b))
    overall = float(view["rating"].mean())
    _floor_chart(top_a, int(floor_a), n_a, overall, "floor-primary")
    _floor_chart(top_b, int(floor_b), n_b, overall, "floor-compare")
    _floor_change(top_a, int(floor_a), top_b, int(floor_b))


def _floor_chart(
    top: pd.DataFrame,
    floor: int,
    eligible: int,
    overall: float,
    chart_key: str,
) -> None:
    st.subheader(f"At least {floor:,} ratings")
    st.caption(f"{eligible:,} movies clear this floor.")
    if top.empty:
        st.info("No movie has that many ratings in this view.")
        return
    frame = top.sort_values(
        ["mean_rating", "n_ratings", "title"],
        ascending=[True, True, False],
    )
    labels = frame.apply(lambda row: f"{row['mean_rating']:.2f} · {int(row['n_ratings'])}", axis=1)
    low = float(frame["mean_rating"].min())
    high = float(frame["mean_rating"].max())
    # These means sit in a tight band near the top of the scale. A 0-to-5 axis
    # makes the five bars look identical, so the axis starts just under the
    # fifth-place average. Wider spreads (after a filter) keep a zero baseline.
    cropped = high - low < 0.75
    x_min = (low - 0.04) if cropped else 0
    x_max = (high + 0.22) if cropped else 5.6
    fig = go.Figure(
        go.Bar(
            x=frame["mean_rating"],
            y=frame["title"],
            orientation="h",
            marker_color=AMBER,
            text=labels,
            textposition="outside",
            cliponaxis=False,
            customdata=frame["n_ratings"],
            hovertemplate=(
                "<b>%{y}</b><br>Average %{x:.3f}<br>%{customdata:,} ratings<extra></extra>"
            ),
        )
    )
    fig.update_yaxes(categoryorder="array", categoryarray=frame["title"].tolist())
    fig.update_xaxes(title="Average rating", range=[x_min, x_max])
    _style(fig, bar_height(len(frame), row=52))
    st.plotly_chart(fig, width="stretch", key=chart_key)
    if cropped:
        st.caption(
            f"Axis starts at {x_min:.2f}, not at 0. These averages sit close together, "
            f"and all of them are above the {overall:.2f} average of ratings in view."
        )


def _floor_change(
    top_a: pd.DataFrame,
    floor_a: int,
    top_b: pd.DataFrame,
    floor_b: int,
) -> None:
    if floor_a == floor_b:
        st.markdown("Both floors are the same, so the two lists match.")
        return
    low_floor, low_top, high_floor, high_top = (
        (floor_a, top_a, floor_b, top_b)
        if floor_a < floor_b
        else (floor_b, top_b, floor_a, top_a)
    )
    low_titles = low_top["title"].tolist()
    high_titles = high_top["title"].tolist()
    dropped = [title for title in low_titles if title not in set(high_titles)]
    entered = [title for title in high_titles if title not in set(low_titles)]
    if not dropped and not entered:
        st.markdown(
            f"Raising the floor from {low_floor:,} to {high_floor:,} does not change the top {len(low_titles)}."
        )
        return
    st.markdown(
        f"Raising the floor from {low_floor:,} to {high_floor:,} drops "
        f"{_title_list(dropped)}, and brings in {_title_list(entered)}."
    )


def _title_list(titles: list[str]) -> str:
    if not titles:
        return "nothing"
    # Titles already contain commas ("Close Shave, A (1995)"), so separate them
    # with semicolons.
    if len(titles) == 1:
        return titles[0]
    return "; ".join(titles[:-1]) + f"; and {titles[-1]}"


def _init_state(names: list[str], full_min: int, full_max: int, max_ratings: int) -> None:
    if "genres" not in st.session_state:
        st.session_state.genres = names
    if "years" not in st.session_state:
        st.session_state.years = (full_min, full_max)
    if "weight" not in st.session_state:
        st.session_state.weight = "rating"
    if "min_year_n" not in st.session_state:
        st.session_state.min_year_n = 1
    if "floor_a" not in st.session_state:
        st.session_state.floor_a = min(50, max_ratings)
    if "floor_b" not in st.session_state:
        st.session_state.floor_b = min(150, max_ratings)


def _reset(names: list[str], full_min: int, full_max: int) -> None:
    st.session_state.genres = names
    st.session_state.years = (full_min, full_max)
    st.session_state.weight = "rating"
    st.session_state.min_year_n = 1
    st.session_state.floor_a = 50
    st.session_state.floor_b = 150


def _style(fig: go.Figure, height: int) -> None:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, sans-serif", color=INK, size=14),
        margin=dict(l=8, r=88, t=16, b=52),
        showlegend=False,
        hoverlabel=dict(bgcolor=INK, font_color="#fafaf9", font_size=13),
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID, zeroline=False)
    fig.update_yaxes(showgrid=False, automargin=True)


def bar_height(n_bars: int, row: int = 34) -> int:
    return max(280, row * n_bars + 90)


if __name__ == "__main__":
    main()
