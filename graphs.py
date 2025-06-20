import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.lines import Line2D

from format import format_line_axes

line_data_container = []


@dataclass
class LineData:
    line: Line2D
    plot: Axes
    func: Callable[[], float] | Callable[[], Awaitable[float]]
    dynamic_y_axis: bool
    first_iteration_timestamp: float | None
    x_data: deque[float] = field(default_factory=deque)
    y_data: deque[float] = field(default_factory=deque)


async def get_data(func: Callable) -> float:
    data = func()
    if asyncio.iscoroutine(func):
        await data
    return data


def create_line_graph(
    plot: Axes,
    func: Callable[[], float],
    style: str,
    y_lim: tuple[float, float] | None = None,
    name: str | None = None,
    format_axis: bool = True,
):
    (line,) = plot.plot([], [], style)
    line.set_alpha(0.75)

    if format_axis:
        format_line_axes(
            plot,
            name or func.__name__.removeprefix("get_").replace("_", " ").capitalize(),
        )

    if y_lim is not None:
        plot.set_ylim(y_lim[0], y_lim[1])

    line_data_container.append(LineData(line, plot, func, bool(not y_lim), None))
    return plot


async def update_line_data(line_data: LineData, max_capacity: int = 30):
    if line_data.first_iteration_timestamp is None:
        line_data.first_iteration_timestamp = time.monotonic()

    y_val = await get_data(line_data.func)

    line_data.x_data.append(time.monotonic() - line_data.first_iteration_timestamp)
    line_data.y_data.append(y_val)

    if len(line_data.x_data) > 15:
        line_data.x_data.popleft()
        line_data.y_data.popleft()

    if line_data.dynamic_y_axis:
        line_data.plot.set_ylim(min(line_data.y_data), max(line_data.y_data))

    if len(line_data.x_data) > 1:
        line_data.plot.set_xlim(line_data.x_data[0], line_data.x_data[-1])

    line_data.line.set_data(line_data.x_data, line_data.y_data)
    return line_data.line


async def animation_loop(
    interval_ms, canvas: FigureCanvasTkAgg, stop_event: asyncio.Event
):
    while not stop_event.is_set():
        for line_data in line_data_container:
            asyncio.create_task(update_line_data(line_data))

        # Wait for all tasks to complete before redrawing the canvas
        await asyncio.gather(
            *[update_line_data(line_data) for line_data in line_data_container]
        )

        canvas.draw()
        await asyncio.sleep(interval_ms / 1000)
