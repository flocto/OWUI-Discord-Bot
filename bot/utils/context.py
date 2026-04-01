import discord
from discord import Message

from ..log import logger


def _sanitize(s: str) -> str:
    """Strip characters that could break the [name (display: "nick")]: delimiter format.

    Removes brackets (our delimiters), double quotes (our display-name quoting),
    and newlines (which could make a display name look like a new author line).
    """
    return s.replace("[", "").replace("]", "").replace('"', "").replace("\n", " ").strip()


def format_author(author: discord.abc.User) -> str:
    name = _sanitize(author.name)
    if author.display_name != author.name:
        nick = _sanitize(author.display_name)
        return f'[{name} (display: "{nick}")]'
    return f"[{name}]"


def resolve_mentions(message: Message) -> str:
    content = message.content
    for user in message.mentions:
        display = f"@USER[{user.name}]"
        content = content.replace(f"<@{user.id}>", display)
        content = content.replace(f"<@!{user.id}>", display)
    for channel in message.channel_mentions:
        content = content.replace(f"<#{channel.id}>", f"#{channel.name}")
    for role in message.role_mentions:
        content = content.replace(f"<@&{role.id}>", f"@ROLE[{role.name}]")
    return content


async def build_reply_context(message: Message) -> str:
    """Return a formatted reply-context prefix line if message is a reply, else empty string."""
    if not message.reference:
        return ""

    ref = message.reference
    replied_msg = ref.resolved

    if replied_msg is None or not isinstance(replied_msg, discord.Message):
        try:
            replied_msg = await message.channel.fetch_message(ref.message_id)
        except (discord.NotFound, discord.HTTPException):
            guild_id = message.guild.id if message.guild else "@me"
            link = f"https://discord.com/channels/{guild_id}/{message.channel.id}/{ref.message_id}"
            logger.warning(f"Could not fetch replied-to message {ref.message_id}")
            return f"[Replying to a deleted/inaccessible message: {link}]\n"

    preview = replied_msg.content[:100].replace("\n", " ")
    if len(replied_msg.content) > 100:
        preview += "..."

    guild_id = message.guild.id if message.guild else "@me"
    link = f"https://discord.com/channels/{guild_id}/{message.channel.id}/{replied_msg.id}"
    author_label = format_author(replied_msg.author)
    return f'[Replying to {author_label}: "{preview}" | {link}]\n'
