"""Tests M12: QAAgent (Q1-Q10), constraints, apply_verdict y QALoop acotado.

Deterministas, cero LLM. El caso pass usa las fixtures canónicas del e2e
(make_golden_rev7); las violaciones se construyen ad hoc con TimelineDraft.
"""
import pytest
from vios_contracts import (
    Blacklist,
    Canvas,
    EditRules,
    IntroOutro,
    TimelineDraft,
    Voice,
    create_timeline,
)
from vios_engine.agents import (
    EditAgent,
    QAAgent,
    QABlocked,
    QAConstraints,
    QALoop,
    constraints_from,
)
from vios_engine.agents.qa import FIX_DROP_CTA, FIX_DROP_SUBTITLE, normalize

from .make_golden_rev7 import make_fixtures, run_f4


@pytest.fixture()
def env():
    playbook, client, intel, plan = make_fixtures()
    ir_edit = EditAgent(fps=30).build_timeline(plan, playbook)
    ir = run_f4(ir_edit, intel, playbook, client)
    return playbook, client, intel, ir_edit, ir


def findings(report, check):
    return [f for f in report.findings if f.check == check]


def tampered(ir, **edits):
    """Copia de la IR con clips añadidos vía draft (viola algo a propósito)."""
    d = TimelineDraft.from_ir(ir)
    for kind, clips in edits.items():
        tid = d.add_track(kind)
        for clip in clips:
            d.add_clip(tid, **clip)
    return d.commit(by="test", why="fixture de violación")


# --- caso pass (fixtures canónicas) ---

def test_review_pass_en_rev7(env):
    playbook, client, intel, _, ir = env
    report = QAAgent().review(ir, intel, playbook, client)
    assert report.verdict == "pass"
    # la ficha del e2e no tiene blacklist → warn Q4, jamás silencio
    assert any(f.check == "Q4" and "lista negra" in f.evidence
               for f in report.warns)


def test_apply_verdict_crea_revision_auditada(env):
    playbook, client, intel, _, ir = env
    qa = QAAgent()
    report = qa.review(ir, intel, playbook, client)
    ir2 = qa.apply_verdict(ir, report)
    assert ir2.revision == ir.revision + 1
    last = ir2.meta.decisions[-1]
    assert last.agent == "qa-agent" and last.action == "qa_pass"
    assert "pass" in last.why


# --- Q1 trazabilidad ---

def test_q1_broll_no_trazable_fix_drop(env):
    playbook, client, intel, _, ir = env
    bad = tampered(ir, video=[{"source": "stock-pirata.mp4", "start": 100,
                               "in_point": 0, "out_point": 30}])
    report = QAAgent().review(bad, intel, playbook, client)
    f = findings(report, "Q1")[0]
    assert f.severity == "block" and f.target == "stock-pirata.mp4"
    assert f.fix is not None and f.responsible == "broll"


def test_q1_bruto_desconocido_sin_fix(env):
    playbook, client, intel, ir_edit, _ = env
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel-educativo")
    d = TimelineDraft.from_ir(base)
    vt = d.add_track("video")
    d.add_clip(vt, source="bruto-fantasma", start=0, in_point=0, out_point=900)
    ir = d.commit(by="edit-agent", why="fixture")
    f = findings(QAAgent().review(ir, intel, playbook, client), "Q1")[0]
    assert f.fix is None and f.responsible == "edit"


# --- Q2 subtítulos literales ---

def test_q2_subtitulo_parafraseado_block(env):
    playbook, client, intel, _, ir = env
    bad = tampered(ir, subtitle=[{"source": "texto que nadie dijo",
                                  "start": 0, "in_point": 0, "out_point": 30}])
    f = findings(QAAgent().review(bad, intel, playbook, client), "Q2")[0]
    assert f.severity == "block" and f.fix == FIX_DROP_SUBTITLE


def test_q2_inaudible_pasa(env):
    playbook, client, intel, _, ir = env
    ok = tampered(ir, subtitle=[{"source": "[inaudible @ 00:12]",
                                 "start": 0, "in_point": 0, "out_point": 30}])
    assert findings(QAAgent().review(ok, intel, playbook, client), "Q2") == []


# --- Q3 CTA aprobado ---

def test_q3_cta_no_aprobado(env):
    playbook, client, intel, _, ir = env
    # la ficha cambió después de editar: el CTA de la IR ya no está aprobado
    client2 = client.model_copy(update={"audience": None})
    playbook2 = playbook.model_copy(update={"cta": None})
    f = findings(QAAgent().review(ir, intel, playbook2, client2), "Q3")[0]
    assert f.severity == "block" and f.fix == FIX_DROP_CTA


# --- Q4 blacklist / Q10 never_do ---

def with_blacklist(client, **kw):
    return client.model_copy(update={
        "voice": Voice(tone=["experto"], blacklist=Blacklist(**kw))})


def test_q4_blacklist_en_subtitulo(env):
    playbook, client, intel, _, ir = env
    bad = tampered(ir, subtitle=[{"source": "La clave es el sistema...",
                                  "start": 300, "in_point": 0, "out_point": 30}])
    client2 = with_blacklist(client, words=["sistema"])
    fs = findings(QAAgent().review(bad, intel, playbook, client2), "Q4")
    assert fs and all(f.severity == "block" for f in fs)
    assert fs[0].fix == FIX_DROP_SUBTITLE


def test_q10_never_do(env):
    playbook, client, intel, _, ir = env
    client2 = client.model_copy(update={
        "edit_rules": EditRules(never_do=["reserva tu llamada"])})
    f = findings(QAAgent().review(ir, intel, playbook, client2), "Q10")[0]
    assert f.severity == "block" and f.fix == FIX_DROP_CTA


# --- Q5 reglas Cliender (sin fix: decide el humano) ---

def test_q5_ghl_y_precio_block_sin_fix(env):
    playbook, client, intel, _, ir = env
    bad = tampered(ir, subtitle=[
        {"source": "usamos Go High Level", "start": 0, "in_point": 0, "out_point": 30},
        {"source": "solo 99€ al mes", "start": 30, "in_point": 0, "out_point": 30},
    ])
    fs = findings(QAAgent().review(bad, intel, playbook, client), "Q5")
    assert len(fs) == 2
    assert all(f.severity == "block" and f.fix is None for f in fs)


# --- Q6 / Q7 / Q8 / Q9 ---

def test_q6_duracion_fuera_de_rango(env):
    playbook, client, intel, ir_edit, _ = env
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel-educativo")
    d = TimelineDraft.from_ir(base)
    vt = d.add_track("video")
    d.add_clip(vt, source="a1", start=0, in_point=0, out_point=90)  # 3s < min 15s
    ir = d.commit(by="edit-agent", why="pieza demasiado corta")
    f = findings(QAAgent().review(ir, intel, playbook, client), "Q6")[0]
    assert f.severity == "block" and f.fix is None and f.responsible == "edit"


def test_q7_sin_hook_warn(env):
    playbook, client, intel, _, ir = env
    d = TimelineDraft.from_ir(ir)
    for m in ir.markers:
        if m.kind == "hook":
            d.remove_marker(m.id)
    f = findings(QAAgent().review(d.commit(by="t", why="sin hook"),
                                  intel, playbook, client), "Q7")[0]
    assert f.severity == "warn"


def test_q8_outro_mandatory_ausente_block(env):
    playbook, client, intel, _, ir = env
    client2 = client.model_copy(update={"visual": client.visual.model_copy(
        update={"intro_outro": IntroOutro(exists=True, file="outro.mp4",
                                          mandatory=True)})})
    f = findings(QAAgent().review(ir, intel, playbook, client2), "Q8")[0]
    assert f.severity == "block" and f.responsible == "branding"


def test_q9_sin_thumbnail_warn(env):
    playbook, client, intel, _, ir = env
    d = TimelineDraft.from_ir(ir)
    for m in ir.markers:
        if m.kind == "thumbnail":
            d.remove_marker(m.id)
    fs = findings(QAAgent().review(d.commit(by="t", why="sin thumb"),
                                   intel, playbook, client), "Q9")
    assert any("thumbnail" in f.evidence for f in fs)


# --- constraints ---

def test_constraints_from_unfixable_none(env):
    playbook, client, intel, _, ir = env
    bad = tampered(ir, subtitle=[{"source": "solo 99€", "start": 0,
                                  "in_point": 0, "out_point": 30}])
    report = QAAgent().review(bad, intel, playbook, client)
    assert constraints_from(report) is None       # Q5 no tiene fix


def test_constraints_from_fixable(env):
    playbook, client, intel, _, ir = env
    client2 = client.model_copy(update={"audience": None})
    playbook2 = playbook.model_copy(update={"cta": None})
    report = QAAgent().review(ir, intel, playbook2, client2)
    c = constraints_from(report)
    assert isinstance(c, QAConstraints) and c.drop_cta


# --- QALoop: corrección acotada ---

def test_qaloop_pass_directo_crea_rev8(env):
    playbook, client, intel, ir_edit, ir = env
    loop = QALoop(QAAgent(), rebuild=lambda c: run_f4(ir_edit, intel, playbook,
                                                      client, constraints=c))
    ir2, report, passes = loop.run(ir, intel, playbook, client)
    assert passes == 0
    assert ir2.revision == 8
    assert ir2.meta.decisions[-1].agent == "qa-agent"


def test_qaloop_corrige_con_drop_y_converge(env):
    playbook, client, intel, ir_edit, ir = env
    # ficha cambió tras editar: el CTA de la IR ya no está aprobado → DROP + re-pasada
    client2 = client.model_copy(update={"audience": None})
    playbook2 = playbook.model_copy(update={"cta": None})
    loop = QALoop(QAAgent(), rebuild=lambda c: run_f4(ir_edit, intel, playbook2,
                                                      client2, constraints=c))
    ir2, report, passes = loop.run(ir, intel, playbook2, client2)
    assert passes == 1
    assert report.verdict == "pass"
    # el agente responsable repuso (omitió) y lo anotó — el QA no parchea
    assert any("vetado por QA" in d.why for d in ir2.meta.decisions)
    cta_clips = [c for t in ir2.tracks if t.kind == "graphic" for c in t.clips
                 if any(e.type == "cta_overlay" for e in c.effects)]
    assert cta_clips == []


def test_qaloop_block_sin_fix_falla_al_humano(env):
    playbook, client, intel, ir_edit, ir = env
    bad = tampered(ir, subtitle=[{"source": "solo 99€", "start": 0,
                                  "in_point": 0, "out_point": 30}])
    loop = QALoop(QAAgent(), rebuild=lambda c: run_f4(ir_edit, intel, playbook,
                                                      client, constraints=c))
    with pytest.raises(QABlocked, match="Q5"):
        loop.run(bad, intel, playbook, client)


def test_normalize():
    assert normalize("  Máximo   RENDIMIENTO ") == "maximo rendimiento"
