import asyncio
import logging

import discord
from datetime import timedelta, datetime
from discord.ext import commands
from discord import app_commands, TextChannel

logger = logging.getLogger("command")


class CommandGroup(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.auto_delete_channels: dict[int, float] = {}
        self.message_delete_tasks: dict[int, asyncio.Task] = {}

    def cog_unload(self) -> None:
        for task in self.message_delete_tasks.values():
            task.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        target_channel_id = message.channel.id
        if target_channel_id in self.auto_delete_channels:
            seconds = self.auto_delete_channels[target_channel_id]

            async def delete_message_after_delay() -> None:
                await discord.utils.sleep_until(
                    message.created_at + timedelta(seconds=seconds)
                )
                if message.channel.id in self.auto_delete_channels:
                    try:
                        await message.delete()
                    except discord.NotFound:
                        pass
                    except discord.Forbidden:
                        pass
                    except Exception as ue:
                        logger.error(f"Error deleting message: {ue}")
                    finally:
                        if message.id in self.message_delete_tasks:
                            del self.message_delete_tasks[message.id]

            task = asyncio.create_task(delete_message_after_delay())
            self.message_delete_tasks[message.id] = task

    @app_commands.command(
        name="ghostmode",
        description="Hide guild members nicknames from the server. (anti-capture)",
    )
    async def nickname_ghost_mode(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer()
        target_guild = interaction.guild

        if not target_guild:
            await interaction.followup.send(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        try:
            for member in target_guild.members:
                if member.nick:
                    await member.edit(nick=None)
            await interaction.followup.send(
                "## All nicknames have been cleared from the server.",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "I do not have permission to change nicknames in this server.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Error clearing nicknames: {e}")
            await interaction.followup.send(
                f"An error occurred: {str(e)}",
                ephemeral=True,
            )

    @app_commands.command(
        name="auto-delete",
        description="Automatically delete messages after a specified time.",
    )
    async def auto_delete_message(
        self,
        interaction: discord.Interaction,
        time: str = "5m",
    ) -> None:
        await interaction.response.defer()
        target_channel: TextChannel = interaction.channel

        time_command = time.lower()

        if time_command == "off":
            if target_channel.id in self.auto_delete_channels:
                del self.auto_delete_channels[target_channel.id]
                await interaction.followup.send(
                    f"## Auto-delete has been **disabled** for this channel.",
                )
            else:
                await interaction.followup.send(
                    f"Auto-delete is not currently enabled for this channel.",
                )
            return

        try:
            if time_command.endswith("s"):
                seconds = int(time[:-1])
            elif time_command.endswith("m"):
                seconds = int(time[:-1]) * 60
            elif time_command.endswith("h"):
                seconds = int(time[:-1]) * 3600
            elif time_command.endswith("d"):
                seconds = int(time[:-1]) * 86400
            else:
                raise ValueError(
                    "Invalid time format. Use '5s', '5m', or '5h'. Use 'off' to disable."
                )

            if seconds <= 0:
                raise ValueError(
                    "Time must be greater than 0 (or use 'off' to disable)."
                )

            if seconds > 172800:  # 2 days in seconds
                raise ValueError("Maximum time limit is 2 days (172800 seconds).")

            self.auto_delete_channels[target_channel.id] = seconds
            await interaction.followup.send(
                f"## Auto-delete has been set to **{time}** for this channel.",
            )

        except ValueError as ve:
            logger.error(f"ValueError in auto-delete command: {ve}")
            await interaction.followup.send(
                content=str(ve),
            )
        except Exception as e:
            logger.error(f"Error in auto-delete command: {e}")
            await interaction.followup.send(
                content=f"An error occurred: {str(e)}",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandGroup(bot))
    logger.info("CommandGroup cog loaded successfully.")
