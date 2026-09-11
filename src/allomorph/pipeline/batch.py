"""
Allomorph Pipeline - Batch Concurrent Circuit Simulation
Parallel batch runner coordinating multiple circuit simulations with ProcessPoolExecutor.
"""

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional, Sequence, Union
from pathlib import Path

from allomorph.config import VOICES
from allomorph.pipeline.stages import (
    DEFAULT_LTSPICE_BIN,
    run_circuit_simulation,
)


def _run_circuit_simulation_task(task_args):
    """Top-level picklable task runner for multiprocessing."""
    voice, instrument, input_wav, backend, ltspice_bin, max_samples = task_args
    success = run_circuit_simulation(
        voice=voice,
        instrument=instrument,
        input_wav=input_wav,
        backend=backend,
        ltspice_bin=ltspice_bin,
        max_samples=max_samples,
    )
    return voice, success


def run_spice_batch(
    voices: Optional[Sequence[str]] = None,
    instrument: str = "30in",
    input_wav: Optional[Union[str, Path]] = None,
    backend: str = "native",
    ltspice_bin: str = DEFAULT_LTSPICE_BIN,
    jobs: Optional[int] = None,
    max_samples: Optional[int] = None,
) -> bool:
    """Executes batch simulation of specified voice circuit models with multi-process concurrency."""
    target_voices = voices if voices else list(VOICES.keys())
    max_workers = jobs if jobs is not None else min(4, os.cpu_count() or 4)
    samples_str = str(max_samples) if max_samples is not None else "full"

    if len(target_voices) > 1 and max_workers > 1:
        print(f"\n[Stage 3] Executing circuit simulations in parallel ({len(target_voices)} voices, {max_workers} workers, Backend: {backend}, Max Samples: {samples_str})...")
        tasks = [(v, instrument, input_wav, backend, ltspice_bin, max_samples) for v in target_voices]
        failed = []
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_run_circuit_simulation_task, task) for task in tasks]
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    v, success = future.result()
                    if not success:
                        failed.append(v)
                        print(f"  [{completed}/{len(target_voices)}] Voice simulation FAILED: {v}")
                    else:
                        print(f"  [{completed}/{len(target_voices)}] Voice simulation finished: {v}")
                except Exception as e:
                    failed.append(f"unknown (error: {e})")
                    print(f"  [{completed}/{len(target_voices)}] Voice simulation worker error: {e}")
        if failed:
            print(f"Warning: {len(failed)} voice simulations failed: {', '.join(failed)}")
            return False
        print("Batch circuit simulation finished.")
        return True
    else:
        mode_desc = "sequentially" if len(target_voices) > 1 else "single voice"
        print(f"\n[Stage 3] Executing circuit simulation {mode_desc} ({len(target_voices)} voice{'s' if len(target_voices) > 1 else ''}, Backend: {backend}, Max Samples: {samples_str})...")
        all_ok = True
        for idx, voice in enumerate(target_voices, 1):
            print(f"\n[{idx}/{len(target_voices)}] Circuit simulation: {voice} (Backend: {backend})...")
            ok = run_circuit_simulation(
                voice,
                instrument=instrument,
                input_wav=input_wav,
                backend=backend,
                ltspice_bin=ltspice_bin,
                max_samples=max_samples,
            )
            if not ok:
                all_ok = False
        print("Batch circuit simulation finished.")
        return all_ok
