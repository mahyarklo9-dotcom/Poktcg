"""
pack_session.py
---------------
نگهداری وضعیت باز کردن پک در RAM (بدون نیاز به DB اضافی).
هر session با کلید (user_id, message_id) شناسایی می‌شه.
"""

import asyncio
from dataclasses import dataclass, field

# ── ساختار یک session باز کردن پک ─────────────────────────────────────────

@dataclass
class PackSession:
    user_id: int
    cards: list          # لیست دیکشنری کارت‌های کامل
    current: int = 0     # ایندکس کارتی که باید بعدی نمایش داده شه
    done: bool = False   # آیا همه کارت‌ها نمایش داده شدن؟

# ── ذخیره‌گاه session ها ────────────────────────────────────────────────────
# کلید: (user_id, msg_id)  مقدار: PackSession
_sessions: dict[tuple[int, int], PackSession] = {}
_lock = asyncio.Lock()

# ── API ─────────────────────────────────────────────────────────────────────

async def create_session(user_id: int, msg_id: int, cards: list) -> PackSession:
    async with _lock:
        session = PackSession(user_id=user_id, cards=cards)
        _sessions[(user_id, msg_id)] = session
        return session


async def get_session(user_id: int, msg_id: int) -> PackSession | None:
    async with _lock:
        return _sessions.get((user_id, msg_id))


async def advance_session(user_id: int, msg_id: int) -> tuple[dict | None, bool]:
    """
    کارت فعلی را برمی‌گرداند و ایندکس را یک واحد جلو می‌بره.
    برمی‌گرداند: (card_dict, is_last)
    اگه session وجود نداشت یا تموم شده بود: (None, True)
    """
    async with _lock:
        session = _sessions.get((user_id, msg_id))
        if not session or session.done:
            return None, True

        card = session.cards[session.current]
        session.current += 1

        if session.current >= len(session.cards):
            session.done = True
            del _sessions[(user_id, msg_id)]

        is_last = session.done
        return card, is_last


async def cleanup_session(user_id: int, msg_id: int):
    async with _lock:
        _sessions.pop((user_id, msg_id), None)
