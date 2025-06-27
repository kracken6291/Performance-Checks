import asyncio
import logging
import threading
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Any

from desktop_notifier import Button, DesktopNotifier, Notification, Urgency


@dataclass
class DumpInfo:
    message: str
    supplier: Callable[[], Any]
    log_path: str = ""
    unit: str | tuple[str, ...] | None = None


class Notifier:
    URGENCY_TO_LOG_LEVEL = {
        Urgency.Critical: logging.CRITICAL,
        Urgency.Normal: logging.INFO,
        Urgency.Low: logging.INFO,
    }

    def __init__(self):
        self.notifier = DesktopNotifier()

        self._tasks: list[asyncio.Task] = []

        self._loop = asyncio.new_event_loop()

        self._thread = threading.Thread(target=self._start_loop)
        self._thread.start()

        self._log_lookup = {}
        self._data_dict = {}

        for name in ["cpu.log", "misc.log", "ram.log", "swap_mem.log"]:
            self._log_lookup[name] = self._create_logger(name)

    def _create_logger(self, file_name: str) -> Logger:
        logger = Logger(__name__ + "." + file_name.removesuffix(".log"))
        logger.setLevel(logging.DEBUG)

        if logger.hasHandlers():
            raise ValueError("Logger already has handlers")

        script_dir = Path(__file__).resolve().parent
        logs_dir = script_dir / "logs"
        log_file = logs_dir / file_name

        logs_dir.mkdir(exist_ok=True)
        log_file.touch(exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        return logger

    def _start_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _log(self, file_name: str, data: str | Notification):
        if "/" in file_name:
            file_name = file_name.partition("/")[-1]

        logger = self._log_lookup.get(file_name)

        if not logger:
            logger = self._create_logger(file_name)
            self._log_lookup[file_name] = logger

        if isinstance(data, Notification):
            logger.log(
                Notifier.URGENCY_TO_LOG_LEVEL.get(data.urgency, logging.CRITICAL),
                "%s : %s",
                data.title,
                data.message,
            )
        elif isinstance(data, str):
            logger.info(data)

    def _create_periodic_message(self, data: list[DumpInfo]) -> str:
        message = ""
        self._data_dict.clear()

        for info in data:
            supplied = info.supplier()
            sub_message = ""

            unit = info.unit

            if isinstance(supplied, str):
                if isinstance(unit, tuple):
                    unit = unit[0]
                sub_message = f"{info.message}: {supplied}{unit if unit else ''}"
            elif isinstance(supplied, Collection) and not isinstance(
                supplied, str | bytes
            ):
                sub_message = f"{info.message}: " + " - ".join(
                    f"{data}{unit[i] if unit and i < len(unit) else ''}"
                    for i, data in enumerate(supplied)
                )
            else:
                sub_message = f"{info.message}: {supplied}{unit if unit else ''}"

            if info.log_path:
                self._data_dict[sub_message] = info.log_path

            message += sub_message + "\n"

        return message

    def create_conditional_notification(
        self,
        notification_supplier: Callable[[], Notification],
        condition: Callable[[], bool],
        temporary: bool = False,
        log_info: str | dict[str, str] | None = None,
        check_interval: float = 1.0,
        delay_interval: float = 20,
    ):
        async def send_conditional_notification():
            while True:
                if condition():
                    notification = notification_supplier()

                    if isinstance(log_info, dict):
                        for message, file_path in log_info.items():
                            self._log(file_path, message)
                    elif log_info:
                        self._log(log_info, notification)
                    await self.notifier.send_notification(notification)
                    if temporary:
                        break
                    await asyncio.sleep(delay_interval - check_interval)
                await asyncio.sleep(check_interval)

        def schedule():
            task = self._loop.create_task(send_conditional_notification())
            self._tasks.append(task)

        self._loop.call_soon_threadsafe(schedule)

    def periodically_send_data(
        self,
        data: list[DumpInfo],
        delay: float,
        buttons: tuple[Button, ...] = (),
    ):
        start = time.monotonic()

        self.create_conditional_notification(
            lambda: Notification(
                title="Performance Info",
                message=self._create_periodic_message(data),
                buttons=buttons,
            ),
            condition=lambda: time.monotonic() - start > delay,
            delay_interval=delay,
            log_info=self._data_dict,
            temporary=False,
        )

    def stop(self):
        for task in self._tasks:
            task.cancel()

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()
