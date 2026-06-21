import aiosqlite
from inventory import has_card, transfer_card
from economy import add_money, remove_money

DB_NAME = "database.db"

async def list_card_for_sale(user_id, card_name, price):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            SELECT id, card_id FROM inventory
            WHERE user_id=? AND card_name=? LIMIT 1
        """, (user_id, card_name))
        card = await cur.fetchone()

        if not card:
            return False

        await db.execute("""
            INSERT INTO market(seller_id, card_id, card_name, price)
            VALUES(?,?,?,?)
        """, (user_id, card[1], card_name, price))

        await db.execute("DELETE FROM inventory WHERE id=?", (card[0],))
        await db.commit()
        return True

async def get_market_cards():
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id,seller_id,card_name,price FROM market WHERE active=1"
        )
        return await cur.fetchall()

async def buy_card(buyer_id, sale_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT seller_id,card_id,card_name,price FROM market WHERE id=? AND active=1",
            (sale_id,)
        )
        sale = await cur.fetchone()
        if not sale:
            return False

        seller_id, card_id, card_name, price = sale
        if not await remove_money(buyer_id, price):
            return False

        await add_money(seller_id, price)
        await db.execute(
            "INSERT INTO inventory(user_id,card_id,card_name,rarity) VALUES(?,?,?,?)",
            (buyer_id, card_id, card_name, "Unknown")
        )
        await db.execute("UPDATE market SET active=0 WHERE id=?", (sale_id,))
        await db.commit()
        return True

async def cancel_sale(user_id, sale_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT card_id,card_name FROM market WHERE id=? AND seller_id=? AND active=1",
            (sale_id, user_id)
        )
        sale = await cur.fetchone()
        if not sale:
            return False

        await db.execute(
            "INSERT INTO inventory(user_id,card_id,card_name,rarity) VALUES(?,?,?,?)",
            (user_id, sale[0], sale[1], "Unknown")
        )
        await db.execute("UPDATE market SET active=0 WHERE id=?", (sale_id,))
        await db.commit()
        return True

async def get_user_sales(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id,card_name,price,active FROM market WHERE seller_id=?",
            (user_id,)
        )
        return await cur.fetchall()
