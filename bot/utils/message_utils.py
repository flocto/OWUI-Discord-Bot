from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord
from discord import Message

if TYPE_CHECKING:
    from ..client import discordClient as DiscordClient


async def send_split_message(
    self: DiscordClient,
    response: str,
    message: discord.Message | discord.Interaction,
    has_followed_up: bool = False,
) -> bool:
    char_limit = 1900
    if len(response) > char_limit:
        is_code_block = False
        parts = response.split("```")

        for i in range(len(parts)):
            if is_code_block:
                code_block_chunks = [parts[i][j:j+char_limit] for j in range(0, len(parts[i]), char_limit)]
                for chunk in code_block_chunks:
                    if self.is_replying_all == "True":
                        if not has_followed_up:
                            await message.reply(f"```{chunk}```", mention_author=False)
                            has_followed_up = True
                        else:
                            await message.channel.send(f"```{chunk}```")
                    elif has_followed_up:
                        await message.followup.send(f"```{chunk}```")
                    else:
                        await message.followup.send(f"```{chunk}```")
                        has_followed_up = True
                is_code_block = False
            else:
                non_code_chunks = [parts[i][j:j+char_limit] for j in range(0, len(parts[i]), char_limit)]
                for chunk in non_code_chunks:
                    if self.is_replying_all == "True":
                        if not has_followed_up:
                            await message.reply(chunk, mention_author=False)
                            has_followed_up = True
                        else:
                            await message.channel.send(chunk)
                    elif has_followed_up:
                        await message.followup.send(chunk)
                    else:
                        await message.followup.send(chunk)
                        has_followed_up = True
                is_code_block = True
    else:
        if self.is_replying_all == "True":
            if not has_followed_up:
                await message.reply(response, mention_author=False)
                has_followed_up = True
            else:
                await message.channel.send(response)
        elif has_followed_up:
            await message.followup.send(response)
        else:
            await message.followup.send(response)
            has_followed_up = True

    return has_followed_up


async def send_response_with_images(
    self: DiscordClient,
    response: dict[str, str | list[str]],
    message: Message,
) -> None:
    response_content = response.get("content")
    response_images = response.get("images")

    split_message_text = re.split(r'\[Image of.*?\]', response_content)

    for i in range(len(split_message_text)):
        if split_message_text[i].strip():
            await send_split_message(self, split_message_text[i].strip(), message, has_followed_up=True)

        if response_images and i < len(response_images):
            await send_split_message(self, response_images[i].strip(), message, has_followed_up=True)
