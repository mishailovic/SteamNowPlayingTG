import asyncio
from pyrogram import Client
from steam.webapi import WebAPI
from steamgrid import SteamGridDB
import requests
from io import BytesIO
from PIL import Image
import logging
import config

STEAM_API_KEY = config.STEAM_API_KEY
STEAMGRID_API_KEY = config.STEAMGRID_API_KEY
STEAM_ID = config.STEAM_ID
CHANNEL = config.CHANNEL
MESSAGE_ID = config.MESSAGE_ID
UPDATE_INTERVAL = config.UPDATE_INTERVAL
BOT_TOKEN = config.BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sgdb = SteamGridDB(STEAMGRID_API_KEY)
steam_api = WebAPI(key=STEAM_API_KEY)
headers = {"Authorization": f"Bearer {STEAMGRID_API_KEY}"}

bot = Client(
    "bot", api_id=1, api_hash="b6b154c3707471f5339bd661645ed3d6", bot_token=BOT_TOKEN
)

current_game_id = None
current_icon_url = None


async def update_channel_status():
    global current_game_id, current_icon_url

    while True:
        try:
            player_data = steam_api.ISteamUser.GetPlayerSummaries(steamids=STEAM_ID)
            player_info = player_data["response"]["players"][0]

            game_id = player_info.get("gameid")
            if not game_id:
                logger.info("No game is currently being played.")
                await asyncio.sleep(UPDATE_INTERVAL)
                continue

            if game_id == current_game_id:
                logger.info("Game ID has not changed. No update needed.")
                await asyncio.sleep(UPDATE_INTERVAL)
                continue

            game = sgdb.get_game_by_steam_appid(int(game_id))

            icon_response = requests.get(
                f"https://www.steamgriddb.com/api/v2/icons/game/{game.id}",
                headers=headers,
            )
            icon_data = icon_response.json()
            icon_url = icon_data["data"][0]["url"]

            if icon_url == current_icon_url:
                logger.info("Game icon has not changed. No update needed.")
                await asyncio.sleep(UPDATE_INTERVAL)
                continue

            current_game_id = game_id
            current_icon_url = icon_url

            icon_response = requests.get(icon_url)
            resized = BytesIO()
            with Image.open(BytesIO(icon_response.content)) as img:
                img = img.resize((1028, 1028), Image.LANCZOS)
                img = img.convert("RGB")
                img.save(resized, format="JPEG")

            await bot.edit_message_text(CHANNEL, MESSAGE_ID, game.name)
            await bot.set_chat_photo(CHANNEL, photo=resized)

            await delete_last_message()

            logger.info(f"Updated channel status: {game.name}")

        except Exception as e:
            logger.error(f"Error updating channel status: {e}")

        await asyncio.sleep(UPDATE_INTERVAL)


async def delete_last_message():
    message = await bot.send_message(CHANNEL, "Changing my avatar...")
    try:
        await bot.delete_messages(CHANNEL, message.id)
        await bot.delete_messages(CHANNEL, message.id - 1)
        logger.info(f"Successfully deleted message with ID: {message.id - 1}")
    except Exception as e:
        logger.error(f"Error deleting message with ID {message.id - 1}: {e}")


async def main():
    try:
        await bot.start()
        logger.info("Bot started")

        update_task = asyncio.create_task(update_channel_status())
        await asyncio.get_event_loop().create_future()

    except KeyboardInterrupt:
        logger.info("Stopping bot")
    finally:
        await bot.stop()
        logger.info("Bot stopped")


if __name__ == "__main__":
    bot.run(main())
