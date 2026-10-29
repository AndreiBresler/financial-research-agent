"""Unit tests for Settings (LLD section 4): defaults, environment and .env loading, and optional credentials."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from filing_support import PAGE_FOOTER_PATTERN
from research_agent.config import MAX_TOOL_ROUNDS_LIMIT, Settings

CREDENTIAL_VARIABLES = ["ANTHROPIC_API_KEY", "TAVILY_API_KEY"]
OVERRIDABLE_VARIABLES = ["CHUNK_MAX_TOKENS", "LLM_MODEL", "INDEX_DIR", "MAX_TOOL_ROUNDS"]
FAKE_ANTHROPIC_KEY = "sk-ant-test-not-a-real-key"
FAKE_TAVILY_KEY = "tvly-test-not-a-real-key"

EXPECTED_DEFAULTS = {
    "llm_model": "anthropic:claude-haiku-5-5",
    "llm_timeout_s": 60,
    "source_html": Path("data/aapl-20250927.htm"),
    "filing_label": "Form 10-K FY2025",
    "index_dir": Path("data/index"),
    "dense_model": "BAAI/bge-small-en-v1.5",
    "sparse_model": "Qdrant/bm25",
    "chunk_max_tokens": 400,
    "top_k": 6,
    "prefetch_limit": 20,
    "rrf_k": 60,
    "min_dense_score": 0.6,
    "xref_max_extra": 3,
    "web_max_results": 5,
    "web_timeout_s": 10,
    "max_tool_rounds": 6,
    "tool_output_max_chars": 12_000,
    "question_max_chars": 2_000,
    "prompts_dir": Path("prompts"),
    "log_path": Path("logs/agent.jsonl"),
}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove credentials and overrides from the environment so the developer's shell can't leak in."""
    for variable in [*CREDENTIAL_VARIABLES, *OVERRIDABLE_VARIABLES]:
        monkeypatch.delenv(variable, raising=False)


def settings_without_env_file() -> Settings:
    """Build Settings from the environment only, never from the project's real .env."""
    return Settings(_env_file=None)


def test_defaults_match_the_design() -> None:
    """Every tunable starts at the value LLD section 4 gives."""
    settings = settings_without_env_file()
    actual = {name: getattr(settings, name) for name in EXPECTED_DEFAULTS}
    assert actual == EXPECTED_DEFAULTS


def test_default_footer_pattern_is_the_one_the_parser_tests_use() -> None:
    """The configured footer pattern and the test suite's copy stay identical."""
    settings = settings_without_env_file()
    assert settings.page_footer_pattern == PAGE_FOOTER_PATTERN


def test_loads_without_credentials_for_ingestion() -> None:
    """Ingestion never calls the APIs, so missing keys don't stop Settings from loading."""
    settings = settings_without_env_file()
    assert settings.anthropic_api_key is None
    assert settings.tavily_api_key is None


def test_reports_missing_credentials_by_variable_name() -> None:
    """The agent's startup check can name exactly which keys are missing."""
    settings = settings_without_env_file()
    assert settings.missing_credentials() == CREDENTIAL_VARIABLES


def test_reads_credentials_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keys set in the environment load as secrets and satisfy the credential check."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC_KEY)
    monkeypatch.setenv("TAVILY_API_KEY", FAKE_TAVILY_KEY)
    settings = settings_without_env_file()
    assert settings.missing_credentials() == []
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == FAKE_ANTHROPIC_KEY


def test_secrets_never_appear_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Printing or logging Settings never reveals a key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC_KEY)
    monkeypatch.setenv("TAVILY_API_KEY", FAKE_TAVILY_KEY)
    settings = settings_without_env_file()
    rendered = repr(settings)
    assert FAKE_ANTHROPIC_KEY not in rendered
    assert FAKE_TAVILY_KEY not in rendered


def test_reads_an_env_file(tmp_path: Path) -> None:
    """Values in a .env file are loaded; one missing key is still reported."""
    env_file = tmp_path / ".env"
    env_file.write_text(f"TAVILY_API_KEY={FAKE_TAVILY_KEY}\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.tavily_api_key is not None
    assert settings.tavily_api_key.get_secret_value() == FAKE_TAVILY_KEY
    assert settings.missing_credentials() == ["ANTHROPIC_API_KEY"]


def test_environment_overrides_a_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tuning a threshold is an environment change, not a code change."""
    monkeypatch.setenv("CHUNK_MAX_TOKENS", "300")
    settings = settings_without_env_file()
    assert settings.chunk_max_tokens == 300


@pytest.mark.parametrize("rounds", [0, MAX_TOOL_ROUNDS_LIMIT + 1])
def test_rejects_a_tool_budget_outside_the_recursion_limit(monkeypatch: pytest.MonkeyPatch, rounds: int) -> None:
    """A tool budget the graph's recursion limit can't fit fails at startup, not in the middle of a question."""
    monkeypatch.setenv("MAX_TOOL_ROUNDS", str(rounds))
    with pytest.raises(ValidationError):
        settings_without_env_file()


def test_accepts_the_largest_tool_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """The largest budget that fits the recursion limit is allowed."""
    monkeypatch.setenv("MAX_TOOL_ROUNDS", str(MAX_TOOL_ROUNDS_LIMIT))
    assert settings_without_env_file().max_tool_rounds == MAX_TOOL_ROUNDS_LIMIT
