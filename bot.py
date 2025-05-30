# Enhanced AutoDeleterUBot with improved cleanup timing
# (c) @xditya
# Redistribution is not allowed.

import asyncio
import logging
from datetime import datetime, timedelta

from decouple import config
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty

from helpers import time_formatter

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("AutoDeleterUBot")

# Load configuration from environment variables
try:
    API_ID = config("API_ID", cast=int)
    API_HASH = config("API_HASH")
    SESSION = config("SESSION")
    DELETE_IN = config("DELETE_IN", default="30m")
    WORK_CHAT_IDS = config(
        "WORK_CHAT_IDS",
        cast=lambda v: [int(x) for x in v.split()] if v else [],
        default=""
    )
    ADMIN_IDS = config(
        "ADMIN_IDS",
        cast=lambda v: [int(x) for x in v.split()] if v else [],
        default=""
    )
except Exception as ex:
    log.error("Configuration error: %s", ex)
    exit(1)

# Global variables
connected_groups = {}
time_to_del = time_formatter(DELETE_IN)

if time_to_del is None:
    log.error("Invalid DELETE_IN format. Use like '30m', '1h', etc.")
    exit(1)

# Initialize Telegram client
try:
    client = TelegramClient(
        StringSession(SESSION),
        api_id=API_ID,
        api_hash=API_HASH
    )
except Exception as e:
    log.error("Client initialization failed: %s", e)
    exit(1)

async def update_connected_groups():
    """Update the list of connected groups with their info"""
    global connected_groups
    connected_groups.clear()
    
    try:
        result = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=200,
            hash=0
        ))
        
        for chat in result.chats:
            if chat.id in WORK_CHAT_IDS:
                connected_groups[chat.id] = {
                    'title': chat.title,
                    'link': f"https://t.me/{chat.username}" if getattr(chat, 'username', None) else None,
                    'last_cleanup': None
                }
    except Exception as e:
        log.error("Failed to update group list: %s", e)

async def perform_cleanup(chat_id):
    """Perform complete message cleanup in a specific chat"""
    try:
        log.info("Starting cleanup in chat %d", chat_id)
        now = datetime.now()
        deletion_threshold = now - timedelta(seconds=time_to_del)
        
        async for message in client.iter_messages(chat_id):
            try:
                if message.date < deletion_threshold:
                    await message.delete()
                    await asyncio.sleep(0.5)  # Rate limiting
            except Exception as e:
                log.warning("Failed to delete message in %d: %s", chat_id, e)
                continue
        
        connected_groups[chat_id]['last_cleanup'] = now
        log.info("Cleanup completed for chat %d", chat_id)
        return True
    except Exception as e:
        log.error("Cleanup failed for chat %d: %s", chat_id, e)
        return False

async def periodic_cleanup():
    """Periodically clean up all messages in connected groups"""
    while True:
        # Wait for DELETE_IN + 10 minutes
        await asyncio.sleep(time_to_del + 600)
        log.info("Starting periodic cleanup (DELETE_IN + 10min)")
        
        for chat_id in list(WORK_CHAT_IDS):
            try:
                success = await perform_cleanup(chat_id)
                if not success:
                    log.warning("Retrying cleanup for chat %d", chat_id)
                    await asyncio.sleep(5)
                    await perform_cleanup(chat_id)
            except Exception as e:
                log.error("Periodic cleanup error in %d: %s", chat_id, e)
                continue

async def is_admin(event):
    """Check if the user is an admin"""
    if event.sender_id in ADMIN_IDS:
        return True
    
    try:
        if event.is_group or event.is_channel:
            participant = await event.client.get_permissions(event.chat_id, event.sender_id)
            return participant.is_admin
    except Exception:
        pass
    return False

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def on_pm_message(event):
    """Handle private messages"""
    help_text = """Evde message ayknda mwne"""
    await event.reply(
        help_text.format(
            DELETE_IN=DELETE_IN,
            group_count=len(WORK_CHAT_IDS)
        ),
        parse_mode='html'
    )

@client.on(events.NewMessage(chats=WORK_CHAT_IDS))
async def listen_to_delete(event):
    """Delete messages after the specified time"""
    await asyncio.sleep(time_to_del)
    try:
        await event.delete()
    except Exception as e:
        log.error("Delete failed in %d: %s", event.chat_id, e)

@client.on(events.NewMessage(pattern=r'^/connect$'))
async def connect_group(event):
    """Connect current group to the bot"""
    if event.is_private:
        return
    
    if not await is_admin(event):
        await event.reply("🚫 You need to be an admin to use this command!")
        return
    
    if event.chat_id not in WORK_CHAT_IDS:
        WORK_CHAT_IDS.append(event.chat_id)
        await update_connected_groups()
        reply = await event.reply(
            f"✅ <b>Group connected!</b>\n"
            f"• Messages will auto-delete after: <code>{DELETE_IN}</code>\n"
            f"• Next full cleanup in: <code>{DELETE_IN} + 10min</code>",
            parse_mode='html'
        )
        await asyncio.sleep(30)
        await reply.delete()
    else:
        reply = await event.reply("ℹ️ This group is already connected!")
        await asyncio.sleep(10)
        await reply.delete()

@client.on(events.NewMessage(pattern=r'^/disconnect$'))
async def disconnect_group(event):
    """Disconnect current group from the bot"""
    if event.is_private:
        return
    
    if not await is_admin(event):
        await event.reply("🚫 You need to be an admin to use this command!")
        return
    
    if event.chat_id in WORK_CHAT_IDS:
        WORK_CHAT_IDS.remove(event.chat_id)
        await update_connected_groups()
        reply = await event.reply("❌ <b>Group disconnected!</b>", parse_mode='html')
        await asyncio.sleep(30)
        await reply.delete()
    else:
        reply = await event.reply("ℹ️ This group wasn't connected!")
        await asyncio.sleep(10)
        await reply.delete()

@client.on(events.NewMessage(pattern=r'^/listgroups$'))
async def list_groups(event):
    """List all connected groups"""
    if not WORK_CHAT_IDS:
        await event.reply("No groups are currently connected.")
        return
    
    response = "📋 <b>Connected Groups</b>:\n\n"
    for chat_id, info in connected_groups.items():
        last_clean = info['last_cleanup'].strftime("%Y-%m-%d %H:%M") if info['last_cleanup'] else "Never"
        link_text = f" | <a href='{info['link']}'>Join</a>" if info['link'] else ""
        response += f"• <b>{info['title']}</b>{link_text}\n   Last cleanup: <code>{last_clean}</code>\n\n"
    
    await event.reply(response, parse_mode='html', link_preview=False)

@client.on(events.NewMessage(pattern=r'^/cleannow$'))
async def force_cleanup(event):
    """Force immediate cleanup"""
    if event.is_private:
        return
    
    if not await is_admin(event):
        await event.reply("🚫 You need to be an admin to use this command!")
        return
    
    if event.chat_id not in WORK_CHAT_IDS:
        await event.reply("This group isn't connected!")
        return
    
    msg = await event.reply("⏳ <b>Starting forced cleanup...</b>", parse_mode='html')
    try:
        success = await perform_cleanup(event.chat_id)
        if success:
            await msg.edit("✅ <b>Cleanup completed!</b>", parse_mode='html')
        else:
            await msg.edit("⚠️ <b>Cleanup partially completed with some errors</b>", parse_mode='html')
        await asyncio.sleep(30)
        await msg.delete()
    except Exception as e:
        await msg.edit(f"❌ <b>Cleanup failed:</b> <code>{str(e)}</code>", parse_mode='html')
        log.error("Force cleanup failed in %d: %s", event.chat_id, e)

# Startup routine
async def initialize():
    await client.start()
    await update_connected_groups()
    me = await client.get_me()
    log.info("Bot started as %s (ID: %d)", me.first_name, me.id)
    log.info("Connected to %d groups", len(WORK_CHAT_IDS))
    log.info("Messages will auto-delete after %s", DELETE_IN)
    log.info("Periodic cleanup every %s + 10min", DELETE_IN)
    
    # Start background tasks
    client.loop.create_task(periodic_cleanup())

# Run the bot
try:
    client.loop.run_until_complete(initialize())
    client.run_until_disconnected()
except KeyboardInterrupt:
    log.info("Bot stopped by user")
except Exception as e:
    log.error("Bot crashed: %s", e)
finally:
    log.info("Shutting down...")
