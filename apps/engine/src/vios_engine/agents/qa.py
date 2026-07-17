"""QA/Compliance Agent (M12): guardián determinista del manual §2 sobre la IR final.

Cero LLM. Checks Q1-Q10 con evidencia exacta y agente responsable. Los fixes
son SOLO sustractivos (el QA quita, jamás añade ni sustituye — decisión Nico
P3): en la re-pasada el agente responsable repone desde la ficha respetando
QAConstraints. Loop de corrección acotado (QA_MAX_LOOPS, plan §5) que converge
por construcción: agentes deterministas + cada pasada solo elimina.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

from vios_contracts import (
    EFFECT_CTA_OVERLAY,
    EFFECT_LOGO_OVERLAY,
    EFFECT_MUSIC_MIX,
    ClientProfile,
    MediaIntelligence,
    Playbook,
    TimelineDraft,
    TimelineIR,
    TimelineValidationError,
    frames_to_s,
    validate,
)

AGENT_NAME = "qa-agent"
QA_MAX_LOOPS = 2                      # plan §5: "max 2 loops"

FIX_DROP_CTA = "drop_cta"
FIX_DROP_ASSET = "drop_asset"
FIX_DROP_MUSIC = "drop_music"
FIX_DROP_SUBTITLE = "drop_subtitle"

_GHL_TERMS = ("ghl", "go high level", "gohighlevel")
_PRICE_RE = re.compile(r"\d+[.,]?\d*\s?(?:€|eur\b|euros?\b)")


def normalize(text: str) -> str:
    """Minúsculas, sin acentos, espacios colapsados — para matching léxico."""
    nfd = unicodedata.normalize("NFD", text)
    plain = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return " ".join(plain.lower().split())


@dataclass(frozen=True)
class QAFinding:
    check: str            # Q1..Q10
    rule: str             # regla del manual §2 (o "cliender"/"playbook")
    severity: str         # block | warn
    evidence: str
    responsible: str      # edit | subtitle | branding | audio | broll | cta | pipeline
    fix: str | None = None
    target: str = ""      # asset url o texto exacto, para construir constraints


@dataclass
class QAReport:
    findings: list[QAFinding] = field(default_factory=list)

    @property
    def blocks(self) -> list[QAFinding]:
        return [f for f in self.findings if f.severity == "block"]

    @property
    def warns(self) -> list[QAFinding]:
        return [f for f in self.findings if f.severity == "warn"]

    @property
    def verdict(self) -> str:
        return "fail" if self.blocks else "pass"


@dataclass
class QAConstraints:
    """Vetos para la re-pasada F4: los agentes QUITAN lo vetado, anotándolo."""
    banned_assets: set[str] = field(default_factory=set)
    banned_subtitle_texts: set[str] = field(default_factory=set)   # normalizados
    drop_cta: bool = False
    drop_music: bool = False


class QABlocked(RuntimeError):
    """Findings block sin corrección posible: decide el humano (NEEDS_INPUT)."""

    def __init__(self, report: QAReport, passes: int) -> None:
        self.report = report
        self.passes = passes
        lines = "; ".join(f"{f.check} [{f.responsible}]: {f.evidence}"
                          for f in report.blocks)
        super().__init__(
            f"QA bloqueado tras {passes} re-pasadas — {lines}")


def constraints_from(report: QAReport) -> QAConstraints | None:
    """Constraints para la re-pasada, o None si algún block no tiene fix."""
    if any(f.fix is None for f in report.blocks):
        return None
    c = QAConstraints()
    for f in report.blocks:
        if f.fix == FIX_DROP_CTA:
            c.drop_cta = True
        elif f.fix == FIX_DROP_MUSIC:
            c.drop_music = True
        elif f.fix == FIX_DROP_ASSET:
            c.banned_assets.add(f.target)
        elif f.fix == FIX_DROP_SUBTITLE:
            c.banned_subtitle_texts.add(normalize(f.target))
    return c


class QAAgent:
    def review(
        self,
        ir: TimelineIR,
        intel_by_asset: dict[str, MediaIntelligence],
        playbook: Playbook,
        profile: ClientProfile,
    ) -> QAReport:
        report = QAReport()
        subtitle_texts = self._subtitle_texts(ir)
        cta_text = self._cta_text(ir)

        self._q1_trazabilidad(ir, intel_by_asset, profile, report)
        self._q2_subtitulos_literales(intel_by_asset, subtitle_texts, report)
        self._q3_cta_aprobado(cta_text, playbook, profile, report)
        self._q4_blacklist(subtitle_texts, cta_text, profile, report)
        self._q5_reglas_cliender(subtitle_texts, cta_text, report)
        self._q6_duracion(ir, playbook, report)
        self._q7_hook(ir, playbook, report)
        self._q8_branding(ir, profile, report)
        self._q9_auditoria(ir, playbook, report)
        self._q10_never_do(subtitle_texts, cta_text, profile, report)
        return report

    def apply_verdict(self, ir: TimelineIR, report: QAReport,
                      passes: int = 0) -> TimelineIR:
        """Commit de la revisión QA (siempre, también sin fixes — decisión Nico P2)."""
        if report.blocks:
            raise ValueError("apply_verdict con findings block: usar QALoop/QABlocked")
        draft = TimelineDraft.from_ir(ir)
        extra = f", {passes} re-pasadas" if passes else ""
        return draft.commit(
            by=AGENT_NAME,
            why=f"qa: pass ({len(report.warns)} warns{extra})",
            action="qa_pass",
        )

    # --- recolección ---

    def _subtitle_texts(self, ir: TimelineIR) -> list[str]:
        return [c.source for t in ir.tracks if t.kind == "subtitle" for c in t.clips]

    def _cta_text(self, ir: TimelineIR) -> str | None:
        for track in ir.tracks:
            if track.kind != "graphic":
                continue
            for clip in track.clips:
                for e in clip.effects:
                    if e.type == EFFECT_CTA_OVERLAY:
                        return e.params.get("text", clip.source)
        return None

    # --- checks ---

    def _q1_trazabilidad(self, ir, intel_by_asset, profile, report) -> None:
        lib = profile.library
        allowed = set(intel_by_asset)
        if lib:
            allowed |= {a.url for a in lib.broll + lib.music_sfx + lib.brand_photos}
        if profile.visual:
            allowed |= {logo.file for logo in profile.visual.logos if logo.file}
            if profile.visual.intro_outro and profile.visual.intro_outro.file:
                allowed.add(profile.visual.intro_outro.file)

        video_tracks = [t for t in ir.tracks if t.kind == "video"]
        for i, track in enumerate(video_tracks):
            for clip in track.clips:
                if clip.source in allowed:
                    continue
                if i == 0:
                    report.findings.append(QAFinding(
                        "Q1", "§2.1", "block",
                        f"clip base '{clip.id}' con source no trazable: "
                        f"'{clip.source}'", "edit"))
                else:
                    report.findings.append(QAFinding(
                        "Q1", "§2.1", "block",
                        f"b-roll '{clip.source}' no está en la biblioteca",
                        "broll", fix=FIX_DROP_ASSET, target=clip.source))
        for track in ir.tracks:
            if track.kind != "audio":
                continue
            for clip in track.clips:
                if clip.source in allowed:
                    continue
                is_music = any(e.type == EFFECT_MUSIC_MIX for e in clip.effects)
                if is_music:
                    report.findings.append(QAFinding(
                        "Q1", "§2.1", "block",
                        f"música '{clip.source}' no está en la biblioteca",
                        "audio", fix=FIX_DROP_MUSIC, target=clip.source))
                else:
                    report.findings.append(QAFinding(
                        "Q1", "§2.1", "block",
                        f"audio '{clip.source}' no trazable al bruto", "edit"))

    def _q2_subtitulos_literales(self, intel_by_asset, subtitle_texts, report) -> None:
        pool = normalize(" ".join(
            seg.text for intel in intel_by_asset.values()
            for seg in intel.transcript.segments))
        for text in subtitle_texts:
            if "[inaudible" in text.lower():
                continue                          # marcado, no inventado (§2.3)
            if normalize(text) not in pool:
                report.findings.append(QAFinding(
                    "Q2", "§2.3", "block",
                    f"subtítulo no literal del transcript: '{text}'",
                    "subtitle", fix=FIX_DROP_SUBTITLE, target=text))

    def _q3_cta_aprobado(self, cta_text, playbook, profile, report) -> None:
        if cta_text is None:
            return
        approved = set()
        if profile.audience and profile.audience.cta and profile.audience.cta.text:
            approved.add(profile.audience.cta.text)
        if playbook.cta and playbook.cta.default_text:
            approved.add(playbook.cta.default_text)
        if cta_text not in approved:              # carácter a carácter (§2.4)
            report.findings.append(QAFinding(
                "Q3", "§2.4", "block",
                f"CTA no aprobado en ficha ni playbook: '{cta_text}'",
                "cta", fix=FIX_DROP_CTA, target=cta_text))

    def _q4_blacklist(self, subtitle_texts, cta_text, profile, report) -> None:
        blacklist = profile.voice.blacklist if profile.voice else None
        if blacklist is None:
            report.findings.append(QAFinding(
                "Q4", "§2.5", "warn", "ficha sin lista negra (bloque C)", "pipeline"))
            return
        terms = (blacklist.words + blacklist.topics
                 + blacklist.competitors + blacklist.claims)
        self._match_terms("Q4", "§2.5", terms, subtitle_texts, cta_text, report)

    def _q5_reglas_cliender(self, subtitle_texts, cta_text, report) -> None:
        for kind, text in self._texts(subtitle_texts, cta_text):
            norm = normalize(text)
            if any(t in norm for t in _GHL_TERMS):
                report.findings.append(QAFinding(
                    "Q5", "cliender-ghl", "block",
                    f"mención a GHL en {kind}: '{text}'", kind))
            if _PRICE_RE.search(norm):
                report.findings.append(QAFinding(
                    "Q5", "cliender-precios", "block",
                    f"precio en {kind}: '{text}'", kind))

    def _q6_duracion(self, ir, playbook, report) -> None:
        rng = playbook.ideal_duration.get(ir.meta.platform)
        if rng is None:
            return
        base = next((t for t in ir.tracks if t.kind == "video"), None)
        total_s = (frames_to_s(sum(c.out_point - c.in_point for c in base.clips),
                               ir.fps) if base else 0.0)
        if not rng.min_s <= total_s <= rng.max_s:
            report.findings.append(QAFinding(
                "Q6", "playbook", "block",
                f"duración {total_s:.1f}s fuera del rango "
                f"[{rng.min_s}, {rng.max_s}] de '{ir.meta.platform}'", "edit"))

    def _q7_hook(self, ir, playbook, report) -> None:
        if playbook.hook is None:
            return
        hook = next((m for m in ir.markers if m.kind == "hook"), None)
        if hook is None:
            report.findings.append(QAFinding(
                "Q7", "playbook", "warn", "sin marker de hook", "edit"))
            return
        p = hook.payload
        if {"start_s", "end_s"} <= p.keys():
            dur = p["end_s"] - p["start_s"]
            if dur > playbook.hook.max_seconds:
                report.findings.append(QAFinding(
                    "Q7", "playbook", "warn",
                    f"hook de {dur:.1f}s > max {playbook.hook.max_seconds}s", "edit"))
        base = next((t for t in ir.tracks if t.kind == "video"), None)
        if base and base.clips and base.clips[0].start != 0:
            report.findings.append(QAFinding(
                "Q7", "playbook", "warn",
                f"la pieza no arranca en frame 0 (arranca en {base.clips[0].start})",
                "edit"))

    def _q8_branding(self, ir, profile, report) -> None:
        visual = profile.visual
        if visual is None:
            return
        io = visual.intro_outro
        if io and io.exists and io.mandatory:
            present = any(c.source == io.file
                          for t in ir.tracks if t.kind == "video" for c in t.clips)
            if not present:
                report.findings.append(QAFinding(
                    "Q8", "§2.1", "block",
                    f"intro/outro mandatory '{io.file}' ausente de la pieza",
                    "branding"))
        if visual.logos:
            has_logo = any(e.type == EFFECT_LOGO_OVERLAY
                           for t in ir.tracks for c in t.clips for e in c.effects)
            if not has_logo:
                report.findings.append(QAFinding(
                    "Q8", "§2.1", "warn",
                    "la ficha tiene logo pero la pieza no lleva logo_overlay",
                    "branding"))

    def _q9_auditoria(self, ir, playbook, report) -> None:
        try:
            validate(ir)
        except TimelineValidationError as exc:
            report.findings.append(QAFinding(
                "Q9", "§2.6", "block", f"IR inválida: {exc}", "pipeline"))
            return
        revs = {d.revision for d in ir.meta.decisions if d.why.strip()}
        missing = [r for r in range(1, ir.revision + 1) if r not in revs]
        if missing:
            report.findings.append(QAFinding(
                "Q9", "§2.6", "warn",
                f"revisiones sin Decision justificada: {missing}", "pipeline"))
        kinds = {m.kind for m in ir.markers}
        if playbook.cta and playbook.cta.enabled and "cta" not in kinds:
            report.findings.append(QAFinding(
                "Q9", "§2.6", "warn", "policy de CTA activa sin marker cta", "edit"))
        if "thumbnail" not in kinds:
            report.findings.append(QAFinding(
                "Q9", "§2.6", "warn", "sin marker de thumbnail", "cta"))

    def _q10_never_do(self, subtitle_texts, cta_text, profile, report) -> None:
        terms = profile.edit_rules.never_do if profile.edit_rules else []
        self._match_terms("Q10", "ficha-E", terms, subtitle_texts, cta_text, report)

    # --- helpers ---

    def _texts(self, subtitle_texts, cta_text) -> list[tuple[str, str]]:
        pairs = [("subtitle", t) for t in subtitle_texts]
        if cta_text is not None:
            pairs.append(("cta", cta_text))
        return pairs

    def _match_terms(self, check, rule, terms, subtitle_texts, cta_text, report) -> None:
        for kind, text in self._texts(subtitle_texts, cta_text):
            norm = normalize(text)
            for term in terms:
                if term and normalize(term) in norm:
                    fix = FIX_DROP_CTA if kind == "cta" else FIX_DROP_SUBTITLE
                    report.findings.append(QAFinding(
                        check, rule, "block",
                        f"término prohibido '{term}' en {kind}: '{text}'",
                        kind, fix=fix, target=text))


class QALoop:
    """Loop de corrección acotado (P1: vive en el handler, el motor no se toca).

    `rebuild(constraints)` la aporta el caller: re-ejecuta su sub-cadena F4
    desde el checkpoint de edit con los vetos. Converge por construcción.
    """

    def __init__(self, qa: QAAgent,
                 rebuild: Callable[[QAConstraints], TimelineIR],
                 max_loops: int = QA_MAX_LOOPS) -> None:
        self._qa = qa
        self._rebuild = rebuild
        self._max_loops = max_loops

    def run(self, ir, intel_by_asset, playbook, profile):
        """Devuelve (ir con revisión qa_pass, report, re-pasadas). Lanza QABlocked."""
        report = self._qa.review(ir, intel_by_asset, playbook, profile)
        passes = 0
        while report.blocks and passes < self._max_loops:
            constraints = constraints_from(report)
            if constraints is None:
                break                             # block sin fix: decide el humano
            passes += 1
            ir = self._rebuild(constraints)
            report = self._qa.review(ir, intel_by_asset, playbook, profile)
        if report.blocks:
            raise QABlocked(report, passes)
        return self._qa.apply_verdict(ir, report, passes), report, passes
