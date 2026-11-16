from pathlib import Path

from agent_service.config import ConfigError


MAX_PROMPT_LENGTH = 20_000
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PromptStore:
    """Load a prompt file and re-read it when its mtime changes."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or PROJECT_ROOT
        self._cached_path: Path | None = None
        self._cached_mtime_ns: int | None = None
        self._cached_text: str | None = None

    def path(self, configured_path: str) -> Path:
        path = Path(configured_path).expanduser()
        if not path.is_absolute():
            path = self._root / path
        return path.resolve()

    def get(self, configured_path: str) -> str:
        path = self.path(configured_path)
        try:
            modified_ns = path.stat().st_mtime_ns
        except FileNotFoundError as exc:
            raise ConfigError(
                f"提示词文件不存在：{configured_path}。"
                "请检查 llm.prompt_file 配置。"
            ) from exc
        except OSError as exc:
            raise ConfigError("无法读取提示词文件。") from exc

        if (
            self._cached_text is not None
            and path == self._cached_path
            and modified_ns == self._cached_mtime_ns
        ):
            return self._cached_text

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ConfigError("无法读取提示词文件。") from exc

        text = text.strip()
        if not text:
            raise ConfigError("提示词文件内容为空。")
        if len(text) > MAX_PROMPT_LENGTH:
            raise ConfigError(
                f"提示词文件过长（上限 {MAX_PROMPT_LENGTH} 字符）。"
            )

        self._cached_path = path
        self._cached_mtime_ns = modified_ns
        self._cached_text = text
        return text