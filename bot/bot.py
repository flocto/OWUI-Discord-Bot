import os
from .client import discordClient


def run_discord_bot() -> None:
    from .commands import setup_commands
    from .events import setup_events
    setup_commands(discordClient)
    setup_events(discordClient)
    discordClient.run(os.getenv("DISCORD_BOT_TOKEN"))
