"""Unit tests for app/llm/interpreter.py and prompt rules."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.interpreter import (
    DirectiveInterpretationsEnvelope,
    _clean_and_parse_json,
    build_fallback_interpretations,
    interpret_operator_notes,
)
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.schemas.contract import (
    BatteryInput,
    DirectiveInterpretation,
    DirectiveType,
    SolarAdjustment,
    WindowAdjustment,
)


@pytest.fixture
def sample_battery() -> BatteryInput:
    """Fixture providing a sample BatteryInput."""
    return BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )


class TestPromptRules:
    """Verify that System Prompt contains all strictly required domain rules."""

    def test_supported_directives_present(self):
        expected_directives = [
            "solar_reduction",
            "minimum_battery_reserve",
            "no_charge_window",
            "no_discharge_window",
            "max_grid_window",
            "no_op",
        ]
        for directive in expected_directives:
            assert directive in SYSTEM_PROMPT

    def test_time_window_rules_present(self):
        assert "start-inclusive" in SYSTEM_PROMPT
        assert "end-exclusive" in SYSTEM_PROMPT
        assert "1 PM to 3 PM" in SYSTEM_PROMPT
        assert "[13, 14]" in SYSTEM_PROMPT
        assert "noon until 2 PM" in SYSTEM_PROMPT
        assert "[12, 13]" in SYSTEM_PROMPT
        assert "6 PM until 9 PM" in SYSTEM_PROMPT
        assert "[18, 19, 20]" in SYSTEM_PROMPT

    def test_solar_factor_rules_present(self):
        assert "drop to 20%" in SYSTEM_PROMPT
        assert "factor = 0.2" in SYSTEM_PROMPT
        assert "80% reduction" in SYSTEM_PROMPT

    def test_relative_reserve_rules_present(self):
        assert "capacity" in SYSTEM_PROMPT
        assert "battery.capacity_kwh" in SYSTEM_PROMPT

    def test_distractor_rules_present(self):
        assert "cafeteria" in SYSTEM_PROMPT.lower()
        assert "seminar" in SYSTEM_PROMPT.lower()
        assert "deadline" in SYSTEM_PROMPT.lower()
        assert "no_op" in SYSTEM_PROMPT

    def test_build_user_prompt(self, sample_battery):
        notes = ["Solar reduction from 1 PM to 3 PM.", "Meeting at 3 PM."]
        prompt = build_user_prompt(notes, sample_battery)
        assert "capacity_kwh: 200.0" in prompt
        assert "Note [0]: Solar reduction" in prompt
        assert "Note [1]: Meeting at 3 PM." in prompt


class TestFallbackInterpretations:
    """Verify fallback interpretations behavior."""

    def test_empty_notes(self):
        assert build_fallback_interpretations([]) == []

    def test_multiple_notes_fallback(self):
        notes = [
            "Solar will drop to 20%.",
            "Do not charge between 2 PM and 4 PM.",
            "Lunch menu changed.",
        ]
        fallbacks = build_fallback_interpretations(notes, reason="Test fallback")
        assert len(fallbacks) == 3
        for i, d in enumerate(fallbacks):
            assert d.note_index == i
            assert d.applies is False
            assert d.directive_type == DirectiveType.NO_OP
            assert d.structured_adjustment is None
            assert "Test fallback" in d.explanation


class TestCleanAndParseJson:
    """Verify robust JSON extraction and validation."""

    def test_envelope_dict_format(self):
        raw = json.dumps({
            "interpretations": [
                {
                    "note_index": 0,
                    "applies": True,
                    "directive_type": "solar_reduction",
                    "structured_adjustment": {"hours": [13, 14], "factor": 0.2},
                    "explanation": "Solar reduction note",
                },
                {
                    "note_index": 1,
                    "applies": False,
                    "directive_type": "no_op",
                    "structured_adjustment": None,
                    "explanation": "Distractor",
                },
            ]
        })
        res = _clean_and_parse_json(raw, expected_count=2)
        assert len(res) == 2
        assert res[0].directive_type == DirectiveType.SOLAR_REDUCTION
        assert isinstance(res[0].structured_adjustment, SolarAdjustment)
        assert res[1].directive_type == DirectiveType.NO_OP

    def test_markdown_code_block_format(self):
        raw = """```json
        [
            {
                "note_index": 0,
                "applies": true,
                "directive_type": "no_charge_window",
                "structured_adjustment": {"hours": [14, 15]},
                "explanation": "No charge"
            }
        ]
        ```"""
        res = _clean_and_parse_json(raw, expected_count=1)
        assert len(res) == 1
        assert res[0].directive_type == DirectiveType.NO_CHARGE_WINDOW
        assert isinstance(res[0].structured_adjustment, WindowAdjustment)

    def test_count_mismatch_raises(self):
        raw = json.dumps({
            "interpretations": [
                {
                    "note_index": 0,
                    "applies": False,
                    "directive_type": "no_op",
                    "structured_adjustment": None,
                    "explanation": "Single",
                }
            ]
        })
        with pytest.raises(ValueError, match="Expected 2 interpretations"):
            _clean_and_parse_json(raw, expected_count=2)


class TestInterpretOperatorNotes:
    """Test the full async interpret_operator_notes pipeline."""

    def test_empty_notes_returns_empty(self, sample_battery):
        res = asyncio.run(interpret_operator_notes([], sample_battery))
        assert res == []

    def test_no_api_keys_falls_back_safely(self, sample_battery, monkeypatch):
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"]:
            monkeypatch.delenv(key, raising=False)

        notes = ["Note A", "Note B"]
        res = asyncio.run(interpret_operator_notes(notes, sample_battery))
        assert len(res) == 2
        assert all(d.applies is False for d in res)
        assert all(d.directive_type == DirectiveType.NO_OP for d in res)
        assert all(d.structured_adjustment is None for d in res)

    def test_successful_llm_call(self, sample_battery, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "mock-test-key")

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "interpretations": [
                {
                    "note_index": 0,
                    "applies": True,
                    "directive_type": "solar_reduction",
                    "structured_adjustment": {"hours": [13, 14], "factor": 0.2},
                    "explanation": "Solar drop 20%",
                }
            ]
        })
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)):
            res = asyncio.run(interpret_operator_notes(["Solar drop 20%"], sample_battery))
            assert len(res) == 1
            assert res[0].applies is True
            assert res[0].directive_type == DirectiveType.SOLAR_REDUCTION
            assert isinstance(res[0].structured_adjustment, SolarAdjustment)
            assert res[0].structured_adjustment.factor == 0.2

    def test_timeout_triggers_safe_fallback(self, sample_battery, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "mock-test-key")

        async def slow_mock(*args, **kwargs):
            await asyncio.sleep(10.0)
            return None

        with patch("litellm.acompletion", new=slow_mock):
            with patch("app.llm.interpreter.STRICT_TIMEOUT_SECONDS", 0.05):
                res = asyncio.run(
                    interpret_operator_notes(["Note 1", "Note 2"], sample_battery)
                )
                assert len(res) == 2
                for i, item in enumerate(res):
                    assert item.note_index == i
                    assert item.applies is False
                    assert item.directive_type == DirectiveType.NO_OP
                    assert item.structured_adjustment is None
                    assert "timed out" in item.explanation.lower()

    def test_llm_exception_triggers_safe_fallback(self, sample_battery, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "mock-test-key")

        with patch("litellm.acompletion", new=AsyncMock(side_effect=RuntimeError("API Network crash"))):
            res = asyncio.run(interpret_operator_notes(["Some note"], sample_battery))
            assert len(res) == 1
            assert res[0].applies is False
            assert res[0].directive_type == DirectiveType.NO_OP
            assert res[0].structured_adjustment is None
            assert "RuntimeError" in res[0].explanation

    def test_malformed_json_triggers_safe_fallback(self, sample_battery, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "mock-test-key")

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Invalid non-json output from LLM"))
        ]

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)):
            res = asyncio.run(interpret_operator_notes(["Some note"], sample_battery))
            assert len(res) == 1
            assert res[0].applies is False
            assert res[0].directive_type == DirectiveType.NO_OP
            assert res[0].structured_adjustment is None
            assert "JSONDecodeError" in res[0].explanation

    def test_daily_quota_rate_limit_skips_retries_and_falls_back(
        self, sample_battery, monkeypatch
    ):
        """Gemini free-tier 20/day quota hit -> skip retries, use deterministic fallback."""
        monkeypatch.setenv("GEMINI_API_KEY", "mock-test-key")

        daily_quota_msg = (
            "litellm.RateLimitError: geminiException - "
            '"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", '
            '"quotaValue": "20" Please retry in 13.970358487s.'
        )
        with patch(
            "litellm.acompletion",
            new=AsyncMock(side_effect=Exception(daily_quota_msg)),
        ) as call_mock:
            res = asyncio.run(
                interpret_operator_notes(
                    ["Solar will drop to 20% from 1 PM to 3 PM"], sample_battery
                )
            )

        # Daily-quota must be classified as non-retryable: only ONE call
        assert call_mock.call_count == 1
        assert len(res) == 1
        # Deterministic parser recognizes "Solar ... 20% ... 1 PM to 3 PM",
        # so the fallback rule preserves it instead of returning a no_op.
        assert res[0].applies is True
        assert res[0].directive_type == DirectiveType.SOLAR_REDUCTION
        assert isinstance(res[0].structured_adjustment, SolarAdjustment)
        assert res[0].structured_adjustment.factor == 0.2
        assert res[0].structured_adjustment.hours == [13, 14]

    def test_transient_rate_limit_retries_then_succeeds(
        self, sample_battery, monkeypatch
    ):
        """Transient 429 (no daily-quota marker) -> honor retryDelay, then succeed."""
        monkeypatch.setenv("GEMINI_API_KEY", "mock-test-key")

        transient_msg = (
            "litellm.RateLimitError: geminiException - "
            '"status": "RESOURCE_EXHAUSTED" Please retry in 0.05s.'
        )
        success_payload = {
            "interpretations": [
                {
                    "note_index": 0,
                    "applies": True,
                    "directive_type": "solar_reduction",
                    "structured_adjustment": {"hours": [13, 14], "factor": 0.2},
                    "explanation": "Solar drop 20%",
                }
            ]
        }
        success_response = MagicMock()
        success_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps(success_payload)))
        ]

        call_count = {"n": 0}

        async def flaky_then_ok(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception(transient_msg)
            return success_response

        with patch("app.core.config.settings.LLM_MAX_RETRIES", 2), \
             patch("app.core.config.settings.LLM_RETRY_BASE_DELAY_SECONDS", 0.05), \
             patch("litellm.acompletion", new=flaky_then_ok):
            res = asyncio.run(
                interpret_operator_notes(["Solar drop to 20% from 1 PM to 3 PM."], sample_battery)
            )

        assert call_count["n"] == 2, "Should retry exactly once after transient 429"
        assert len(res) == 1
        assert res[0].applies is True
        assert res[0].directive_type == DirectiveType.SOLAR_REDUCTION

    def test_transient_rate_limit_exhausts_retries_and_falls_back(
        self, sample_battery, monkeypatch
    ):
        """Persistent transient 429 -> after max retries, fall back deterministically."""
        monkeypatch.setenv("GEMINI_API_KEY", "mock-test-key")

        transient_msg = (
            "litellm.RateLimitError: geminiException - "
            '"status": "RESOURCE_EXHAUSTED" Please retry in 0.05s.'
        )
        with patch(
            "litellm.acompletion",
            new=AsyncMock(side_effect=Exception(transient_msg)),
        ) as call_mock, \
             patch("app.core.config.settings.LLM_MAX_RETRIES", 1), \
             patch("app.core.config.settings.LLM_RETRY_BASE_DELAY_SECONDS", 0.02):
            res = asyncio.run(
                interpret_operator_notes(
                    ["Meeting at 5 PM about library hours"], sample_battery
                )
            )

        # 1 initial + 1 retry = 2 calls before giving up
        assert call_mock.call_count == 2
        assert len(res) == 1
        # "library" is a deterministic-parser distractor -> falls to no_op
        assert res[0].applies is False
        assert res[0].directive_type == DirectiveType.NO_OP
        assert "rate-limit" in res[0].explanation.lower() or \
               "RateLimit" in res[0].explanation
