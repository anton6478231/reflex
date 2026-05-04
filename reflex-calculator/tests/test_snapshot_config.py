from copy import deepcopy

from utils.config_snapshot import (
    apply_config_snapshot,
    build_config_snapshot,
    preflight_config_snapshot,
)


DEFAULTS = {
    "model_a": {
        "parameters": {
            "revenue": {"num_clinics": 2, "setup_fee": 1000},
            "fixed_costs": {"team_salaries": 100},
            "variable_costs": {"cogs_per_device": 50},
            "assumptions": {"desired_margin": 0.2},
        }
    },
    "model_b": {
        "parameters": {
            "revenue": {"num_clinics": 2, "rental_price": 100},
            "fixed_costs": {"team_salaries": 100},
            "variable_costs": {"cogs_per_device": 50},
            "assumptions": {"desired_margin": 0.2},
        }
    },
    "model_ab": {
        "parameters": {
            "revenue": {"num_clinics": 2, "rental_price": 100, "new_cost_article": 77},
            "fixed_costs": {"team_salaries": 100},
            "variable_costs": {"cogs_per_device": 50},
            "assumptions": {"desired_margin": 0.2},
        }
    },
}

ASSUMPTION_IDS = ("A01", "A02", "A03", "A04")


class FakeState(dict):
    def __getattr__(self, item):
        return self[item]

    def __setattr__(self, key, value):
        self[key] = value


def _base_state():
    state = FakeState()
    state["num_months"] = 6
    state["saved_params"] = {
        model: deepcopy(DEFAULTS[model]["parameters"])
        for model in ("model_a", "model_b", "model_ab")
    }
    state["custom_fixed_costs"] = {model: {} for model in ("model_a", "model_b", "model_ab")}
    state["custom_variable_costs"] = {model: {} for model in ("model_a", "model_b", "model_ab")}
    state["custom_revenue"] = {model: {} for model in ("model_a", "model_b", "model_ab")}
    for aid in ASSUMPTION_IDS:
        state[f"assumption_status_{aid}"] = "hypothesis"
    # R&D phase defaults
    state["rnd_enabled"] = False
    state["rnd_months"] = 3
    state["rnd_cost_categories"] = []
    state["rnd_costs_matrix"] = {}
    return state


def test_build_snapshot_contains_payload():
    state = _base_state()
    snapshot = build_config_snapshot(state, DEFAULTS, ASSUMPTION_IDS, app_version="v-test")
    assert "payload" in snapshot
    assert snapshot["payload"]["num_months"] == 6
    assert snapshot["app_version"] == "v-test"


def test_preflight_fills_missing_new_numeric_with_zero():
    old_snapshot = {
        "schema_version": 1,
        "payload": {
            "num_months": 3,
            "saved_params": {
                "model_a": deepcopy(DEFAULTS["model_a"]["parameters"]),
                "model_b": deepcopy(DEFAULTS["model_b"]["parameters"]),
                "model_ab": {
                    "revenue": {"num_clinics": 2, "rental_price": 100},
                    "fixed_costs": {"team_salaries": 100},
                    "variable_costs": {"cogs_per_device": 50},
                    "assumptions": {"desired_margin": 0.2},
                },
            },
        },
    }
    report = preflight_config_snapshot(old_snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    assert (
        report["normalized_payload"]["saved_params"]["model_ab"]["revenue"]["new_cost_article"]
        == 0
    )


def test_preflight_reports_unknown_removed_fields():
    snapshot = {
        "schema_version": 1,
        "payload": {
            "saved_params": {
                "model_a": {
                    "revenue": {"num_clinics": 2, "setup_fee": 1000, "removed_param": 999},
                    "fixed_costs": {"team_salaries": 100},
                    "variable_costs": {"cogs_per_device": 50},
                    "assumptions": {"desired_margin": 0.2},
                },
                "model_b": deepcopy(DEFAULTS["model_b"]["parameters"]),
                "model_ab": deepcopy(DEFAULTS["model_ab"]["parameters"]),
            }
        },
    }
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    assert "saved_params.model_a.revenue.removed_param" in report["unknown_fields"]


def test_apply_snapshot_updates_state():
    state = _base_state()
    payload = {
        "num_months": 9,
        "saved_params": {
            model: deepcopy(DEFAULTS[model]["parameters"])
            for model in ("model_a", "model_b", "model_ab")
        },
        "custom_fixed_costs": {model: {} for model in ("model_a", "model_b", "model_ab")},
        "custom_variable_costs": {model: {} for model in ("model_a", "model_b", "model_ab")},
        "custom_revenue": {model: {} for model in ("model_a", "model_b", "model_ab")},
        "stage_gate_statuses": {"A01": "validated", "A02": "in_validation", "A03": "hypothesis", "A04": "validated"},
    }
    apply_config_snapshot(state, payload, ASSUMPTION_IDS)
    assert state["num_months"] == 9
    assert state["assumption_status_A01"] == "validated"
    assert state["assumption_status_A02"] == "in_validation"


# ── новые тесты: patient_modes, manual_patients_matrices, clinic_schedule ──

def _full_payload(overrides: dict | None = None) -> dict:
    """Вспомогательный payload с новыми полями."""
    payload: dict = {
        "num_months": 6,
        "saved_params": {
            model: deepcopy(DEFAULTS[model]["parameters"])
            for model in ("model_a", "model_b", "model_ab")
        },
        "custom_fixed_costs": {model: {} for model in ("model_a", "model_b", "model_ab")},
        "custom_variable_costs": {model: {} for model in ("model_a", "model_b", "model_ab")},
        "custom_revenue": {model: {} for model in ("model_a", "model_b", "model_ab")},
        "stage_gate_statuses": {aid: "hypothesis" for aid in ASSUMPTION_IDS},
        "patient_modes": {
            "model_a": "auto",
            "model_b": "manual",
            "model_ab": "auto",
        },
        "manual_patients_matrices": {
            model: [[0] * 12 for _ in range(12)]
            for model in ("model_a", "model_b", "model_ab")
        },
        "clinic_schedule": [{"month_start": 1, "count": 3}],
    }
    if overrides:
        payload.update(overrides)
    return payload


def test_build_snapshot_includes_patient_modes():
    state = _base_state()
    state["patient_mode_model_a"] = "manual"
    state["patient_mode_model_b"] = "auto"
    state["patient_mode_model_ab"] = "manual"
    snapshot = build_config_snapshot(state, DEFAULTS, ASSUMPTION_IDS)
    modes = snapshot["payload"]["patient_modes"]
    assert modes["model_a"] == "manual"
    assert modes["model_b"] == "auto"
    assert modes["model_ab"] == "manual"


def test_build_snapshot_includes_clinic_schedule():
    state = _base_state()
    state["clinic_schedule_model_a"] = [{"month_start": 2, "count": 5}]
    snapshot = build_config_snapshot(state, DEFAULTS, ASSUMPTION_IDS)
    assert snapshot["payload"]["clinic_schedule"] == [{"month_start": 2, "count": 5}]


def test_build_snapshot_includes_manual_patients_matrix():
    state = _base_state()
    mx = [[0] * 12 for _ in range(12)]
    mx[0][0] = 7
    state["manual_patients_matrix_model_b"] = mx
    snapshot = build_config_snapshot(state, DEFAULTS, ASSUMPTION_IDS)
    assert snapshot["payload"]["manual_patients_matrices"]["model_b"][0][0] == 7


def test_preflight_normalizes_unknown_patient_mode():
    snapshot = {"schema_version": 2, "payload": _full_payload({"patient_modes": {"model_a": "WRONG", "model_b": "manual", "model_ab": "auto"}})}
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    assert report["normalized_payload"]["patient_modes"]["model_a"] == "auto"
    assert report["normalized_payload"]["patient_modes"]["model_b"] == "manual"
    assert any("WRONG" in w for w in report["warnings"])


def test_preflight_fills_missing_matrices_with_zeros():
    payload = _full_payload()
    del payload["manual_patients_matrices"]
    snapshot = {"schema_version": 2, "payload": payload}
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    for model in ("model_a", "model_b", "model_ab"):
        matrix = report["normalized_payload"]["manual_patients_matrices"][model]
        assert len(matrix) == 36
        assert all(len(row) == 36 for row in matrix)
        assert all(cell == 0 for row in matrix for cell in row)
    assert any("manual_patients_matrices" in f for f in report["missing_fields"])


def test_preflight_normalizes_clinic_schedule():
    payload = _full_payload({"clinic_schedule": [{"month_start": 3, "count": 2}, {"month_start": "bad"}]})
    snapshot = {"schema_version": 2, "payload": payload}
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    sched = report["normalized_payload"]["clinic_schedule"]
    assert len(sched) == 1
    assert sched[0] == {"month_start": 3, "count": 2}


def test_preflight_reports_missing_clinic_schedule():
    payload = _full_payload()
    del payload["clinic_schedule"]
    snapshot = {"schema_version": 2, "payload": payload}
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    assert "clinic_schedule" in report["missing_fields"]
    assert report["normalized_payload"]["clinic_schedule"] == []


def test_apply_restores_patient_modes_and_matrix():
    state = _base_state()
    mx = [[0] * 12 for _ in range(12)]
    mx[1][1] = 9
    payload = _full_payload({
        "patient_modes": {"model_a": "manual", "model_b": "auto", "model_ab": "manual"},
        "manual_patients_matrices": {
            "model_a": mx,
            "model_b": [[0] * 12 for _ in range(12)],
            "model_ab": [[0] * 12 for _ in range(12)],
        },
        "clinic_schedule": [{"month_start": 2, "count": 4}],
    })
    apply_config_snapshot(state, payload, ASSUMPTION_IDS)
    assert state["patient_mode_model_a"] == "manual"
    assert state["patient_mode_model_b"] == "auto"
    assert state["patient_mode_model_ab"] == "manual"
    assert state["manual_patients_matrix_model_a"][1][1] == 9
    assert state["clinic_schedule_model_a"] == [{"month_start": 2, "count": 4}]


def test_apply_resets_clinic_schedule_init_flag():
    state = _base_state()
    state["clinic_schedule_model_a_initialized"] = True
    payload = _full_payload({"clinic_schedule": []})
    apply_config_snapshot(state, payload, ASSUMPTION_IDS)
    assert "clinic_schedule_model_a_initialized" not in state


def test_preflight_schema_version_2_no_missing_for_new_fields():
    """Слепок v2 с полными новыми полями не должен иметь missing для них."""
    snapshot = {"schema_version": 2, "payload": _full_payload()}
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    new_field_misses = [
        f for f in report["missing_fields"]
        if f.startswith("patient_modes") or f.startswith("manual_patients_matrices") or f == "clinic_schedule"
    ]
    assert new_field_misses == []


# ── R&D phase snapshot round-trip tests ────────────────────────────────────

def _full_payload_with_rnd(**rnd_overrides) -> dict:
    """Payload с R&D полями."""
    payload = _full_payload()
    payload.update({
        "rnd_enabled": True,
        "rnd_months": 3,
        "rnd_cost_categories": ["Зарплата", "Оборудование"],
        "rnd_costs_matrix": {
            "Зарплата": [100_000.0, 100_000.0, 100_000.0],
            "Оборудование": [50_000.0, 0.0, 30_000.0],
        },
    })
    payload.update(rnd_overrides)
    return payload


def test_build_snapshot_contains_rnd_fields():
    """build_config_snapshot включает R&D поля."""
    state = _base_state()
    state["rnd_enabled"] = True
    state["rnd_months"] = 2
    state["rnd_cost_categories"] = ["Cat A", "Cat B"]
    state["rnd_costs_matrix"] = {"Cat A": [1000.0, 2000.0], "Cat B": [500.0, 500.0]}
    snapshot = build_config_snapshot(state, DEFAULTS, ASSUMPTION_IDS)
    payload = snapshot["payload"]
    assert payload["rnd_enabled"] is True
    assert payload["rnd_months"] == 2
    assert payload["rnd_cost_categories"] == ["Cat A", "Cat B"]
    assert payload["rnd_costs_matrix"]["Cat A"] == [1000.0, 2000.0]


def test_preflight_rnd_fields_normalized():
    """preflight_config_snapshot корректно нормализует R&D поля."""
    snapshot = {"schema_version": 5, "payload": _full_payload_with_rnd()}
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    p = report["normalized_payload"]
    assert p["rnd_enabled"] is True
    assert p["rnd_months"] == 3
    assert "Зарплата" in p["rnd_costs_matrix"]
    assert len(p["rnd_cost_categories"]) == 2


def test_preflight_rnd_missing_fields_default_to_disabled():
    """Старые слепки без R&D полей: R&D disabled по умолчанию."""
    snapshot = {"schema_version": 4, "payload": _full_payload()}
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    p = report["normalized_payload"]
    assert p["rnd_enabled"] is False
    assert p["rnd_months"] == 3  # default
    assert p["rnd_cost_categories"] == []
    assert p["rnd_costs_matrix"] == {}
    # Поля должны быть отмечены как missing
    assert "rnd_enabled" in report["missing_fields"]


def test_apply_snapshot_restores_rnd_state():
    """apply_config_snapshot восстанавливает R&D состояние."""
    state = _base_state()
    payload = _full_payload_with_rnd()
    apply_config_snapshot(state, payload, ASSUMPTION_IDS)
    assert state["rnd_enabled"] is True
    assert state["rnd_months"] == 3
    assert state["rnd_cost_categories"] == ["Зарплата", "Оборудование"]
    assert state["rnd_costs_matrix"]["Зарплата"] == [100_000.0, 100_000.0, 100_000.0]


def test_apply_snapshot_rnd_disabled_by_default_from_old():
    """Старые слепки (без R&D полей) применяются с R&D disabled."""
    state = _base_state()
    # Устанавливаем R&D enabled
    state["rnd_enabled"] = True
    state["rnd_months"] = 5
    # Применяем старый payload без R&D полей
    payload = _full_payload()  # нет rnd_ ключей
    apply_config_snapshot(state, payload, ASSUMPTION_IDS)
    # После применения R&D должен быть disabled
    assert state["rnd_enabled"] is False


def test_preflight_rnd_months_clamped():
    """rnd_months ограничивается диапазоном [1, 24]."""
    snapshot = {"schema_version": 5, "payload": _full_payload_with_rnd(rnd_months=100)}
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["normalized_payload"]["rnd_months"] == 24


def test_preflight_rnd_costs_matrix_bad_format():
    """Плохой формат rnd_costs_matrix обрабатывается без краша."""
    snapshot = {"schema_version": 5, "payload": _full_payload_with_rnd(rnd_costs_matrix="bad")}
    report = preflight_config_snapshot(snapshot, DEFAULTS, ASSUMPTION_IDS)
    assert report["valid"]
    assert report["normalized_payload"]["rnd_costs_matrix"] == {}
