import asyncio
import sys
import threading
import tkinter as tk
import tkinter.ttk as ttk
from itertools import chain
from typing import Protocol, runtime_checkable

import matplotlib.pyplot as plt
import psutil
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from format import format_figure  # Assuming this formats the figure globally
from graphs import animation_loop, create_line_graph


@runtime_checkable
class Screen(Protocol):
    def __init__(self, master: tk.Tk, controller: "MainApplication"):
        pass

    def pack(*args, **kwargs):
        pass

    def pack_forget(self):
        pass


class InfoScreen(tk.Frame, Screen):
    def __init__(self, master: tk.Tk, controller: "MainApplication"):
        super().__init__(master)
        self.controller = controller
        self.pack(fill=tk.BOTH, expand=True)

        tk.Label(self, text="Specific Info", font=("Consolas", 40)).pack(padx=20, pady=20)
        tk.Button(self, text="Return", command=self.return_to_main, width=15, height=2, borderwidth=2).pack(side=tk.BOTTOM, pady=20)
        
        # Create a frame to hold the Text and Scrollbar
        text_frame = tk.Frame(self, width=100, height=300)
        text_frame.pack(fill=tk.BOTH, expand=True)

        size = self.controller.root.winfo_fpixels("0.5c")
        text_widget = tk.Text(text_frame, borderwidth=2, width=40, height=80, wrap="word", font=("Consolas", int(size)))
        text_widget.pack(side=tk.LEFT, expand=False)

    def return_to_main(self):
        self.controller.show_screen("GraphScreen")


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
        self.controller.stop_event.clear()

        create_line_graph(
            self.axs[0][0], lambda: psutil.cpu_percent(0.1), "b-", (0, 100), "CPU Usage"
        )
        create_line_graph(
            self.axs[0][1],
            lambda: psutil.virtual_memory().percent,
            "r-",
            (0, 100),
            "Virtual Mem Usage",
        )
        create_line_graph(
            self.axs[1][0],
            lambda: psutil.swap_memory().percent,
            "g-",
            (0, 100),
            "Swap Mem Usage",
        )
        create_line_graph(
            self.axs[1][1],
            lambda: psutil.sensors_battery().percent if psutil.sensors_battery() else 0,
            "y-",
            (0, 100),
            "Battery",
        )
        self._handle_inputs()

    def start_animation(self):
        threading.Thread(
            target=lambda: asyncio.run(
                animation_loop(30, self.canvas, self.controller.stop_event)
            ),
            daemon=True,
        ).start()

        self.initialized = True

    def _handle_inputs(self):
        def on_press(event):
            for ax in chain.from_iterable(self.axs):
                if event.inaxes == ax and self.selected:
                    self.controller.stop_event.set()
                    self.controller.show_screen("TestScreen")
                    self.initialized = False

        self.fig.canvas.mpl_connect("button_press_event", on_press)


class MainApplication:
    def __init__(self):
        self.root = tk.Tk()
        self.root.geometry("1920x1200")
        self.root.title("System Stats")
        self.root.protocol("WM_DELETE_WINDOW", self.stop_app)
        self.root.tk.call("source", "azure.tcl")
        self.root.tk.call("set_theme", "dark")

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

        if (
            isinstance(self.current_screen, GraphScreen)
            and not self.current_screen.initialized
        ):
            self.stop_event.clear()
            self.current_screen.start_animation()

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
