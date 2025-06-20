import asyncio

from desktop_notifier import DesktopNotifier

notifier = DesktopNotifier()

async def notify():
    await notifier.send(title="Hello", message="This is a test notification", timeout=5)

asyncio.run(notify())