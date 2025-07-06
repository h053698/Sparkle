import asyncio

import discord
from datetime import timedelta
from discord.ext import commands
from discord import app_commands


class CommandGroup(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.auto_delete_channels = {}
        self.message_delete_tasks = {}

    def cog_unload(self) -> None:
        for task in self.message_delete_tasks.values():
            task.cancel()

    async def _update_channel_name(self, channel_id: int, duration_str: str = None) -> None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        original_name = channel.name

        if '| ⏱️' in original_name:
            original_name = original_name.split('┃⏱️')[0]

        new_name = original_name
        if duration_str:
            new_name = f"{original_name}┃⏱️{duration_str}"

        if new_name != channel.name:
            try:
                await channel.edit(name=new_name)
            except Exception as e:
                print(f"알 수 없는 오류 발생: 채널 '{original_name}' 이름 변경 실패: {e}")



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
                        print(f"Error deleting message: {ue}")
                    finally:
                        if message.id in self.message_delete_tasks:
                            del self.message_delete_tasks[message.id]

            task = asyncio.create_task(delete_message_after_delay())
            self.message_delete_tasks[message.id] = task

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
        target_channel_id = interaction.channel_id

        time_command = time.lower()

        if time_command == "off":
            if target_channel_id in self.auto_delete_channels:
                del self.auto_delete_channels[target_channel_id]
                await self._update_channel_name(target_channel_id, None)
                await interaction.followup.send(
                    f"Auto-delete has been **disabled** for this channel.",
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
            else:
                raise ValueError(
                    "Invalid time format. Use '5s', '5m', or '5h'. Use 'off' to disable."
                )

            if seconds <= 0:
                raise ValueError(
                    "Time must be greater than 0 (or use 'off' to disable)."
                )

            self.auto_delete_channels[target_channel_id] = seconds
            await self._update_channel_name(target_channel_id, time)
            await interaction.followup.send(
                f"Auto-delete has been set to **{time}** for this channel.",
            )

        except ValueError as ve:
            await interaction.followup.send(
                content=str(ve),
            )
        except Exception as e:
            await interaction.followup.send(
                content=f"An error occurred: {str(e)}",
                ephemeral=True,
            )




async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandGroup(bot), override=True)
    print("loaded command group")
