"""
Utilities for exporting/importing full calculator configuration snapshots.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

SUPPORTED_MODELS = ("model_a", "model_b", "model_ab")
SNAPSHOT_SCHEMA_VERSION = 5

_DEFAULT_PREDICTOR_SETTINGS = {
    "initial_investment": 0,
    "target_breakeven_month": 3,
    "target_margin_rate": 0.25,
}

VALID_PATIENT_MODES = ("auto", "manual")
_MATRIX_SIZE = 36


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _deep_merge_with_rules(
    schema: Dict[str, Any],
    incoming: Dict[str, Any],
    parent_path: str = "",
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """
    Merge incoming payload into current schema recursively.

    Rules:
    - fields missing in incoming are filled from schema; numeric fields become 0
      to keep "new article" semantics.
    - unknown fields from incoming are collected and ignored by default.
    """
    normalized: Dict[str, Any] = {}
    missing_fields: List[str] = []
    unknown_fields: List[str] = []

    for key, schema_value in schema.items():
        path = f"{parent_path}.{key}" if parent_path else key
        if key not in incoming:
            if isinstance(schema_value, dict):
                normalized[key] = deepcopy(schema_value)
            elif _is_number(schema_value):
                normalized[key] = 0
            else:
                normalized[key] = deepcopy(schema_value)
            missing_fields.append(path)
            continue

        incoming_value = incoming[key]
        if isinstance(schema_value, dict):
            if isinstance(incoming_value, dict):
                child_norm, child_missing, child_unknown = _deep_merge_with_rules(
                    schema=schema_value,
                    incoming=incoming_value,
                    parent_path=path,
                )
                normalized[key] = child_norm
                missing_fields.extend(child_missing)
                unknown_fields.extend(child_unknown)
            else:
                normalized[key] = deepcopy(schema_value)
                missing_fields.append(path)
        else:
            normalized[key] = incoming_value

    for key in incoming.keys():
        if key not in schema:
            path = f"{parent_path}.{key}" if parent_path else key
            unknown_fields.append(path)

    return normalized, missing_fields, unknown_fields


def _build_schema_from_defaults(defaults: Dict[str, Any]) -> Dict[str, Any]:
    return {
        model: deepcopy(defaults[model]["parameters"])
        for model in SUPPORTED_MODELS
    }


def build_config_snapshot(
    session_state: Any,
    defaults: Dict[str, Any],
    assumption_ids: Tuple[str, ...],
    app_version: str = "v1.0",
    predictor_settings: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Build JSON-serializable full configuration snapshot from session state.
    """
    default_saved_params = _build_schema_from_defaults(defaults)
    saved_params = deepcopy(session_state.get("saved_params", default_saved_params))

    # num_clinics is a runtime passthrough from revenue→variable_costs (line 1696 in calculator.py).
    # It is always recomputed on render, so it must NOT be persisted in variable_costs.
    for model in SUPPORTED_MODELS:
        saved_params.get(model, {}).get("variable_costs", {}).pop("num_clinics", None)

    stage_gate_statuses = {}
    for aid in assumption_ids:
        key = f"assumption_status_{aid}"
        stage_gate_statuses[aid] = session_state.get(key, "hypothesis")

    _empty_matrix = [[0] * _MATRIX_SIZE for _ in range(_MATRIX_SIZE)]
    patient_modes = {
        model: session_state.get(f"patient_mode_{model}", "auto")
        for model in SUPPORTED_MODELS
    }
    manual_patients_matrices = {
        model: deepcopy(
            session_state.get(f"manual_patients_matrix_{model}", _empty_matrix)
        )
        for model in SUPPORTED_MODELS
    }
    clinic_schedule = list(
        deepcopy(session_state.get("clinic_schedule_model_a", []))
    )

    normalized_predictor: Dict[str, Any] = {}
    for model in SUPPORTED_MODELS:
        if predictor_settings and model in predictor_settings:
            src = predictor_settings[model]
        else:
            src = {}
        normalized_predictor[model] = {
            "initial_investment": float(src.get("initial_investment", 0)),
            "target_breakeven_month": int(src.get("target_breakeven_month", 3)),
            "target_margin_rate": float(src.get("target_margin_rate", 0.25)),
        }

    # R&D phase settings
    rnd_enabled = bool(session_state.get("rnd_enabled", False))
    rnd_months = int(session_state.get("rnd_months", 3))
    rnd_cost_categories = list(session_state.get("rnd_cost_categories", []))
    rnd_costs_matrix = deepcopy(session_state.get("rnd_costs_matrix", {}))

    payload = {
        "num_months": int(session_state.get("num_months", 3)),
        "discount_rate_annual": float(session_state.get("discount_rate_annual", 0.20)),
        "saved_params": saved_params,
        "predictor_settings": normalized_predictor,
        "custom_fixed_costs": deepcopy(
            session_state.get(
                "custom_fixed_costs",
                {model: {} for model in SUPPORTED_MODELS},
            )
        ),
        "custom_variable_costs": deepcopy(
            session_state.get(
                "custom_variable_costs",
                {model: {} for model in SUPPORTED_MODELS},
            )
        ),
        "custom_revenue": deepcopy(
            session_state.get(
                "custom_revenue",
                {model: {} for model in SUPPORTED_MODELS},
            )
        ),
        "stage_gate_statuses": stage_gate_statuses,
        "patient_modes": patient_modes,
        "manual_patients_matrices": manual_patients_matrices,
        "clinic_schedule": clinic_schedule,
        "rnd_enabled": rnd_enabled,
        "rnd_months": rnd_months,
        "rnd_cost_categories": rnd_cost_categories,
        "rnd_costs_matrix": rnd_costs_matrix,
    }

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "app_version": app_version,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def preflight_config_snapshot(
    snapshot_data: Dict[str, Any],
    defaults: Dict[str, Any],
    assumption_ids: Tuple[str, ...],
) -> Dict[str, Any]:
    """
    Validate snapshot and produce normalized payload + compatibility report.
    """
    errors: List[str] = []
    warnings: List[str] = []
    missing_fields: List[str] = []
    unknown_fields: List[str] = []

    if not isinstance(snapshot_data, dict):
        return {
            "valid": False,
            "errors": ["Файл не является JSON-объектом."],
            "warnings": [],
            "missing_fields": [],
            "unknown_fields": [],
            "normalized_payload": {},
            "meta": {},
        }

    schema_version = snapshot_data.get("schema_version")
    payload = snapshot_data.get("payload")
    if not isinstance(payload, dict):
        errors.append("В snapshot отсутствует блок payload.")

    if schema_version is None:
        warnings.append("Не найден schema_version; пробую совместимость как legacy.")
    elif not isinstance(schema_version, int):
        errors.append("schema_version должен быть целым числом.")
    elif schema_version > SNAPSHOT_SCHEMA_VERSION:
        warnings.append(
            f"Snapshot schema_version={schema_version} новее поддерживаемой "
            f"{SNAPSHOT_SCHEMA_VERSION}. Применяются только совместимые поля."
        )

    if errors:
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "missing_fields": missing_fields,
            "unknown_fields": unknown_fields,
            "normalized_payload": {},
            "meta": {},
        }

    model_schema = _build_schema_from_defaults(defaults)
    payload = payload or {}

    normalized_saved: Dict[str, Any] = {}
    incoming_saved = payload.get("saved_params", {})
    if not isinstance(incoming_saved, dict):
        incoming_saved = {}
        warnings.append("saved_params отсутствует или имеет неверный формат; применены defaults.")

    for model in SUPPORTED_MODELS:
        incoming_model = incoming_saved.get(model, {})
        if not isinstance(incoming_model, dict):
            incoming_model = {}
            warnings.append(f"saved_params.{model} имеет неверный формат; применены defaults.")
        # num_clinics in variable_costs is a runtime passthrough — silently migrate old snapshots.
        incoming_vc = incoming_model.get("variable_costs")
        if isinstance(incoming_vc, dict):
            incoming_vc.pop("num_clinics", None)
        norm, miss, unknown = _deep_merge_with_rules(
            schema=model_schema[model],
            incoming=incoming_model,
            parent_path=f"saved_params.{model}",
        )
        normalized_saved[model] = norm
        missing_fields.extend(miss)
        unknown_fields.extend(unknown)

    for model in incoming_saved.keys():
        if model not in SUPPORTED_MODELS:
            unknown_fields.append(f"saved_params.{model}")

    def _normalize_custom_block(block_name: str) -> Dict[str, Dict[str, Any]]:
        incoming_block = payload.get(block_name, {})
        normalized_block: Dict[str, Dict[str, Any]] = {model: {} for model in SUPPORTED_MODELS}
        if not isinstance(incoming_block, dict):
            warnings.append(f"{block_name} имеет неверный формат; блок сброшен.")
            return normalized_block

        for model in SUPPORTED_MODELS:
            entries = incoming_block.get(model, {})
            if not isinstance(entries, dict):
                warnings.append(f"{block_name}.{model} имеет неверный формат; блок сброшен.")
                continue
            normalized_entries: Dict[str, Any] = {}
            for name, item in entries.items():
                if isinstance(item, dict):
                    value = item.get("value", 0)
                    item_type = item.get("type", "")
                    normalized_entries[name] = {"value": value, "type": item_type}
                else:
                    normalized_entries[name] = {"value": 0, "type": ""}
                    warnings.append(f"{block_name}.{model}.{name} поврежден; сброшен в 0.")
            normalized_block[model] = normalized_entries

        for model in incoming_block.keys():
            if model not in SUPPORTED_MODELS:
                unknown_fields.append(f"{block_name}.{model}")
        return normalized_block

    normalized_custom_fixed = _normalize_custom_block("custom_fixed_costs")
    normalized_custom_variable = _normalize_custom_block("custom_variable_costs")
    normalized_custom_revenue = payload.get("custom_revenue", {model: {} for model in SUPPORTED_MODELS})
    if not isinstance(normalized_custom_revenue, dict):
        normalized_custom_revenue = {model: {} for model in SUPPORTED_MODELS}

    stage_gate_statuses = {}
    incoming_stage = payload.get("stage_gate_statuses", {})
    if not isinstance(incoming_stage, dict):
        incoming_stage = {}
    for aid in assumption_ids:
        stage_gate_statuses[aid] = incoming_stage.get(aid, "hypothesis")
        if aid not in incoming_stage:
            missing_fields.append(f"stage_gate_statuses.{aid}")
    for aid in incoming_stage.keys():
        if aid not in assumption_ids:
            unknown_fields.append(f"stage_gate_statuses.{aid}")

    num_months = payload.get("num_months", 3)
    if not isinstance(num_months, int):
        try:
            num_months = int(num_months)
        except Exception:
            num_months = 3
            warnings.append("num_months не распознан, применено 3.")
    num_months = min(max(num_months, 1), 36)

    # --- discount_rate_annual ---
    raw_discount = payload.get("discount_rate_annual")
    if raw_discount is None:
        missing_fields.append("discount_rate_annual")
        discount_rate_annual = 0.20
    else:
        try:
            discount_rate_annual = float(raw_discount)
            discount_rate_annual = min(max(discount_rate_annual, 0.0), 10.0)
        except (TypeError, ValueError):
            discount_rate_annual = 0.20
            warnings.append("discount_rate_annual не распознан, применено 0.20.")

    # --- patient_modes ---
    incoming_modes = payload.get("patient_modes", {})
    if not isinstance(incoming_modes, dict):
        incoming_modes = {}
        warnings.append("patient_modes имеет неверный формат; сброшен в 'auto' для всех моделей.")
    normalized_patient_modes: Dict[str, str] = {}
    for model in SUPPORTED_MODELS:
        raw_mode = incoming_modes.get(model, "auto")
        if raw_mode not in VALID_PATIENT_MODES:
            warnings.append(
                f"patient_modes.{model}='{raw_mode}' не распознан; применено 'auto'."
            )
            raw_mode = "auto"
        normalized_patient_modes[model] = raw_mode
    for model in incoming_modes.keys():
        if model not in SUPPORTED_MODELS:
            unknown_fields.append(f"patient_modes.{model}")
    if not incoming_modes:
        for model in SUPPORTED_MODELS:
            missing_fields.append(f"patient_modes.{model}")

    # --- manual_patients_matrices ---
    _empty_matrix = [[0] * _MATRIX_SIZE for _ in range(_MATRIX_SIZE)]
    incoming_matrices = payload.get("manual_patients_matrices", {})
    if not isinstance(incoming_matrices, dict):
        incoming_matrices = {}
        warnings.append("manual_patients_matrices имеет неверный формат; сброшены в нули.")
    normalized_matrices: Dict[str, List[List[int]]] = {}
    for model in SUPPORTED_MODELS:
        raw_matrix = incoming_matrices.get(model)
        if raw_matrix is None:
            missing_fields.append(f"manual_patients_matrices.{model}")
            normalized_matrices[model] = [row[:] for row in _empty_matrix]
            continue
        if not isinstance(raw_matrix, list):
            warnings.append(
                f"manual_patients_matrices.{model} имеет неверный формат; сброшен в нули."
            )
            normalized_matrices[model] = [row[:] for row in _empty_matrix]
            continue
        norm_matrix: List[List[int]] = []
        for i in range(_MATRIX_SIZE):
            if i < len(raw_matrix) and isinstance(raw_matrix[i], list):
                row = []
                for j in range(_MATRIX_SIZE):
                    val = raw_matrix[i][j] if j < len(raw_matrix[i]) else 0
                    try:
                        row.append(int(val))
                    except (TypeError, ValueError):
                        row.append(0)
                norm_matrix.append(row)
            else:
                norm_matrix.append([0] * _MATRIX_SIZE)
        normalized_matrices[model] = norm_matrix
    for model in incoming_matrices.keys():
        if model not in SUPPORTED_MODELS:
            unknown_fields.append(f"manual_patients_matrices.{model}")

    # --- clinic_schedule ---
    incoming_schedule = payload.get("clinic_schedule", None)
    if incoming_schedule is None:
        missing_fields.append("clinic_schedule")
        normalized_schedule: List[Dict[str, Any]] = []
    elif not isinstance(incoming_schedule, list):
        warnings.append("clinic_schedule имеет неверный формат; сброшен в [].")
        normalized_schedule = []
    else:
        normalized_schedule = []
        for entry in incoming_schedule:
            if isinstance(entry, dict):
                try:
                    month_start = int(entry.get("month_start", 1))
                    count = int(entry.get("count", 1))
                    normalized_schedule.append({"month_start": month_start, "count": count})
                except (TypeError, ValueError):
                    warnings.append(
                        f"clinic_schedule: запись {entry} содержит нечисловые значения; пропущена."
                    )
            else:
                warnings.append(
                    f"clinic_schedule: запись {entry} имеет неверный формат; пропущена."
                )

    # --- predictor_settings ---
    incoming_predictor = payload.get("predictor_settings", {})
    if not isinstance(incoming_predictor, dict):
        incoming_predictor = {}
        warnings.append("predictor_settings имеет неверный формат; применены defaults.")
    normalized_predictor_settings: Dict[str, Any] = {}
    for model in SUPPORTED_MODELS:
        src = incoming_predictor.get(model, {})
        if not isinstance(src, dict):
            src = {}
            warnings.append(f"predictor_settings.{model} имеет неверный формат; применены defaults.")
        try:
            inv = float(src.get("initial_investment", 0))
            inv = max(0.0, inv)
        except (TypeError, ValueError):
            inv = 0.0
        try:
            tbm = int(src.get("target_breakeven_month", 3))
            tbm = min(max(tbm, 1), 36)
        except (TypeError, ValueError):
            tbm = 3
        try:
            tmr = float(src.get("target_margin_rate", 0.25))
            tmr = min(max(tmr, 0.0), 1.0)
        except (TypeError, ValueError):
            tmr = 0.25
        normalized_predictor_settings[model] = {
            "initial_investment": inv,
            "target_breakeven_month": tbm,
            "target_margin_rate": tmr,
        }
        if not src:
            missing_fields.append(f"predictor_settings.{model}")
    for model in incoming_predictor.keys():
        if model not in SUPPORTED_MODELS:
            unknown_fields.append(f"predictor_settings.{model}")

    # --- rnd_enabled ---
    raw_rnd_enabled = payload.get("rnd_enabled")
    if raw_rnd_enabled is None:
        missing_fields.append("rnd_enabled")
        rnd_enabled = False
    else:
        rnd_enabled = bool(raw_rnd_enabled)

    # --- rnd_months ---
    raw_rnd_months = payload.get("rnd_months")
    if raw_rnd_months is None:
        missing_fields.append("rnd_months")
        rnd_months_normalized = 3
    else:
        try:
            rnd_months_normalized = min(max(int(raw_rnd_months), 1), 24)
        except (TypeError, ValueError):
            rnd_months_normalized = 3
            warnings.append("rnd_months не распознан, применено 3.")

    # --- rnd_cost_categories ---
    raw_rnd_cats = payload.get("rnd_cost_categories")
    if raw_rnd_cats is None:
        missing_fields.append("rnd_cost_categories")
        rnd_cost_categories: List[str] = []
    elif not isinstance(raw_rnd_cats, list):
        warnings.append("rnd_cost_categories имеет неверный формат; сброшен в [].")
        rnd_cost_categories = []
    else:
        rnd_cost_categories = [str(c) for c in raw_rnd_cats if c]

    # --- rnd_costs_matrix ---
    raw_rnd_matrix = payload.get("rnd_costs_matrix")
    if raw_rnd_matrix is None:
        missing_fields.append("rnd_costs_matrix")
        rnd_costs_matrix: Dict[str, List[float]] = {}
    elif not isinstance(raw_rnd_matrix, dict):
        warnings.append("rnd_costs_matrix имеет неверный формат; сброшена в {}.")
        rnd_costs_matrix = {}
    else:
        rnd_costs_matrix = {}
        for cat, vals in raw_rnd_matrix.items():
            if isinstance(vals, list):
                rnd_costs_matrix[str(cat)] = [
                    float(v) if isinstance(v, (int, float)) else 0.0
                    for v in vals
                ]
            else:
                warnings.append(f"rnd_costs_matrix.{cat} имеет неверный формат; сброшен в [].")
                rnd_costs_matrix[str(cat)] = []

    normalized_payload = {
        "num_months": num_months,
        "discount_rate_annual": discount_rate_annual,
        "saved_params": normalized_saved,
        "custom_fixed_costs": normalized_custom_fixed,
        "custom_variable_costs": normalized_custom_variable,
        "custom_revenue": normalized_custom_revenue,
        "stage_gate_statuses": stage_gate_statuses,
        "patient_modes": normalized_patient_modes,
        "manual_patients_matrices": normalized_matrices,
        "clinic_schedule": normalized_schedule,
        "predictor_settings": normalized_predictor_settings,
        "rnd_enabled": rnd_enabled,
        "rnd_months": rnd_months_normalized,
        "rnd_cost_categories": rnd_cost_categories,
        "rnd_costs_matrix": rnd_costs_matrix,
    }

    if unknown_fields:
        warnings.append(
            "Обнаружены поля из старой/другой версии калькулятора. "
            "Нужно подтверждение для импорта с игнорированием этих полей."
        )

    return {
        "valid": True,
        "errors": [],
        "warnings": warnings,
        "missing_fields": sorted(set(missing_fields)),
        "unknown_fields": sorted(set(unknown_fields)),
        "normalized_payload": normalized_payload,
        "meta": {
            "schema_version": schema_version,
            "app_version": snapshot_data.get("app_version", "unknown"),
            "exported_at": snapshot_data.get("exported_at", ""),
        },
    }


def apply_config_snapshot(
    session_state: Any,
    normalized_payload: Dict[str, Any],
    assumption_ids: Tuple[str, ...],
) -> None:
    """
    Apply normalized snapshot payload to Streamlit session state.
    """
    session_state.saved_params = deepcopy(normalized_payload.get("saved_params", {}))
    session_state.custom_fixed_costs = deepcopy(normalized_payload.get("custom_fixed_costs", {}))
    session_state.custom_variable_costs = deepcopy(normalized_payload.get("custom_variable_costs", {}))
    session_state.custom_revenue = deepcopy(normalized_payload.get("custom_revenue", {}))
    session_state.num_months = int(normalized_payload.get("num_months", 3))
    session_state.discount_rate_annual = float(normalized_payload.get("discount_rate_annual", 0.20))
    # Сброс виджета ставки дисконтирования, чтобы он подхватил новое значение из session_state
    for _sfx in ("_value", "_slider_widget", "_manual_widget"):
        _k = f"global_discount_rate{_sfx}"
        if _k in session_state:
            del session_state[_k]

    stage_map = normalized_payload.get("stage_gate_statuses", {})
    for aid in assumption_ids:
        session_state[f"assumption_status_{aid}"] = stage_map.get(aid, "hypothesis")

    patient_modes = normalized_payload.get("patient_modes", {})
    matrices = normalized_payload.get("manual_patients_matrices", {})
    for model in SUPPORTED_MODELS:
        session_state[f"patient_mode_{model}"] = patient_modes.get(model, "auto")
        _empty = [[0] * _MATRIX_SIZE for _ in range(_MATRIX_SIZE)]
        session_state[f"manual_patients_matrix_{model}"] = deepcopy(
            matrices.get(model, _empty)
        )

    session_state.clinic_schedule_model_a = deepcopy(
        normalized_payload.get("clinic_schedule", [])
    )
    if "clinic_schedule_model_a_initialized" in session_state:
        del session_state["clinic_schedule_model_a_initialized"]

    predictor_map = normalized_payload.get("predictor_settings", {})
    for model in SUPPORTED_MODELS:
        cfg = predictor_map.get(model, _DEFAULT_PREDICTOR_SETTINGS)
        for _key in (
            f"{model}_initial_investment",
            f"{model}_target_breakeven",
            f"{model}_target_margin_rate",
        ):
            for _suffix in ("_value", "_slider_widget", "_manual_widget"):
                if f"{_key}{_suffix}" in session_state:
                    del session_state[f"{_key}{_suffix}"]
        session_state[f"{model}_initial_investment_value"] = float(cfg.get("initial_investment", 0))
        session_state[f"{model}_target_breakeven_value"] = int(cfg.get("target_breakeven_month", 3))
        session_state[f"{model}_target_margin_rate_value"] = float(cfg.get("target_margin_rate", 0.25))

    # R&D phase settings (backward-compatible: missing keys default to disabled)
    session_state.rnd_enabled = bool(normalized_payload.get("rnd_enabled", False))
    session_state.rnd_months = int(normalized_payload.get("rnd_months", 3))
    session_state.rnd_cost_categories = list(normalized_payload.get("rnd_cost_categories", []))
    session_state.rnd_costs_matrix = deepcopy(normalized_payload.get("rnd_costs_matrix", {}))
    # Clear toggle widget key so it picks up the new value
    for _sfx in ("_value", "_slider_widget", "_manual_widget"):
        _k = f"rnd_enabled_toggle{_sfx}"
        if _k in session_state:
            del session_state[_k]
    if "rnd_months_slider" in session_state:
        del session_state["rnd_months_slider"]
