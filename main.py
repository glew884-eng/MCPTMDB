"""Minimal MCP server exposing a few TMDB (The Movie Database) tools."""
import os

import httpx
from fastmcp import FastMCP

TMDB_BASE = "https://api.themoviedb.org/3"
DEFAULT_LANG = os.environ.get("TMDB_LANGUAGE", "fr-FR")

mcp = FastMCP("TMDB")


async def tmdb_get(path: str, **params) -> dict:
    """Call the TMDB API using the v4 Read Access Token (Bearer)."""
    token = os.environ.get("TMDB_API_TOKEN")
    if not token:
        raise RuntimeError("TMDB_API_TOKEN environment variable is not set")
    params.setdefault("language", DEFAULT_LANG)
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{TMDB_BASE}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
        )
        r.raise_for_status()
        return r.json()


def _slim(item: dict) -> dict:
    """Keep only the fields useful to the model."""
    return {
        "id": item.get("id"),
        "title": item.get("title") or item.get("name"),
        "date": item.get("release_date") or item.get("first_air_date"),
        "rating": item.get("vote_average"),
        "overview": item.get("overview"),
    }


@mcp.tool()
async def search_movies(query: str, year: int | None = None) -> list[dict]:
    """Search movies by title. Optionally filter by release year."""
    params = {"query": query}
    if year:
        params["year"] = year
    data = await tmdb_get("/search/movie", **params)
    return [_slim(m) for m in data.get("results", [])[:10]]


@mcp.tool()
async def search_tv(query: str) -> list[dict]:
    """Search TV series by title."""
    data = await tmdb_get("/search/tv", query=query)
    return [_slim(t) for t in data.get("results", [])[:10]]


@mcp.tool()
async def get_movie_details(movie_id: int) -> dict:
    """Get details for a movie (genres, runtime, top cast, director) from its TMDB id."""
    d = await tmdb_get(f"/movie/{movie_id}", append_to_response="credits")
    crew = d.get("credits", {}).get("crew", [])
    cast = d.get("credits", {}).get("cast", [])
    return {
        **_slim(d),
        "tagline": d.get("tagline"),
        "runtime_min": d.get("runtime"),
        "genres": [g["name"] for g in d.get("genres", [])],
        "directors": [c["name"] for c in crew if c.get("job") == "Director"],
        "top_cast": [c["name"] for c in cast[:8]],
    }


@mcp.tool()
async def get_trending(media_type: str = "movie", window: str = "week") -> list[dict]:
    """Get trending titles. media_type: 'movie' or 'tv'. window: 'day' or 'week'."""
    if media_type not in ("movie", "tv") or window not in ("day", "week"):
        raise ValueError("media_type must be movie|tv and window must be day|week")
    data = await tmdb_get(f"/trending/{media_type}/{window}")
    return [_slim(m) for m in data.get("results", [])[:10]]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
