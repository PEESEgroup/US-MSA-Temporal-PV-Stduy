#!/usr/bin/env python3
"""Run static checks and report PDF build freshness for the active TeX trees."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT.parents[1]
OUTPUT = ROOT / "generated" / "static_tex_checks.json"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_comments(text: str) -> str:
    return "\n".join(re.split(r"(?<!\\)%", line, maxsplit=1)[0] for line in text.splitlines())


def resolve_tree(entry: Path) -> list[Path]:
    resolved: list[Path] = []
    seen: set[Path] = set()

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in seen:
            return
        if not path.is_file():
            raise FileNotFoundError(path)
        seen.add(path)
        resolved.append(path)
        for relative in re.findall(r"\\input\{([^}]+)\}", strip_comments(path.read_text())):
            child = ROOT / relative
            if child.suffix == "":
                child = child.with_suffix(".tex")
            visit(child)

    visit(entry)
    return resolved


def brace_balance(path: Path) -> int:
    level = 0
    text = strip_comments(path.read_text())
    for match in re.finditer(r"(?<!\\)[{}]", text):
        level += 1 if match.group() == "{" else -1
        if level < 0:
            raise ValueError(f"Negative brace balance in {path}")
    return level


def main() -> int:
    main_tree = resolve_tree(ROOT / "main.tex")
    si_tree = resolve_tree(ROOT / "supplementary.tex")
    all_paths = sorted(set(main_tree + si_tree))
    all_text = "\n".join(strip_comments(path.read_text()) for path in all_paths)
    labels = re.findall(r"\\label\{([^}]+)\}", all_text)
    refs = re.findall(r"\\(?:ref|eqref)\{([^}]+)\}", all_text)
    citations = {
        key.strip()
        for group in re.findall(r"\\cite[a-zA-Z]*\{([^}]+)\}", all_text)
        for key in group.split(",")
        if key.strip()
    }
    bib_text = (ROOT / "references.bib").read_text()
    bib_keys = set(re.findall(r"@[A-Za-z]+\{([^,]+),", bib_text))
    macro_defs = set(re.findall(r"\\providecommand\{\\([A-Za-z]+)\}", all_text))
    results_text = (ROOT / "sections" / "02_results.tex").read_text()
    results_macros = set(re.findall(r"\\([A-Z][A-Za-z]+)", results_text))
    builtin_result_tokens = {"Fig", "Supplementary"}
    missing_macros = sorted(results_macros - macro_defs - builtin_result_tokens)

    figure_names = re.findall(r"\\mainfig\{([^}]+)\}", all_text)
    missing_figures = [name for name in figure_names if not (ROOT.parent / "figures" / "v1" / name).is_file()]
    c8_manifest_path = ANALYTICS / "data_high_level" / "area_uncertainty_manifest.json"
    c8_manifest = json.loads(c8_manifest_path.read_text())
    c8_hash_failures = []
    for name, meta in c8_manifest["outputs"].items():
        path = Path(meta["path"])
        if not path.is_file() or sha256(path) != meta["sha256"]:
            c8_hash_failures.append(name)
    c12_manifest_path = ANALYTICS / "data_high_level" / "c12_partial_validation_manifest.json"
    c12_manifest = json.loads(c12_manifest_path.read_text())
    c12_hash_failures = []
    for name, meta in c12_manifest["outputs"].items():
        path = Path(meta["path"])
        if not path.is_file() or sha256(path) != meta["sha256"]:
            c12_hash_failures.append(name)

    main_pdf = ROOT / "main.pdf"
    supplementary_pdf = ROOT / "supplementary.pdf"
    main_compiled_current = main_pdf.is_file() and main_pdf.stat().st_mtime >= max(
        path.stat().st_mtime for path in main_tree
    )
    supplementary_compiled_current = (
        supplementary_pdf.is_file()
        and supplementary_pdf.stat().st_mtime
        >= max(path.stat().st_mtime for path in si_tree)
    )
    compilation_current = main_compiled_current and supplementary_compiled_current

    checks = {
        "main_inputs_resolve": True,
        "main_input_file_count_recursive": len(main_tree),
        "supplementary_inputs_resolve": True,
        "supplementary_input_file_count_recursive": len(si_tree),
        "figure_files_resolve": not missing_figures,
        "missing_figures": missing_figures,
        "all_tex_brace_balances_zero": all(brace_balance(path) == 0 for path in all_paths),
        "unique_label_count": len(set(labels)),
        "duplicate_labels": sorted(label for label in set(labels) if labels.count(label) > 1),
        "unresolved_references": sorted(set(refs) - set(labels)),
        "bibliography_key_count": len(bib_keys),
        "missing_citation_keys": sorted(citations - bib_keys),
        "draftnote_count": all_text.count("\\draftnote{"),
        "results_draftnote_count": results_text.count("\\draftnote{"),
        "results_unique_macro_reference_count": len(results_macros - builtin_result_tokens),
        "results_macros_resolve": not missing_macros,
        "missing_result_macros": missing_macros,
        "c8_manifest_status": c8_manifest["status"],
        "c8_manifest_output_count": len(c8_manifest["outputs"]),
        "c8_output_hash_failures": c8_hash_failures,
        "c8_uncertainty_connected_in_main": "generated/area_uncertainty_macros.tex"
        in (ROOT / "main.tex").read_text(),
        "c8_tables_connected_in_supplementary": all(
            value in (ROOT / "supplementary.tex").read_text()
            for value in (
                "generated/table_s5_area_uncertainty_city.tex",
                "generated/table_s6_area_uncertainty_diagnostics.tex",
            )
        ),
        "c12_manifest_status": c12_manifest["status"],
        "c12_validation_level": c12_manifest["validation_level"],
        "c12_manifest_output_count": len(c12_manifest["outputs"]),
        "c12_output_hash_failures": c12_hash_failures,
        "c12_macros_connected_in_main": "generated/c12_partial_validation_macros.tex"
        in (ROOT / "main.tex").read_text(),
        "c12_tables_connected_in_supplementary": all(
            value in (ROOT / "supplementary.tex").read_text()
            for value in (
                "generated/table_s7_scope_full_narrow.tex",
                "generated/table_s8_candidate_bridge.tex",
                "generated/table_s9_unknown_unavailable.tex",
            )
        ),
        "c12_nonidentifiability_stated_in_methods": all(
            value in (ROOT / "sections" / "04_methods.tex").read_text()
            for value in ("non-candidate", "historical disappearance", "complete historical PV capacity")
        ),
        "c12_nonidentifiability_stated_in_discussion": all(
            value in (ROOT / "sections" / "03_discussion.tex").read_text()
            for value in ("non-candidate", "historical disappearance", "complete historical PV capacity")
        ),
        "compilation_performed_for_current_revision": compilation_current,
        "main_pdf_current": main_compiled_current,
        "supplementary_pdf_current": supplementary_compiled_current,
        "compilation_reason": (
            "Both PDFs are newer than every file in their resolved TeX input trees."
            if compilation_current
            else "At least one PDF is absent or older than a file in its resolved TeX input tree."
        ),
    }
    required_true = (
        checks["figure_files_resolve"],
        checks["all_tex_brace_balances_zero"],
        not checks["duplicate_labels"],
        not checks["unresolved_references"],
        not checks["missing_citation_keys"],
        checks["results_draftnote_count"] == 0,
        checks["results_macros_resolve"],
        checks["c8_manifest_status"] == "REPRODUCED",
        not checks["c8_output_hash_failures"],
        checks["c8_uncertainty_connected_in_main"],
        checks["c8_tables_connected_in_supplementary"],
        checks["c12_manifest_status"] == "REPRODUCED",
        checks["c12_validation_level"] == "partial_validation_with_explicit_scope_limitation",
        not checks["c12_output_hash_failures"],
        checks["c12_macros_connected_in_main"],
        checks["c12_tables_connected_in_supplementary"],
        checks["c12_nonidentifiability_stated_in_methods"],
        checks["c12_nonidentifiability_stated_in_discussion"],
    )
    payload = {
        "checked_utc": now(),
        "scope": "active paper/manuscript main and supplementary TeX trees after C8 and C12 partial-validation integration",
        "checks": checks,
        "result": (
            "PASS_COMPILED" if all(required_true) and compilation_current
            else "PASS_STATIC_ONLY" if all(required_true)
            else "FAIL"
        ),
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["result"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
