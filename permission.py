from discord.ext import commands
from discord import Interaction


def guild_install_only_command():
    async def predicate(interaction_or_ctx):
        if isinstance(interaction_or_ctx, Interaction):
            if interaction_or_ctx.guild is None:
                await interaction_or_ctx.response.send_message(
                    "This command can only be used in a guild. (Not supported in DMs or uninstalled guilds)",
                    ephemeral=True,
                )
                return False
            if interaction_or_ctx.data and "guild_id" not in interaction_or_ctx.data:
                await interaction_or_ctx.response.send_message(
                    "This command can only be used in a guild. (Not supported in DMs or uninstalled guilds)",
                    ephemeral=True,
                )
                return False
            return True

        await interaction_or_ctx.response.send_message(
            f"Unable to use this command in a guild. (Unexpected Error)"
        )
        return False

    return commands.check(predicate)
