"""
Discord source collector for Community Pulse.

Collects messages from designated Pure community Discord channels.
Uses discord.py when bot token is configured. Falls back gracefully.
"""

import os

# Placeholder: real implementation requires discord.py and a bot token
# import discord

CHANNEL_IDS = os.getenv("DISCORD_CHANNEL_IDS", "").split(",") if os.getenv("DISCORD_CHANNEL_IDS") else []


def collect() -> list[dict]:
    """Collect signals from Discord. Returns a list of raw signal dicts."""
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token or not CHANNEL_IDS:
        print("[discord] No bot token or channel IDs configured. Skipping.")
        return []

    # --- Real implementation (uncomment when ready) ---
    # signals = []
    #
    # class PulseClient(discord.Client):
    #     async def on_ready(self):
    #         for channel_id in CHANNEL_IDS:
    #             channel = await self.fetch_channel(int(channel_id.strip()))
    #             async for message in channel.history(limit=200):
    #                 if not message.author.bot:
    #                     signals.append({
    #                         "id": f"discord_{message.id}",
    #                         "source": "discord",
    #                         "source_url": f"https://discord.com/channels/{message.guild.id}/{channel_id}/{message.id}",
    #                         "date": message.created_at.isoformat(),
    #                         "topic": infer_topic(message.content),
    #                         "content_preview": message.content[:500],
    #                         "author": str(message.author),
    #                         "engagement": {"likes": sum(r.count for r in message.reactions), "replies": 0, "shares": 0},
    #                     })
    #         await self.close()
    #
    # client = PulseClient(intents=discord.Intents.default())
    # await client.start(token)
    # return signals

    print("[discord] Collector registered. Implement with discord.py + bot token.")
    return []


def infer_topic(text: str) -> str:
    """Basic keyword-based topic inference."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["filter", "filtration", "pressure"]):
        return "water_filtration_performance"
    if any(w in text_lower for w in ["support", "help", "issue", "broken"]):
        return "customer_support"
    if any(w in text_lower for w in ["install", "setup", "fitting"]):
        return "installation_difficulty"
    if any(w in text_lower for w in ["durable", "quality", "last", "lifetime"]):
        return "product_durability"
    if any(w in text_lower for w in ["feature", "suggestion", "idea"]):
        return "feature_request"
    return "general"