from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


# ================= SIMPLE PLOT ==================
class SimplePlot(FigureCanvas):
    def __init__(self, ylabel="", title=""):
        fig = Figure(figsize=(4, 2.5), tight_layout=True)
        super().__init__(fig)
        self.ax = fig.add_subplot(111)
        fig.patch.set_facecolor('#0c0c0c')
        self.ax.set_facecolor('#222')
        self.ax.set_title(title, color='w', fontsize=12, fontweight='bold')
        self.ax.set_ylabel(ylabel, color='w', fontsize=11)
        self.ax.tick_params(colors='w', labelsize=9)
        for spine in self.ax.spines.values():
            spine.set_color('#888')
        self.ax.grid(True, color='#555', linestyle='--', linewidth=0.6)

    def plot_series(self, times, values, title, color=None, y_fixed_range=None):
        self.ax.clear()
        self.ax.set_facecolor('#222')
        self.ax.set_title(title, color='w', fontsize=12, fontweight='bold')
        self.ax.set_ylabel(self.ax.get_ylabel(), color='w', fontsize=11)

        if len(times) > 0 and len(values) > 0:
            x = list(range(len(values)))
            if color:
                self.ax.plot(x, values, marker='o', markersize=4, linewidth=2.0, linestyle='-', color=color)
            else:
                self.ax.plot(x, values, marker='o', markersize=4, linewidth=2.0, linestyle='-')

            step = max(1, len(times) // 8)
            ticks = list(range(0, len(times), step))
            labels = [times[i].strftime("%H:%M") for i in ticks]
            self.ax.set_xticks(ticks)
            self.ax.set_xticklabels(labels, rotation=30, color='w', fontsize=9)

            if y_fixed_range:
                self.ax.set_ylim(y_fixed_range)
                y_min, y_max = y_fixed_range
                if "Temp" in title:
                    self.ax.set_yticks(list(range(y_min, y_max + 1, 5)))
                elif "Humid" in title:
                    self.ax.set_yticks(list(range(y_min, y_max + 1, 10)))
            else:
                y_max = max(values) * 1.2 if max(values) > 0 else 1
                self.ax.set_ylim(0, y_max)

        self.ax.tick_params(colors='w', labelsize=9)
        for spine in self.ax.spines.values():
            spine.set_color('#888')
        self.ax.grid(True, color='#555', linestyle='--', linewidth=0.6)
        self.draw()
