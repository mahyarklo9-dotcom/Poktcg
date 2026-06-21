import aiosqlite

DB_NAME = "database.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            money INTEGER DEFAULT 0,
            packs INTEGER DEFAULT 0,
            last_mony INTEGER DEFAULT 0
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS inventory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            card_id TEXT,
            card_name TEXT,
            rarity TEXT,
            image TEXT
        )
        """)

        # برای کسایی که قبلاً دیتابیس ساخته بودن (بدون ستون image)،
        # ستون رو اضافه می‌کنیم تا با خطا مواجه نشن.
        cur = await db.execute("PRAGMA table_info(inventory)")
        cols = [row[1] for row in await cur.fetchall()]
        if "image" not in cols:
            await db.execute("ALTER TABLE inventory ADD COLUMN image TEXT")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS market(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            card_id TEXT,
            card_name TEXT,
            price INTEGER,
            active INTEGER DEFAULT 1,
            image TEXT,
            rarity TEXT
        )
        """)

        cur = await db.execute("PRAGMA table_info(market)")
        cols = [row[1] for row in await cur.fetchall()]
        if "image" not in cols:
            await db.execute("ALTER TABLE market ADD COLUMN image TEXT")
        if "rarity" not in cols:
            await db.execute("ALTER TABLE market ADD COLUMN rarity TEXT")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS trades(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1 INTEGER,
            user2 INTEGER,
            card1 TEXT,
            card2 TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

        await db.commit()
