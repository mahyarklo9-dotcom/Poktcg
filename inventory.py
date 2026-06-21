import aiosqlite

DB_NAME = "database.db"


async def add_card(user_id, card_id, card_name, rarity="Unknown", image=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO inventory(user_id, card_id, card_name, rarity, image)
            VALUES(?,?,?,?,?)
            """,
            (user_id, card_id, card_name, rarity, image)
        )
        await db.commit()


async def get_inventory(user_id):
    """برای /inv — برمی‌گردونه (card_name, rarity, card_id, image, count)

    نکته‌ی مهم: گروه‌بندی روی (card_name, rarity) انجام می‌شه، نه فقط
    card_name. اگه فقط روی card_name گروه‌بندی بشه، یک کارت هولو و
    نسخه‌ی معمولیِ همون کارت با هم قاطی می‌شن و SQLite به‌صورت دلخواه
    فقط یکی از rarity/card_id/image رو نشون می‌ده (باگ قبلی).

    برای این‌که card_id و image همیشه از یک ردیفِ مشخص (نه دلخواه)
    بیان، اول کوچیک‌ترین id هر گروه رو پیدا می‌کنیم و بعد جزئیات رو
    دقیقاً از همون ردیف می‌خونیم.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT i.card_name, i.rarity, i.card_id, i.image, g.cnt
            FROM inventory i
            JOIN (
                SELECT card_name, rarity, MIN(id) as min_id, COUNT(*) as cnt
                FROM inventory
                WHERE user_id=?
                GROUP BY card_name, rarity
            ) g ON g.min_id = i.id
            ORDER BY i.card_name
            """,
            (user_id, )
        )
        return await cur.fetchall()


async def get_all_cards(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT id, card_id, card_name, rarity
            FROM inventory
            WHERE user_id=?
            """,
            (user_id,)
        )
        return await cur.fetchall()


async def remove_card(user_id, card_name):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id FROM inventory WHERE user_id=? AND card_name=? LIMIT 1",
            (user_id, card_name)
        )
        row = await cur.fetchone()
        if not row:
            return False
        await db.execute("DELETE FROM inventory WHERE id=?", (row[0],))
        await db.commit()
        return True


async def has_card(user_id, card_name):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM inventory WHERE user_id=? AND card_name=?",
            (user_id, card_name)
        )
        row = await cur.fetchone()
        return row[0] > 0


async def transfer_card(from_user, to_user, card_name):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT card_id, card_name, rarity, id, image FROM inventory WHERE user_id=? AND card_name=? LIMIT 1",
            (from_user, card_name)
        )
        card = await cur.fetchone()
        if not card:
            return False
        await db.execute(
            "INSERT INTO inventory(user_id, card_id, card_name, rarity, image) VALUES(?,?,?,?,?)",
            (to_user, card[0], card[1], card[2], card[4])
        )
        await db.execute("DELETE FROM inventory WHERE id=?", (card[3],))
        await db.commit()
        return True
