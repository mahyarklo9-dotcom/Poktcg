import time
import aiosqlite

DB_NAME = "database.db"

MONY_MIN = 30
MONY_MAX = 120
PACK_PRICE = 30
MONY_COOLDOWN = 3600


async def get_user(db, user_id):
    cur = await db.execute(
        "SELECT user_id, money, packs, last_mony FROM users WHERE user_id=?",
        (user_id,)
    )
    return await cur.fetchone()


async def ensure_user(user_id, username=""):
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(db, user_id)

        if not user:
            await db.execute(
                "INSERT INTO users(user_id, username, money, packs) VALUES(?,?,0,0)",
                (user_id, username)
            )
            await db.commit()


async def get_balance(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT money FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def add_money(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET money = money + ? WHERE user_id=?",
            (amount, user_id)
        )
        await db.commit()


async def remove_money(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT money FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()

        if not row or row[0] < amount:
            return False

        await db.execute(
            "UPDATE users SET money = money - ? WHERE user_id=?",
            (amount, user_id)
        )
        await db.commit()
        return True


async def can_claim_mony(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT last_mony FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()

        if not row:
            return True, 0

        remain = MONY_COOLDOWN - (int(time.time()) - row[0])

        if remain > 0:
            return False, remain

        return True, 0


async def update_mony_time(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET last_mony=? WHERE user_id=?",
            (int(time.time()), user_id)
        )
        await db.commit()


async def buy_pack(user_id):
    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute(
            "SELECT money FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()

        if not row or row[0] < PACK_PRICE:
            return False

        await db.execute(
            "UPDATE users SET money = money - ?, packs = packs + 1 WHERE user_id=?",
            (PACK_PRICE, user_id)
        )

        await db.commit()
        return True


async def get_packs(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT packs FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def consume_pack(user_id):
    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute(
            "SELECT packs FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()

        if not row or row[0] <= 0:
            return False

        await db.execute(
            "UPDATE users SET packs = packs - 1 WHERE user_id=?",
            (user_id,)
        )

        await db.commit()
        return True
