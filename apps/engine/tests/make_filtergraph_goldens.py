"""Regenera los goldens de filtergraph (tests/golden/filtergraph_*.json).

Solo tras un cambio DELIBERADO del plan de render, revisando el diff a mano.
Ejecutar desde apps/engine: `uv run python tests/make_filtergraph_goldens.py`.
"""
import json
from pathlib import Path

from test_render_m11 import FONTS, GOLDEN_IRS, asset_paths_for, load_ir
from vios_engine.render import ir_to_filtergraph

OUT = Path(__file__).parent / "golden"

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name in GOLDEN_IRS:
        ir = load_ir(name)
        plan = ir_to_filtergraph(ir, asset_paths_for(ir), "preview", "instagram",
                                 font_files=FONTS)
        payload = {
            "filter_complex": plan.filter_complex,
            "inputs": [list(t) for t in plan.inputs],
            "output_args": list(plan.output_args),
            "has_ass": plan.ass_content is not None,
        }
        path = OUT / f"filtergraph_{name}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"golden escrito: {path.name}")
