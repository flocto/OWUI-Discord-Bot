import os
import re
import base64
import asyncio

from .log import logger
from .utils.message_utils import send_split_message
from .utils.upload_files import upload_attachment
from .tools.memory import add_memory, recall_memories, forget_memory
from .tools.do_nothing import do_nothing
from .types import ContentPart, ConversationMessage, ImagePart

import discord
from discord import app_commands
from openwebui_client import OpenWebUIClient

# typing
from openai.types.file_object import FileObject
from typing import Any

# env
from dotenv import load_dotenv
load_dotenv()

TOOLS = [
    # Memory tools
    "add_memory", 
    "recall_memories", 
    "forget_memory", 
    # Do nothing
    "do_nothing"
]


class discordClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=False))
        self.tree = app_commands.CommandTree(self)
        self.chatModel: str | None = os.getenv("MODEL")
        self.conversation_history: list[ConversationMessage] = []
        self.current_channel: discord.abc.Messageable | None = None
        self.activity = discord.Activity(
            type=discord.ActivityType.listening, name="hi im mevin")
        self.isPrivate: bool = False
        self.is_replying_all: str | None = os.getenv("REPLYING_ALL")
        self.replying_all_discord_channel_id: str | None = os.getenv(
            "REPLYING_ALL_DISCORD_CHANNEL_ID")
        self.openwebui_client = OpenWebUIClient(api_key=os.getenv(
            "API_KEY"), base_url=os.getenv("BASE_API_URL"))

        self.openwebui_client.tool_registry.register(
            add_memory, name="add_memory")
        self.openwebui_client.tool_registry.register(
            recall_memories, name="recall_memories")
        self.openwebui_client.tool_registry.register(
            forget_memory, name="forget_memory")
        self.openwebui_client.tool_registry.register(
            do_nothing, name="do_nothing")

        self.message_queue: asyncio.Queue[tuple[discord.Interaction, str]] = asyncio.Queue()
        self.max_history_chars: int = int(
            os.getenv("MAX_HISTORY_CHARS", "32000"))  # ~8k tokens
        self.batch_delay: float = float(os.getenv("BATCH_DELAY", "3"))
        self.pending_batch: list[tuple[discord.Message, str, list[discord.Attachment]]] = []
        self._batch_timer_task: asyncio.Task[None] | None = None
        self.file_library: dict[str, FileObject] = {}  # Maps filename to FileObject for re-attaching
        self.pending_context: list[str] = []  # Reaction/event notes to prepend to the next batch flush

    async def process_messages(self) -> None:
        while True:
            if self.current_channel is not None:
                while not self.message_queue.empty():
                    async with self.current_channel.typing():
                        message, user_message = await self.message_queue.get()
                        try:
                            await self.send_message(message, user_message)
                        except Exception as e:
                            logger.exception(
                                f"Error while processing message: {e}")
                        finally:
                            self.message_queue.task_done()
            await asyncio.sleep(1)

    async def enqueue_message(self, message: discord.Interaction, user_message: str) -> None:
        await message.response.defer(ephemeral=self.isPrivate) if self.is_replying_all == "False" else None
        await self.message_queue.put((message, user_message))

    async def enqueue_batch_message(
        self,
        message: discord.Message,
        user_message: str,
        attachments: list[discord.Attachment] | None = None,
    ) -> None:
        self.pending_batch.append(
            (message, user_message, list(attachments or [])))
        if self._batch_timer_task is not None and not self._batch_timer_task.done():
            self._batch_timer_task.cancel()
        self._batch_timer_task = asyncio.get_event_loop().create_task(
            self._batch_flush_timer(message.channel)
        )

    async def _batch_flush_timer(self, channel: discord.abc.Messageable) -> None:
        try:
            async with channel.typing():
                await asyncio.sleep(self.batch_delay)
        except asyncio.CancelledError:
            return
        await self._flush_batch()

    async def _flush_batch(self) -> None:
        if not self.pending_batch:
            return
        batch = self.pending_batch
        self.pending_batch = []
        self._batch_timer_task = None

        last_message = batch[-1][0]
        combined_user_message = "\n".join(user_msg for _, user_msg, _ in batch)
        all_attachments = [att for _, _, atts in batch for att in atts]

        if self.pending_context:
            context_block = "\n".join(self.pending_context)
            combined_user_message = context_block + "\n" + combined_user_message
            self.pending_context = []

        logger.info(
            f"Flushing batch of {len(batch)} message(s)"
            + (f" with attachments: {[att.filename for att in all_attachments]}" if all_attachments else "")
        )

        async with last_message.channel.typing():
            try:
                response = await self.handle_response(combined_user_message, all_attachments)
                if response is not None:
                    await send_split_message(self, response, last_message)
            except Exception as e:
                logger.exception(
                    f"Error while processing batched messages: {e}")

    async def send_message(self, message: discord.Interaction, user_message: str) -> None:
        try:
            response = await self.handle_response(user_message)
            if response is not None:
                await send_split_message(self, response, message)
        except Exception as e:
            logger.exception(f"Error while sending : {e}")

    def _content_len(self, content: str | list[ContentPart]) -> int:
        if isinstance(content, str):
            return len(content)
        return sum(len(p.get("text", "")) for p in content if isinstance(p, dict))

    def _trim_history(self) -> None:
        anchor = 2  # always keep first 2 messages (system prompt exchange)
        total = sum(self._content_len(m["content"])
                    for m in self.conversation_history)
        while total > self.max_history_chars and len(self.conversation_history) > anchor + 1:
            removed = self.conversation_history.pop(anchor)
            total -= self._content_len(removed["content"])

    async def _attachment_to_part(self, att: discord.Attachment) -> ImagePart | FileObject | None:
        """Returns an ImagePart (inline base64), a FileObject (uploaded file), or None (unsupported)."""
        if not att.content_type:
            logger.warning(
                f"Attachment '{att.filename}' has no content type, defaulting to application/octet-stream")
        data = await att.read()
        if att.content_type and att.content_type.startswith("image/"):
            mime = att.content_type.split(";")[0]
            logger.info(
                f"Embedding '{att.filename}' ({mime}) as inline base64 image")
            b64 = base64.b64encode(data).decode()
            return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        else:
            content_type = att.content_type or "application/octet-stream"
            return upload_attachment(self.openwebui_client, att.filename, data, content_type)

    def _resolve_file_mentions(self, user_message: str) -> list[FileObject]:
        """Parse $filename mentions and return matching FileObjects from the library."""
        files = []
        for name in re.findall(r"\$(\S+)", user_message):
            if name in self.file_library:
                files.append(self.file_library[name])
                logger.info(
                    f"Re-attaching '{name}' from file library via mention")
            else:
                logger.warning(
                    f"Mentioned file '${name}' not found in file library (known: {list(self.file_library)})")
        return files

    async def handle_response(self, user_message: str, attachments: list[discord.Attachment] | None = None) -> str | None:
        turn_files: list[FileObject] = []
        content: str | list[ContentPart]
        if attachments:
            content = [{"type": "text", "text": user_message}]
            unsupported: list[str] = []
            for att in attachments:
                try:
                    part = await self._attachment_to_part(att)
                    if part is None:
                        unsupported.append(att.filename)
                    elif isinstance(part, dict):
                        content.append(part)
                    else:
                        self.file_library[att.filename] = part
                        turn_files.append(part)
                except Exception as e:
                    logger.warning(
                        f"Failed to process attachment {att.filename}: {e}")
            if unsupported:
                content[0][
                    "text"] += f"\n\n[Note: The following attachment(s) could not be processed because their file type is not supported: {', '.join(unsupported)}]"
        else:
            content = user_message

        # Re-attach any files mentioned by $filename
        for f in self._resolve_file_mentions(user_message):
            if f not in turn_files:
                turn_files.append(f)

        self.conversation_history.append({'role': 'user', 'content': content})
        self._trim_history()

        chat_kwargs: dict[str, Any] = dict(
            messages=self.conversation_history,
            tools=TOOLS,
            max_tool_calls=10,
            model=self.chatModel,
        )
        if turn_files:
            chat_kwargs["files"] = turn_files

        response = self.openwebui_client.chat_with_tools(**chat_kwargs)

        # chat_with_tools may return a ChatCompletion or a plain string
        if isinstance(response, str):
            bot_response = response
        elif hasattr(response, "choices") and response.choices:
            bot_response = response.choices[0].message.content
        else:
            error = getattr(response, 'error', None)
            raise RuntimeError(f"API returned no usable response: {error or response}")

        if not bot_response:
            logger.info("Bot chose to stay silent (empty response)")
            self.conversation_history.append({'role': 'assistant', 'content': '[silent]'})
            return None

        self.conversation_history.append({'role': 'assistant', 'content': bot_response})
        return bot_response

    def reset_conversation_history(self) -> None:
        self.conversation_history = []


discordClient = discordClient()
