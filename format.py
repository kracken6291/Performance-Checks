import matplotlib
import seaborn as sns
from matplotlib.axes import Axes
from matplotlib.figure import Figure


def format_figure(fig: Figure):
    matplotlib.rcParams["toolbar"] = "none"
    matplotlib.rcParams["axes.ymargin"] = 0.2
    sns.set_style("dark")
    sns.set_theme("poster", font="Segoe UI", font_scale=0.6)

    fig.set_facecolor("#191818")
    # fig.set_size_inches(10, 8, forward=True)


def format_axes(ax: Axes, name: str):
    ax.set_ylim(0, 100)
    ax.set_xlabel("Time")  # X-label is always the same
    ax.set_ylabel(name)
    ax.set_alpha(0.5)

    ax.set_facecolor("#0d0d0d")

    ax.grid(False)
    ax.tick_params(axis="both", color="#cccccc", labelcolor="#cccccc")

    ax.xaxis.label.set_color("#cccccc")
    ax.yaxis.label.set_color("#cccccc")
    ax.title.set_color("#cccccc")

    for spine in ax.spines.values():
        spine.set_color("#555555")
