# NJN KASHTAPETT ONDAKKIYE REPO EEDIT CHEYAN THANIKK ULUPP ONDO.
# (c) @mayflower10
# Redistribution is not allowed.

import asyncio
import logging

from decouple import config
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from helpers import time_formatter

# initializing logger
logging.basicConfig(
    level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message)s"
)
log = logging.getLogger("TelethonSnippets")

# fetching variales from env
try:
    API_ID = config("API_ID", cast=int)
    API_HASH = config("API_HASH")
    SESSION = config("SESSION")
    DELETE_IN = config("DELETE_IN")
    WORK_CHAT_IDS = config(
        "WORK_CHAT_IDS", cast=lambda v: [int(x) for x in v.split(" ")]
    )
except BaseException as ex:
    log.info(ex)


log.info("Connecting bot.")
try:
    client = TelegramClient(
        StringSession(SESSION), api_id=API_ID, api_hash=API_HASH
    ).start()
except BaseException as e:
    log.warning(e)
    exit(1)

time_to_del = time_formatter(DELETE_IN)

if time_to_del is None:
    log.info("Invalid time unit. Exiting.")
    exit(1)


@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def on_pm_message(event):
    await event.reply(
        "Hi. I'm an auto deleter userbot. I can delete messages in chats after a specific time interval.\nYou cannot use me here, contact @adishsuresh "
    )


@client.on(events.NewMessage(chats=WORK_CHAT_IDS))
async def listen_to_delete(event):
    await asyncio.sleep(time_to_del)
    try:
        await event.delete()
    except Exception as exc:
        log.error(
            "Unable to delete message from %d in chat %s [%d] due to the following error:\n%s",
            event.sender_id,
            event.chat.title,
            event.chat_id,
            exc,
        )


ubot_self = client.loop.run_until_complete(client.get_me())
log.info("\nClient has started as %d.\n", ubot_self.id)
client.run_until_disconnected()
