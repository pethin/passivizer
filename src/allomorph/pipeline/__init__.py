"""
Allomorph Pipeline Subpackage
Coordinates visualization, audio prefiltering, batch SPICE circuit simulation,
and NAM neural model training.
"""

from allomorph.pipeline.batch import (
    _run_circuit_simulation_task,
    run_spice_batch,
)
from allomorph.pipeline.cli import (
    list_instruments,
    list_voices,
    main,
)
from allomorph.pipeline.stages import (
    run_circuit_simulation,
    run_training,
    run_visualization,
)

__all__ = [
    "_run_circuit_simulation_task",
    "list_instruments",
    "list_voices",
    "main",
    "run_circuit_simulation",
    "run_spice_batch",
    "run_training",
    "run_visualization",
]
