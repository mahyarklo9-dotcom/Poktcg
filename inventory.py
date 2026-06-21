import aiosqlite

DB_NAME = "database.db"

async def add_card(user_id, card_id, card_name, rarity="Unknown"):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO inventory(user_id, card_id, card_name, rarity)
            VALUES(?,?,?,?)
            """,
            (user_id, card_id, card_name, rarity)
        )
        await db.commit()


async def get_inventory(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT card_name, COUNT(*)
            FROM inventory
            WHERE user_id=?
            GROUP BY card_name
            ORDER BY card_name
            """,
            (user_id,)
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
            """
            SELECT id
            FROM inventory
            WHERE user_id=? AND card_name=?
            LIMIT 1
            """,
            (user_id, card_name)
        )

        row = await cur.fetchone()

        if not row:
            return False

        await db.execute(
            "DELETE FROM inventory WHERE id=?",
            (row[0],)
        )

        await db.commit()
        return True


async def has_card(user_id, card_name):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT COUNT(*)
            FROM inventory
            WHERE user_id=? AND card_name=?
            """,
            (user_id, card_name)
        )

        row = await cur.fetchone()
        return row[0] > 0


async def transfer_card(from_user, to_user, card_name):

    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute(
            """
            SELECT card_id, card_name, rarity, id
            FROM inventory
            WHERE user_id=? AND card_name=?
            LIMIT 1
            """,
            (from_user, card_name)
        )

        card = await cur.fetchone()

        if not card:
            return False

        await db.execute(
            """
            INSERT INTO inventory(user_id, card_id, card_name, rarity)
            VALUES(?,?,?,?)
            """,
            (to_user, card[0], card[1], card[2])
        )

        await db.execute(
            "DELETE FROM inventory WHERE id=?",
            (card[3],)
        )

        await db.commit()

        return True
