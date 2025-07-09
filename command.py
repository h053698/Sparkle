import asyncio
import logging
import random

import discord
from datetime import timedelta
from discord.ext import commands
from discord import app_commands, TextChannel

from faker import Faker

logger = logging.getLogger("command")


class CommandGroup(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.auto_delete_channels: dict[int, float] = {}
        self.message_delete_tasks: dict[int, asyncio.Task] = {}

        self.ghost_mode_original_nicks: dict[int, dict[int, str | None]] = {}
        self.ghost_mode_restore_tasks: dict[int, asyncio.Task] = {}
        self.is_ghost_mode_active: dict[int, bool] = {}

        self.faker = Faker(["en_US"])

    def cog_unload(self) -> None:
        for task in self.message_delete_tasks.values():
            task.cancel()
        for task in self.ghost_mode_restore_tasks.values():
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

    async def _restore_nicknames(self, guild: discord.Guild) -> None:
        if guild.id not in self.ghost_mode_original_nicks:
            return

        original_nicks = self.ghost_mode_original_nicks[guild.id]
        restored_count = 0
        failed_count = 0

        for member_id, original_nick in original_nicks.items():
            member = guild.get_member(member_id)
            if member:
                try:
                    if (
                        member == self.bot.user
                        or not member.guild_permissions.manage_nicknames
                    ):
                        continue

                    if guild.me.top_role.position > member.top_role.position:
                        await member.edit(nick=original_nick)
                        restored_count += 1
                    else:
                        logger.warning(
                            f"Skipping nickname restore for {member.display_name} (ID: {member.id}) due to role hierarchy."
                        )
                        failed_count += 1

                except discord.Forbidden:
                    logger.warning(
                        f"Failed to restore nickname for {member.display_name} (ID: {member.id}) due to permissions."
                    )
                    failed_count += 1
                except Exception as e:
                    logger.error(
                        f"Error restoring nickname for {member.display_name} (ID: {member.id}): {e}"
                    )
                    failed_count += 1

        if guild.id in self.ghost_mode_original_nicks:
            del self.ghost_mode_original_nicks[guild.id]
        if guild.id in self.is_ghost_mode_active:
            self.is_ghost_mode_active[guild.id] = False
        if guild.id in self.ghost_mode_restore_tasks:
            del self.ghost_mode_restore_tasks[guild.id]

        logger.info(
            f"Nickname restoration complete for guild {guild.name}. Restored: {restored_count}, Failed: {failed_count}"
        )

    @app_commands.command(
        name="ghostmode",
        description="Hide guild members nicknames from the server. (anti-capture)",
    )
    async def nickname_ghost_mode(
        self,
        interaction: discord.Interaction,
        duration: str = None,
    ) -> None:
        await interaction.response.defer()
        target_guild = interaction.guild

        if not target_guild:
            await interaction.followup.send(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if not target_guild.me.guild_permissions.manage_nicknames:
            await interaction.followup.send(
                "I do not have permission to manage nicknames in this server. (contact an guild admin)",
                ephemeral=True,
            )
            return

        current_active_ghost_mode = self.is_ghost_mode_active.get(
            target_guild.id, False
        )

        if duration and duration.lower() == "off":
            if current_active_ghost_mode:
                await interaction.followup.send(
                    f"## Ghost mode has been **disabled** for this server.",
                )
                if target_guild.id in self.ghost_mode_restore_tasks:
                    self.ghost_mode_restore_tasks[target_guild.id].cancel()
                    del self.ghost_mode_restore_tasks[target_guild.id]
                await self._restore_nicknames(target_guild)
                await interaction.message.reply(
                    "All nicknames have been restored.",
                )
            else:
                await interaction.followup.send(
                    "Ghost mode is not currently enabled for this server.",
                    ephemeral=True,
                )
                return

        if current_active_ghost_mode:
            await interaction.followup.send(
                "Ghost mode is already active in this server.",
                ephemeral=True,
            )
            return

        self.is_ghost_mode_active[target_guild.id] = True
        self.ghost_mode_original_nicks[target_guild.id] = {}

        changed_count = 0
        skipped_count = 0

        logger.info(f"Activating ghost mode for guild: {target_guild.name} (ID: {target_guild.id})")
        if len(target_guild.members) == 1:
            await target_guild.chunk()
        try:
            print("aaaa")
            for member in target_guild.members:
                logger.info("Processing member: %s (ID: %s)", member.display_name, member.id)
                if member == self.bot.user:
                    continue

                # if (
                #     target_guild.me.top_role.position <= member.top_role.position
                #     and member != target_guild.owner
                # ):
                #     logger.warning(
                #         f"Skipping nickname change for {member.display_name} (ID: {member.id}) due to role hierarchy."
                #     )
                #     skipped_count += 1
                #     continue

                # if member.guild_permissions.administrator:
                #     logger.info(
                #         f"Skipping nickname change for administrator {member.display_name} (ID: {member.id})."
                #     )
                #     skipped_count += 1
                #     continue

                self.ghost_mode_original_nicks[target_guild.id][member.id] = member.nick

                new_nick = self.faker.name()
                if len(new_nick) > 32:
                    new_nick = self.faker.first_name() + str(
                        random.randint(10, 99)
                    )  # 너무 길면 짧게
                    if len(new_nick) > 32:
                        new_nick = new_nick[:32]

                try:
                    logger.info(f"Changing nickname for {member.display_name} (ID: {member.id}) to {new_nick}")
                    await member.edit(nick=new_nick)
                    changed_count += 1
                    await asyncio.sleep(0.5)
                except discord.Forbidden:
                    logger.warning(
                        f"Failed to change nickname for {member.display_name} (ID: {member.id}) due to permissions."
                    )
                    skipped_count += 1
                except Exception as e:
                    logger.error(
                        f"Error changing nickname for {member.display_name} (ID: {member.id}): {e}"
                    )
                    skipped_count += 1

            if duration:
                seconds_duration = 0
                if duration.endswith("s"):
                    seconds_duration = int(duration[:-1])
                elif duration.endswith("m"):
                    seconds_duration = int(duration[:-1]) * 60
                elif duration.endswith("h"):
                    seconds_duration = int(duration[:-1]) * 3600
                else:
                    await interaction.followup.send(
                        "Invalid duration format. Use '5s', '5m', or '5h'",
                        ephemeral=True,
                    )
                    return

                if target_guild.id in self.ghost_mode_restore_tasks:
                    self.ghost_mode_restore_tasks[target_guild.id].cancel()

                async def restore_after_time():
                    await asyncio.sleep(seconds_duration)
                    if self.is_ghost_mode_active.get(target_guild.id):
                        logger.info(
                            f"Ghost mode duration ended for guild {target_guild.name}. Restoring nicknames..."
                        )
                        await self._restore_nicknames(target_guild)

                self.ghost_mode_restore_tasks[target_guild.id] = asyncio.create_task(
                    restore_after_time()
                )

            await interaction.followup.send(
                f"## Ghost mode has been **activated** for this server.\n"
            )

        except Exception as e:
            logger.error(f"Error in ghostmode command: {e}")
            await interaction.followup.send(
                content=f"An error occurred while activating ghost mode: {str(e)}",
                ephemeral=True,
            )
            # 오류 발생 시 고스트 모드 상태 초기화
            if target_guild.id in self.ghost_mode_original_nicks:
                del self.ghost_mode_original_nicks[target_guild.id]
            if target_guild.id in self.is_ghost_mode_active:
                self.is_ghost_mode_active[target_guild.id] = False

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
