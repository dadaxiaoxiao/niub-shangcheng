import os
from pathlib import Path

import yaml
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
)


class LlmConfig(BaseModel):
    base_url: str = Field(
        default="https://api.openai.com/v1",
        min_length=1,
        validation_alias=AliasChoices("base_url", "baseUrl", "baseURL"),
    )
    api_key: SecretStr = Field(
        min_length=1,
        validation_alias=AliasChoices("api_key", "apiKey", "apikey"),
    )
    model: str = Field(min_length=1)
    prompt_file: str = Field(
        default="prompts/shopping_agent.md",
        min_length=1,
        validation_alias=AliasChoices("prompt_file", "promptFile"),
    )
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        validation_alias=AliasChoices("max_tokens", "maxTokens"),
    )
    max_turns: int = Field(
        default=6,
        ge=1,
        le=20,
        validation_alias=AliasChoices("max_turns", "maxTurns"),
    )
    timeout_seconds: float = Field(
        default=60,
        gt=0,
        validation_alias=AliasChoices("timeout_seconds", "timeoutSeconds"),
    )

    @field_validator("base_url", "api_key", mode="before")
    @classmethod
    def expand_environment_variables(cls, value: object) -> object:
        if isinstance(value, str):
            return os.path.expandvars(value)
        return value


class MallConfig(BaseModel):
    base_url: str = Field(
        default="http://127.0.0.1:3001",
        min_length=1,
        validation_alias=AliasChoices("base_url", "baseUrl", "baseURL"),
    )
    timeout_seconds: float = Field(
        default=5,
        gt=0,
        validation_alias=AliasChoices("timeout_seconds", "timeoutSeconds"),
    )
    demo_user_id: str = Field(
        default="u-demo",
        min_length=1,
        max_length=64,
        validation_alias=AliasChoices("demo_user_id", "demoUserId"),
    )

    @field_validator("base_url", mode="before")
    @classmethod
    def expand_environment_variables(cls, value: object) -> object:
        if isinstance(value, str):
            return os.path.expandvars(value)
        return value


class AppConfig(BaseModel):
    llm: LlmConfig
    mall: MallConfig = Field(default_factory=MallConfig)


class ConfigError(RuntimeError):
    """A safe, user-facing configuration error."""


class ConfigStore:
    """Load YAML config and refresh it when the file changes."""

    def __init__(self) -> None:
        self._cached_path: Path | None = None
        self._cached_mtime_ns: int | None = None
        self._cached_config: AppConfig | None = None

    def path(self) -> Path:
        configured_path = os.getenv("AGENT_CONFIG_FILE")
        if configured_path:
            path = Path(configured_path).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
        else:
            path = Path(__file__).resolve().parents[2] / "config" / "llm.yaml"
        return path.resolve()

    def get(self) -> AppConfig:
        path = self.path()
        try:
            modified_ns = path.stat().st_mtime_ns
        except FileNotFoundError as exc:
            raise ConfigError(
                "模型配置文件不存在，请创建 config/llm.yaml 或设置 AGENT_CONFIG_FILE。"
            ) from exc

        if (
            self._cached_config is not None
            and path == self._cached_path
            and modified_ns == self._cached_mtime_ns
        ):
            return self._cached_config

        try:
            raw_config = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            raise ConfigError("无法读取模型配置文件。") from exc
        except yaml.YAMLError as exc:
            raise ConfigError("模型配置文件的 YAML 格式无效。") from exc

        if not isinstance(raw_config, dict):
            raise ConfigError("模型配置文件必须是一个 YAML 对象。")

        llm_section = raw_config.get("llm")
        if isinstance(llm_section, dict) and (
            "system_prompt" in llm_section or "systemPrompt" in llm_section
        ):
            raise ConfigError(
                "llm.system_prompt 已废弃：请把提示词移到 prompts/shopping_agent.md，"
                "并在配置中设置 llm.prompt_file。"
            )

        try:
            config = AppConfig.model_validate(raw_config)
        except ValidationError as exc:
            fields = ", ".join(
                ".".join(str(part) for part in error["loc"])
                for error in exc.errors(include_input=False, include_url=False)
            )
            raise ConfigError(f"模型配置校验失败：{fields}") from exc

        self._cached_path = path
        self._cached_mtime_ns = modified_ns
        self._cached_config = config
        return config


config_store = ConfigStore()

