import signal
import sys

import psutil
from desktop_notifier import Button, Notification, Urgency

from app import GraphScreen, InfoScreen, MainApplication, bytes_to_gigabytes
from notifier import DumpInfo, Notifier


def create_conditional_notifications(notifier: Notifier) -> None:
    notifier.create_conditional_notification(
        lambda: Notification(
            title="CPU usage above 80%",
            message="Could be from opening new application or a more serious issue",
            urgency=Urgency.Critical,
        ),
        lambda: psutil.cpu_percent(0.1) > 80,
        log_info="cpu.log",
        delay_interval=300,
    )

    notifier.create_conditional_notification(
        lambda: Notification(
            title="RAM usage above 80%",
            message=f"Current Usage {psutil.virtual_memory().percent}",
            urgency=Urgency.Critical,
        ),
        lambda: psutil.virtual_memory().percent > 80,
        log_info="ram.log",
        delay_interval=300,
    )


def create_periodic_notifications(notifier: Notifier, app: MainApplication) -> None:
    def gb(i: float | int):
        return round(bytes_to_gigabytes(i), 1)

    def on_run_pressed():
        app.show()
        app.root.after(0, lambda: app.show_screen("GraphScreen"))

    info = [
        DumpInfo("CPU Usage", lambda: psutil.cpu_percent(0.1), "cpu.log", "%"),
        DumpInfo("RAM Usage", lambda: psutil.virtual_memory().percent, "ram.log", "%"),
        DumpInfo(
            "Swap Mem Usage", lambda: psutil.swap_memory().percent, "swap_mem.log", "%"
        ),
        DumpInfo("Battery", lambda: psutil.sensors_battery().percent, "misc.log", "%"),
    ]

    info2 = [
        DumpInfo(
            "Disk Usage", lambda: psutil.disk_usage("C:").percent, "misc.log", "%"
        ),
        DumpInfo(
            "Extra RAM Info",
            lambda: (
                gb(psutil.virtual_memory().available),
                gb(psutil.virtual_memory().used),
            ),
            "ram.log",
            ("GB", "GB"),
        ),
        DumpInfo(
            "Extra Swap Mem Info",
            lambda: (gb(psutil.swap_memory().free), gb(psutil.swap_memory().used)),
            "swap_mem.log",
            ("GB", "GB"),
        ),
        DumpInfo(
            "Extra Battery Info",
            lambda: (
                round(psutil.sensors_battery().secsleft / 3600, 1)
                if not psutil.sensors_battery().power_plugged
                else "N/A",
                psutil.sensors_battery().power_plugged,
            ),
            "misc.log",
            (" Hours",),
        ),
    ]

    notifier.periodically_send_data(
        info, 3600, (Button("Run", on_pressed=on_run_pressed),)
    )
    notifier.periodically_send_data(
        info2, 3630, (Button("Run", on_pressed=on_run_pressed),)
    )


def handle_exit(*args):
    notifier.stop()
    app.stop()
    sys.exit(0)


if __name__ == "__main__":
    notifier = Notifier()
    app = MainApplication()

    app.register_screen("InfoScreen", InfoScreen)
    app.register_screen("GraphScreen", GraphScreen)

    create_conditional_notifications(notifier)
    create_periodic_notifications(notifier, app)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        app.run()
    except (KeyboardInterrupt, SystemExit, Exception):
        handle_exit()
