from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import discord

from .log import logger
from .utils.context import format_author, resolve_mentions, build_reply_context

if TYPE_CHECKING:
    from .client import discordClient as DiscordClient


def setup_events(client: DiscordClient) -> None:

    @client.event
    async def on_ready():
        await client.tree.sync()
        loop = asyncio.get_event_loop()
        loop.create_task(client.process_messages())
        logger.info(f'{client.user} is now running!')

    @client.event
    async def on_message(message):
        if client.is_replying_all == "True":
            if message.author == client.user:
                return
            if client.replying_all_discord_channel_id:
                if message.channel.id == int(client.replying_all_discord_channel_id):
                    username = str(message.author)
                    attachments = message.attachments
                    att_placeholders = "".join(
                        f" [Attachment {i+1}: {a.filename}]" for i, a in enumerate(attachments)
                    )
                    reply_context = await build_reply_context(message)
                    user_message = (
                        f"{reply_context}"
                        f"{format_author(message.author)}: {resolve_mentions(message)}{att_placeholders}"
                    )
                    client.current_channel = message.channel
                    logger.info(
                        f"\x1b[31m{username}\x1b[0m : '{message.content}' ({client.current_channel})")
                    await client.enqueue_batch_message(message, user_message, attachments)
            else:
                logger.exception(
                    "replying_all_discord_channel_id not found, please use the command `/replyall` again.")

    @client.event
    async def on_message_edit(before, after):
        if client.is_replying_all != "True":
            return
        if after.author == client.user:
            return
        if not client.replying_all_discord_channel_id:
            return
        if after.channel.id != int(client.replying_all_discord_channel_id):
            return
        if before.content == after.content:
            return

        username = str(after.author)
        attachments = after.attachments
        att_placeholders = "".join(
            f" [Attachment {i+1}: {a.filename}]" for i, a in enumerate(attachments)
        )
        old_preview = before.content[:100]
        if len(before.content) > 100:
            old_preview += "..."
        user_message = (
            f"[EDIT] {format_author(after.author)}: {resolve_mentions(after)}{att_placeholders}\n"
            f'[Previous content was: "{old_preview}"]'
        )
        client.current_channel = after.channel
        logger.info(f"\x1b[31m{username}\x1b[0m edited: '{after.content}' ({client.current_channel})")
        await client.enqueue_batch_message(after, user_message, attachments)

    @client.event
    async def on_reaction_add(reaction: discord.Reaction, user):
        if client.is_replying_all != "True":
            return
        if user == client.user:
            return
        if not client.replying_all_discord_channel_id:
            return
        if reaction.message.channel.id != int(client.replying_all_discord_channel_id):
            return

        emoji = str(reaction.emoji)
        author_label = format_author(user)
        msg_content = reaction.message.content or "(cached content unavailable)"
        msg_preview = msg_content[:60].replace("\n", " ")
        if len(msg_content) > 60:
            msg_preview += "..."
        client.pending_context.append(
            f'[REACTION] {author_label} reacted {emoji} to: "{msg_preview}"'
        )
        logger.info(f"{author_label} added reaction {emoji}")

    @client.event
    async def on_reaction_remove(reaction: discord.Reaction, user):
        if client.is_replying_all != "True":
            return
        if user == client.user:
            return
        if not client.replying_all_discord_channel_id:
            return
        if reaction.message.channel.id != int(client.replying_all_discord_channel_id):
            return

        emoji = str(reaction.emoji)
        author_label = format_author(user)
        msg_content = reaction.message.content or "(cached content unavailable)"
        msg_preview = msg_content[:60].replace("\n", " ")
        if len(msg_content) > 60:
            msg_preview += "..."
        client.pending_context.append(
            f'[REACTION REMOVED] {author_label} removed reaction {emoji} from: "{msg_preview}"'
        )
        logger.info(f"{author_label} removed reaction {emoji}")
