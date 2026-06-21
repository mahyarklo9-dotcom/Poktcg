import asyncio
import random
import time

import aiohttp

BASE_URL = "https://api.tcgdex.net/v2/en"

# How long to keep the full card list cached before refreshing (seconds)
CACHE_TTL = 3600

_cache_lock = asyncio.Lock()
_cards_cache = []
_cache_time = 0


async def _fetch_json(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
            if response.status != 200:
                return None
            return await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None


async def get_all_cards(force_refresh=False):
    """Return the cached brief card list (id, name, image), refreshing
    from the TCGdex API when the cache is empty or stale."""
    global _cards_cache, _cache_time

    now = time.time()
    if not force_refresh and _cards_cache and (now - _cache_time) < CACHE_TTL:
        return _cards_cache

    async with _cache_lock:
        # Another task may have refreshed the cache while we waited
        now = time.time()
        if not force_refresh and _cards_cache and (now - _cache_time) < CACHE_TTL:
            return _cards_cache

        async with aiohttp.ClientSession() as session:
            data = await _fetch_json(session, f"{BASE_URL}/cards")

        if data:
            _cards_cache = data
            _cache_time = time.time()
        return _cards_cache


async def get_random_cards(count=8):
    """Return `count` random brief cards (id, name, image)."""
    cards = await get_all_cards()
    if not cards:
        return []
    return random.sample(cards, min(count, len(cards)))


async def get_card(card_id):
    """Return the full card object (includes rarity, hp, attacks, etc.)."""
    async with aiohttp.ClientSession() as session:
        return await _fetch_json(session, f"{BASE_URL}/cards/{card_id}")


async def get_random_cards_detailed(count=8):
    """Pick `count` random cards and fetch full details for each one
    (so rarity is available), used when opening a pack."""
    briefs = await get_random_cards(count)
    if not briefs:
        return []

    async with aiohttp.ClientSession() as session:
        tasks = [_fetch_json(session, f"{BASE_URL}/cards/{c['id']}") for c in briefs]
        results = await asyncio.gather(*tasks)

    detailed = []
    for brief, full in zip(briefs, results):
        if full:
            detailed.append(full)
        else:
            # API hiccup on the detail call: fall back to the brief data
            detailed.append({**brief, "rarity": "Unknown"})
    return detailed


def build_image_url(image_base, quality="high", ext="png"):
    """TCGdex image URLs are returned without quality/extension, e.g.
    'https://assets.tcgdex.net/en/swsh/swsh3/136' and need
    '/high.png' (or '/low.webp', etc.) appended."""
    if not image_base:
        return None
    return f"{image_base}/{quality}.{ext}"


async def get_card_image(card_id_or_card, quality="high", ext="png"):
    """Accepts either a card_id (str) or an already-fetched card dict."""
    card = card_id_or_card
    if isinstance(card_id_or_card, str):
        card = await get_card(card_id_or_card)

    if not card:
        return None

    image = card.get("image")
    return build_image_url(image, quality, ext)
