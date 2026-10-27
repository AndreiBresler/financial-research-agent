"""Runtime configuration (LLD section 4): environment variables and .env, validated at startup."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = ".env"
ENV_FILE_ENCODING = "utf-8"
ANTHROPIC_KEY_VARIABLE = "ANTHROPIC_API_KEY"
TAVILY_KEY_VARIABLE = "TAVILY_API_KEY"


class Settings(BaseSettings):
    """All runtime configuration. Credentials are optional here so ingestion runs without them."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding=ENV_FILE_ENCODING, extra="ignore")

    # Credentials: required only by the agent, which checks missing_credentials() at startup.
    anthropic_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    # Language model
    llm_model: str = "anthropic:claude-sonnet-5-5"
    llm_timeout_s: float = 60
    # Ingestion
    source_html: Path = Path("data/aapl-20250927.htm")
    filing_label: str = "Form 10-K FY2025"  # names the filing in every 10-K source line
    index_dir: Path = Path("data/index")
    # Footer line that closes each page; group 1 is the printed page number.
    page_footer_pattern: str = r"^Apple Inc\. \| \d{4} Form 10-K \| (\d+)$"
    dense_model: str = "BAAI/bge-small-en-v1.5"
    sparse_model: str = "Qdrant/bm25"
    chunk_max_tokens: int = 400  # headroom under the model's 512-token limit
    # Retrieval
    top_k: int = 6
    prefetch_limit: int = 20
    rrf_k: int = 60  # standard RRF constant; Qdrant defaults to 2
    min_dense_score: float = 0.6  # "not found" floor; eval: off-topic <= 0.55, on-topic >= 0.68
    xref_max_extra: int = 3
    # Tools and agent limits
    web_max_results: int = 5
    web_timeout_s: float = 10
    max_tool_rounds: int = 6
    tool_output_max_chars: int = 12_000
    question_max_chars: int = 2_000

    def missing_credentials(self) -> list[str]:
        """Return the environment variable names of the API keys that are unset or empty."""
        credentials = {ANTHROPIC_KEY_VARIABLE: self.anthropic_api_key, TAVILY_KEY_VARIABLE: self.tavily_api_key}
        return [name for name, secret in credentials.items() if secret is None or not secret.get_secret_value()]
