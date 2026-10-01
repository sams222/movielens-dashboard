# Build log

Raw notes from building the MovieLens dashboard. Kept so next week's write-up can use the real prompts and choices, not a reconstruction.

## Moment 1 — Genre breakdown

Prompt (from the assignment): "What's the distribution of genres among the movies that were rated? Movies can have multiple genres — have the AI explain how it handled that before it counts anything."

What I checked before counting: the file is one row per rating, `genres` is pipe-separated, and a title like L.A. Confidential is `Crime|Film-Noir|Mystery|Thriller`. 1,682 movies, 2,893 genre tags.

First instinct the chart table warns about: a pie, or counting rating rows so popular movies dominate. I did not do either.

Decision: count distinct movies, once per genre tag. Drama|War adds one to Drama and one to War. Bars are sorted by count, horizontal, because there are 19 tags and they are not slices of a whole (they sum to 2,893, not 1,682). Drama is on 725 movies. The `unknown` tag is 2 movies; I left it in rather than deleting it quietly.

## Moment 2 — What "average rating" means

Prompt: "Which genres have the highest average rating? Which have the lowest?"

I computed both versions before picking one.

- Each rating equally: Film-Noir 3.92 (1,733 ratings), unknown 3.20 (10 ratings). Next lowest with any real support is Fantasy at 3.22.
- Each movie equally: Film-Noir still first, but the middle moves. Musical rises, Drama drops, Horror becomes the low end once `unknown` is set aside.

Default is each rating equally, because "average rating" is the mean of the stars people gave. The other definition is a radio button on that chart, since the two answers are not the same list. The axis starts at 0 and runs to 5 so a 0.7-star gap is not stretched.

## Moment 3 — Release year, not the year someone rated it

Prompt: "How has the mean rating changed across movie release years?"

The file has `year`, `rating_year`, and `timestamp`. The question is about when the movie came out, so the line uses `year`. Five movies (30 ratings) have no release year, including a row titled "unknown". They stay in the other charts and are left off this line.

I did not smooth it. 1926 is a mean of 3.0 from 2 ratings, and a rolling average would hide that. Marker area grows with the number of ratings. The vertical scale is tightened around the yearly means (they live between about 3.0 and 4.4), and the caption says it is not the 1-to-5 scale. Among years with at least 50 ratings, 1942 is highest (4.40) and 1998 is lowest (3.30).

## Moment 4 — The floor, and a chart that didn't work

Prompt: "What are the top 5 best-rated movies, once you only count movies with at least 50 ratings? What changes if you raise that floor to 150?"

Rule: arithmetic mean. Floor is the number of ratings. Tie goes to more ratings, then title.

At 50 the top five are Close Shave, Schindler's List, The Wrong Trousers, Casablanca, and the Wallace & Gromit compilation. At 150 the three shorter titles drop (67, 112, and 118 ratings) and Shawshank, Rear Window, and The Usual Suspects come in. Schindler's List and Casablanca survive both cuts.

First drawing used a 0-to-5 axis. The five bars looked identical, because 4.39 and 4.49 are the same length on that scale. I changed it: when the top five sit in a tight band, the axis starts just under fifth place, and the caption says it does not start at 0. Labels still show the mean and the rating count.

Second bug, found while moving the floor to 200: Streamlit crashed with a duplicate element id, because the 150 chart and the 200 chart were the same five movies and Streamlit treated them as one widget. Each chart now has its own key.

## What the controls do

- Genre list and release-year range limit every chart. Full span is the assigned question. Narrowing the years drops movies with no release year.
- "How to average" only changes question 2.
- "Hide release years with fewer ratings than" only changes question 3. Default is 1, so 1926 stays.
- Two floors, default 50 and 150, are question 4.
