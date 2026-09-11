"""
Allomorph Pipeline Subpackage
Coordinates visualization, audio prefiltering, batch SPICE circuit simulation,
and NAM neural model training.
"""

from allomorph.pipeline.stages import (
    run_visualization,
    run_prep_audio,
    run_circuit_simulation,
    run_spice_voice,
    run_training,
)
from allomorph.pipeline.batch import (
    _run_circuit_simulation_task,
    run_spice_batch,
)
from allomorph.pipeline.cli import (
    list_instruments,
    list_voices,
    main,
)

__all__ = [
    "run_visualization",
    "run_prep_audio",
    "run_circuit_simulation",
    "run_spice_voice",
    "run_training",
    "_run_circuit_simulation_task",
    "run_spice_batch",
    "list_instruments",
    "list_voices",
    "main",
]
