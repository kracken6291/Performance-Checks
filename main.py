import asyncio
import re
import sys
import threading
import tkinter as tk
import tkinter.ttk as ttk
from collections.abc import Callable
from dataclasses import dataclass
from itertools import chain
from typing import Protocol, runtime_checkable

import matplotlib.pyplot as plt
import psutil
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from format import (  # Assuming this formats the figure globally
    format_bar_axes,
    format_figure,
)
from graphs import animation_loop, create_line_graph


def bytes_to_gigabytes(value: int | float) -> float:
    """Convert bytes to gigabytes."""
    return value / (1024**3) if isinstance(value, int | float) else value


@dataclass
class InfoScreenData:
    log_file: str
    data_factory: Callable[[], dict[str, float]]
    graph_name: str
    unit: str | None = None  # Optional unit for the graph, e.g., "MB", "GHz"


@runtime_checkable
class Screen(Protocol):
    def __init__(self, master: tk.Tk, controller: "MainApplication"):
        pass

    def pack(*args, **kwargs):
        pass

    def pack_forget(self):
        pass


class InfoScreen(tk.Frame, Screen):
    screen_info: InfoScreenData = InfoScreenData(
        log_file="test.log",
        data_factory=lambda: {},
        graph_name="Error",
    )

    def __init__(self, master: tk.Tk, controller: "MainApplication"):
        super().__init__(master)
        self.controller = controller
        self.grid(row=0, column=0, sticky="nsew")
        self.initialized = False

        self.columnconfigure(
            list(range(10)), weight=1
        )  # Create 10 columns with equal weight

        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Specific Info", font=("Consolas", 40)).grid(
            row=0, column=0, columnspan=10, sticky="n", pady=10
        )
        ttk.Button(self, text="Return", command=self.return_to_main, width=15).grid(
            row=2, column=0, columnspan=10, sticky="s", pady=10
        )

        self.text_widget = tk.Listbox(self, font=("Consolas", 12))
        self.text_widget.grid(row=1, column=0, columnspan=4, sticky="nsew", padx=10)

    def configure(self):
        fig, ax = plt.subplots()
        format_figure(fig)
        format_bar_axes(ax)

        ax.set_title(InfoScreen.screen_info.graph_name)
        if InfoScreen.screen_info.unit:
            ax.set_ylabel(InfoScreen.screen_info.unit)

        for key, data in InfoScreen.screen_info.data_factory().items():
            if key != "percent": # Already handled by line graphs
                bar = ax.bar(key, data)
                if data != 0:
                    ax.bar_label(bar, fmt=f"{data:.3g} {InfoScreen.screen_info.unit or ''}", label_type="center", padding=2)

        FigureCanvasTkAgg(fig, self).get_tk_widget().grid(
            row=1, column=5, columnspan=5, sticky="nsew"
        )

        if not InfoScreen.screen_info.log_file:
            self.text_widget.insert(tk.END, "No log file specified.")
            return

        with open(InfoScreen.screen_info.log_file) as f:
            data = f.readlines()
            if data:
                data.reverse()
                for line in data:
                    self.text_widget.insert(tk.END, line.strip())

        self.initialized = True

    def return_to_main(self):
        self.initialized = False
        self.controller.show_screen("GraphScreen")
        self.pack_forget()


class GraphScreen(tk.Frame, Screen):
    def __init__(self, master: tk.Tk, controller: "MainApplication"):
        super().__init__(master)

        self.controller = controller
        self.initialized = False
        self.selected = True

        self.fig, self.axs = plt.subplots(2, 2)
        format_figure(self.fig)

        self.canvas = FigureCanvasTkAgg(self.fig, self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.draw()

        self._create_widgets()

    def _create_widgets(self):
        def get_unique_proccess_memory_info(num_processes: int = 5) -> dict[str, float]:
            """
            Returns a dictionary mapping unique process names to their total VMS memory usage in gigabytes.
            Only the top `num_processes` memory-consuming process names are included.
            """

            def format_name(name: str) -> str:
                # Split on common separators and return the first part
                split_name = re.split(r"[.\-_]", name)[0].strip()
                return split_name[:7]

            memory_by_name: dict[str, float] = {}

            for p in psutil.process_iter():
                try:
                    name = format_name(p.name())
                    mem = p.memory_info().vms
                    memory_by_name[name] = memory_by_name.get(name, 0) + mem
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by memory usage and convert to gigabytes
            sorted_items = sorted(
                memory_by_name.items(), key=lambda item: item[1], reverse=True
            )
            return {
                name: bytes_to_gigabytes(mem)
                for name, mem in sorted_items[:num_processes]
            }

        self.controller.stop_event.clear()

        self.cpu_usage = create_line_graph(
            self.axs[0][0], lambda: psutil.cpu_percent(0.1), "b-", (0, 100), "CPU Usage"
        )
        self.v_mem_usage = create_line_graph(
            self.axs[0][1],
            lambda: psutil.virtual_memory().percent,
            "r-",
            (0, 100),
            "Virtual Mem Usage",
        )
        self.s_mem_usage = create_line_graph(
            self.axs[1][0],
            lambda: psutil.swap_memory().percent,
            "g-",
            (0, 100),
            "Swap Mem Usage",
        )
        self.battery_usage = create_line_graph(
            self.axs[1][1],
            lambda: psutil.sensors_battery().percent if psutil.sensors_battery() else 0,
            "y-",
            (0, 100),
            "Battery",
        )

        self.INFO_SCREEN_LOOKUP = {
            self.cpu_usage: InfoScreenData(
                log_file="test.log",
                data_factory=lambda: psutil.cpu_stats()._asdict(),
                graph_name="Extra CPU Info",
            ),
            self.v_mem_usage: InfoScreenData(
                log_file="test.log",
                data_factory=lambda: {
                    k: bytes_to_gigabytes(v)
                    for k, v in psutil.virtual_memory()._asdict().items()
                },
                graph_name="Extra Virtual Memory Info",
                unit="GB",
            ),
            self.s_mem_usage: InfoScreenData(
                log_file="test.log",
                data_factory=lambda: {
                    k: bytes_to_gigabytes(v)
                    for k, v in psutil.swap_memory()._asdict().items()
                },
                graph_name="Extra Swap Memory Info",
                unit="GB",
            ),
            self.battery_usage: InfoScreenData(
                log_file="test.log",
                data_factory=lambda: get_unique_proccess_memory_info(),
                graph_name="Top 5 Process Memory Usage",
                unit="GB",
            ),
        }

        self._handle_inputs()

    def configure(self):
        threading.Thread(
            target=lambda: asyncio.run(
                animation_loop(20, self.canvas, self.controller.stop_event)
            ),
            daemon=True,
        ).start()

        self.initialized = True

    def _handle_inputs(self):
        def on_press(event):
            for ax in chain.from_iterable(self.axs):
                if event.inaxes == ax and self.selected:
                    InfoScreen.screen_info = self.INFO_SCREEN_LOOKUP.get(
                        ax, InfoScreenData("", lambda: {}, "Error")
                    )

                    self.controller.stop_event.set()
                    self.controller.show_screen("TestScreen")
                    self.initialized = False

        self.fig.canvas.mpl_connect("button_press_event", on_press)


class MainApplication:
    def __init__(self):
        self.root = tk.Tk()
        self.root.geometry("800x600")
        self.root.title("System Stats")
        self.root.protocol("WM_DELETE_WINDOW", self.stop_app)
        self.root.tk.call("source", "azure.tcl")
        self.root.tk.call("set_theme", "dark")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.stop_event = asyncio.Event()
        self.screen_instances: dict[str, Screen] = {}
        self.screen_classes: dict[str, type[Screen]] = {}
        self.current_screen: Screen | None = None

    def register_screen(self, name: str, screen_cls: type[Screen]):
        self.screen_classes[name] = screen_cls

    def show_screen(self, name: str):
        if self.current_screen:
            self.current_screen.pack_forget()

        if name not in self.screen_instances:
            screen = self.screen_classes[name](self.root, self)
            self.screen_instances[name] = screen
        else:
            screen = self.screen_instances[name]

        self.current_screen = screen
        self.current_screen.pack(fill=tk.BOTH, expand=True)

        if hasattr(screen, "configure") and not getattr(screen, "initialized", False):
            if isinstance(screen, GraphScreen):
                self.stop_event.clear()
            screen.configure()  # type: ignore

    def stop_app(self):
        self.stop_event.set()
        self.root.destroy()
        sys.exit()

    def run(self):
        self.show_screen("GraphScreen")
        self.root.mainloop()


if __name__ == "__main__":
    app = MainApplication()
    app.register_screen("GraphScreen", GraphScreen)
    app.register_screen("TestScreen", InfoScreen)
    app.run()
