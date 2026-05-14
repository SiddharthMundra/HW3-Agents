"""Tools the meme finder agent can call. Each docstring becomes its tool description."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from agents import function_tool
from agents.run_context import RunContextWrapper

from meme_agent.config import default_model, vision_client
from meme_agent.context import MemeContext

MAX_IMAGE_BYTES = 8 * 1024 * 1024
CACHE_DIR = Path(".meme_cache")
EXPORT_DIR = Path("exports")


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-]", "_", base)
    return base[:160] or "report.md"


@function_tool
async def fetch_meme_image(ctx: RunContextWrapper[MemeContext], image_url: str) -> str:
    """Download an https meme image into a local cache so it can be analyzed.

    SAFE: read-only network fetch. Always allowed.

    Args:
        image_url: Public http(s) URL pointing at a PNG/JPEG/GIF/WebP image.
    """
    parsed = urlparse(image_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "ERROR: only http(s) URLs with a host are allowed."

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 MemeFinderBot/1.0"},
        ) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            body = resp.content
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    except Exception as exc:  # noqa: BLE001
        ctx.context.activity.append(f"❌ fetch_meme_image failed: {exc}")
        return f"ERROR: download failed: {exc}"

    if len(body) > MAX_IMAGE_BYTES:
        return f"ERROR: image too large ({len(body)} bytes)."
    if ctype and not ctype.startswith("image/"):
        return f"ERROR: expected image content-type, got {ctype!r}."

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ext = mimetypes.guess_extension(ctype) if ctype else ".jpg"
    if not ext:
        ext = ".jpg"
    fname = f"{abs(hash(image_url)) % (10 ** 12)}{ext}"
    path = CACHE_DIR / fname
    path.write_bytes(body)

    ctx.context.fetched_image_url = image_url
    ctx.context.fetched_image_path = str(path)
    ctx.context.activity.append(f"📥 fetched image ({len(body):,} bytes)")
    return f"Image saved to {path} ({len(body)} bytes). Call analyze_meme_image next."


@function_tool
async def analyze_meme_image(ctx: RunContextWrapper[MemeContext]) -> str:
    """Use a vision model to read on-image text and describe the meme.

    SAFE: vision call on the previously fetched image. Always allowed.
    """
    path_str = ctx.context.fetched_image_path
    if not path_str or not Path(path_str).is_file():
        return "ERROR: no fetched image. Call fetch_meme_image(image_url=...) first."

    raw = Path(path_str).read_bytes()
    mime = mimetypes.guess_type(path_str)[0] or "image/jpeg"
    data_url = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

    client = vision_client()
    try:
        resp = await client.chat.completions.create(
            model=default_model(),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "You are looking at a meme image. Return:\n"
                                "1. Verbatim transcription of ALL visible text (top text, bottom text, captions, watermarks).\n"
                                "2. Subjects / template (e.g. 'Drake Hotline Bling', 'Distracted Boyfriend', 'Surprised Pikachu').\n"
                                "3. Tone (wholesome, sarcastic, ironic, political, absurd, etc).\n"
                                "4. Any recognizable characters, shows, or franchises depicted.\n"
                                "DO NOT invent meme names, dates, or origin stories — that's another tool's job."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=600,
        )
    except Exception as exc:  # noqa: BLE001
        ctx.context.activity.append(f"❌ analyze_meme_image failed: {exc}")
        return f"ERROR: vision call failed: {exc}"

    ctx.context.vision_runs += 1
    ctx.context.activity.append("🔍 analyzed image with vision model")
    return (resp.choices[0].message.content or "").strip()


def _ddg_search(query: str, max_results: int) -> list[dict]:
    """Try the modern ddgs package with one retry, fall back to legacy package."""
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            try:
                from ddgs import DDGS  # modern package
            except ImportError:
                from duckduckgo_search import DDGS  # legacy
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt == 0:
                time.sleep(1.5)
    if last_err:
        raise last_err
    return []


@function_tool
async def web_search(
    ctx: RunContextWrapper[MemeContext],
    query: str,
    max_results: int = 6,
) -> str:
    """Search the public web for meme name / origin write-ups (DuckDuckGo).

    SAFE: read-only public search. Always allowed. Call this 2–4 times with
    different queries when researching a meme.

    Args:
        query: Specific search query. Include distinctive on-image text or the
            character + show name.
        max_results: 1..10 results to return.
    """
    max_results = max(1, min(int(max_results), 10))
    try:
        rows = await asyncio.to_thread(_ddg_search, query, max_results)
    except Exception as exc:  # noqa: BLE001
        ctx.context.activity.append(f"❌ web_search('{query}') failed: {exc}")
        return f"ERROR: web search failed: {exc}"

    ctx.context.web_searches += 1
    if not rows:
        ctx.context.activity.append(f"🔎 web_search('{query}') → 0 results")
        return (
            f"No web results for '{query}'. Try a different query (different "
            "wording, add the show/character name, or use distinctive on-image text)."
        )

    ctx.context.web_search_hits += len(rows)
    ctx.context.activity.append(f"🔎 web_search('{query}') → {len(rows)} results")
    parts: list[str] = []
    for i, row in enumerate(rows, start=1):
        title = (row.get("title") or "").strip()
        url = (row.get("href") or "").strip()
        body = (row.get("body") or "").strip()
        snippet = f"{title}\nURL: {url}\n{body}"
        ctx.context.last_search_snippets.append(snippet[:1200])
        parts.append(f"--- Result {i} ---\n{snippet}")
    return "\n\n".join(parts)


@function_tool
async def save_report(
    ctx: RunContextWrapper[MemeContext],
    filename: str,
    markdown_body: str,
) -> str:
    """Save a markdown report to ./exports/. REQUIRES USER CONFIRMATION.

    The host app must enable "Allow saving reports" — without it this tool refuses.

    Args:
        filename: e.g. ``doge_report.md``. Subdirectories not allowed.
        markdown_body: full markdown text to write.
    """
    if not ctx.context.user_allows_disk_write:
        ctx.context.activity.append("🚫 save_report refused — toggle is off")
        return (
            "SAVE_DENIED: disk export is disabled. Tell the user to enable "
            "'Allow saving reports' in the controls, then retry."
        )

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = (EXPORT_DIR / _safe_filename(filename)).resolve()
    if not str(path).startswith(str(EXPORT_DIR.resolve())):
        return "ERROR: path escapes ./exports/."
    path.write_text(markdown_body, encoding="utf-8")
    ctx.context.activity.append(f"💾 saved report → {path.name}")
    return f"Saved report to {path}"
