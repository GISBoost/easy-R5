"""Orchestrator: run the whole delay pipeline for every city/resolution in
cities.CITIES. Idempotent -- prepare_data rebuilds gpkgs (cheap, R5 network
cache is reused), run_accessibility skips cases with matching .params.json,
compute_delay always recomputes from the acc gpkgs.

Run inside the QGIS Python env, one city at a time is safest (R5 memory):

    import run_all
    run_all.city("gdansk")          # all resolutions for one city
    run_all.everything()            # all cities (heavy -- Warszawa last)
"""

from __future__ import annotations

import cities as C
import prepare_data
import run_accessibility
import compute_delay


def city(name: str):
    _, resolutions = C.CITIES[name]
    for res in resolutions:
        print(f"\n===== {name} {res} m =====")
        prepare_data.main(name, res)
        run_accessibility.main(name, res)
        compute_delay.main(name, res)
    print(f"\n##### {name} complete #####")


def everything():
    order = [c for c in C.CITIES if c != "warszawa"] + (["warszawa"] if "warszawa" in C.CITIES else [])
    for name in order:
        city(name)
