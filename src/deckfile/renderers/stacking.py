from __future__ import annotations

import numpy as np


def normalize_layers(layer_values: list[np.ndarray]) -> list[np.ndarray]:
    """Rescale stacked layers so each column sums to 100.

    Columns whose layers sum to zero are left at zero rather than dividing by
    zero.
    """
    totals = np.sum(layer_values, axis=0)
    totals = np.where(totals == 0, 1, totals)
    return [(v / totals) * 100 for v in layer_values]
