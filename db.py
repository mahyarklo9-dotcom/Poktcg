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
            rarity TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS market(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            card_id TEXT,
            card_name TEXT,
            price INTEGER,
            active INTEGER DEFAULT 1
        )
        """)

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
