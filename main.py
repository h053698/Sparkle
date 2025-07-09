import os
import logging
from asyncio import run

from discord.ext import commands
from discord import AllowedMentions, Intents

from core.env_validator import get_settings

settings = get_settings()
logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger("sparkle")


class Sparkle(commands.Bot):
    def __init__(self) -> None:
        allowed_mentions = AllowedMentions(roles=False, everyone=False, users=True)
        intents = Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        super().__init__(
            command_prefix=os.urandom(10).hex(),
            pm_help=None,
            chunk_guilds_at_startup=False,
            heartbeat_timeout=150.0,
            allowed_mentions=allowed_mentions,
            intents=intents,
            enable_debug_events=True,
        )

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user.name} (ID: {self.user.id})")

    async def setup_hook(self) -> None:
        await self.load_extension("command")
        logger.info("Command extension loaded successfully.")
        await self.tree.sync()
        logger.info("Command tree synced successfully.")


async def main() -> None:
    bot = Sparkle()

    async with bot:
        await bot.start(token=settings.BOT_TOKEN)


if __name__ == "__main__":
    run(main())
