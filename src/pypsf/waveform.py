from dataclasses import dataclass, field

import numpy as np

try:
    from matplotlib import pyplot as plt
except:
    plt = None


@dataclass
class Waveform:
    t: np.ndarray
    t_unit: str
    y: np.ndarray
    y_unit: str
    name: str = field(default="")

    def __post_init__(self) -> None:
        if isinstance(self.y, float):
            self.y = np.broadcast_to(self.y, self.t.shape)
        assert len(self.t) == len(self.y)

    def __str__(self) -> str:
        return f"Waveform: {len(self.t)} points, t = {self.t[0]} -> {self.t[-1]} {self.t_unit}"

    def plot(self):
        if plt is None:
            raise ModuleNotFoundError("Matplotlib is not installed")
        plt.plot(self.t, self.y, label=self.name)
