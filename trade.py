import aiosqlite
from inventory import has_card, transfer_card

DB_NAME = "database.db"

async def create_trade(user1, user2, card1, card2):
    if not await has_card(user1, card1):
        return None

    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            INSERT INTO trades(user1,user2,card1,card2,status)
            VALUES(?,?,?,?, 'pending')
        """, (user1,user2,card1,card2))
        await db.commit()
        return cur.lastrowid

async def accept_trade(trade_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT user1,user2,card1,card2,status FROM trades WHERE id=?",
            (trade_id,)
        )
        trade = await cur.fetchone()
        if not trade or trade[4] != "pending":
            return False

        if not await has_card(trade[0], trade[2]):
            return False
        if not await has_card(trade[1], trade[3]):
            return False

        await transfer_card(trade[0], trade[1], trade[2])
        await transfer_card(trade[1], trade[0], trade[3])

        await db.execute("UPDATE trades SET status='accepted' WHERE id=?", (trade_id,))
        await db.commit()
        return True

async def reject_trade(trade_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE trades SET status='rejected' WHERE id=?", (trade_id,))
        await db.commit()

async def get_trade(trade_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT * FROM trades WHERE id=?", (trade_id,))
        return await cur.fetchone()

async def get_pending_trades(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT * FROM trades WHERE user2=? AND status='pending'",
            (user_id,)
        )
        return await cur.fetchall()
