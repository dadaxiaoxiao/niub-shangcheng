import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

from agents import (
    Agent,
    FunctionTool,
    ModelSettings,
    OpenAIChatCompletionsModel,
    RawResponsesStreamEvent,
    RunConfig,
    RunItemStreamEvent,
    Runner,
    ToolCallItem,
    ToolCallOutputItem,
    set_tracing_disabled,
)
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from agent_service.config import LlmConfig
from agent_service.tools import TOOL_DEFINITIONS, ToolRunner


set_tracing_disabled(True)


@dataclass(slots=True)
class TextDelta:
    text: str


@dataclass(slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ToolResult:
    name: str
    result: dict[str, Any]


StreamEvent = TextDelta | ToolCall | ToolResult


def _parse_arguments(raw: str) -> tuple[dict[str, Any], str | None]:
    if not raw.strip():
        return {}, None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}, "工具参数不是合法的 JSON。"
    if not isinstance(parsed, dict):
        return {}, "工具参数必须是 JSON 对象。"
    return parsed, None


def _parse_tool_output(output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        return output
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            return {"output": output}
        if isinstance(parsed, dict):
            return parsed
        return {"output": parsed}
    return {"output": str(output)}


def _raw_field(raw: Any, name: str) -> str:
    """Read a field from an SDK raw item that may be a model or a dict."""
    if isinstance(raw, dict):
        value = raw.get(name)
    else:
        value = getattr(raw, name, None)
    return value if isinstance(value, str) else ""


def _build_tools(tool_runner: ToolRunner | None) -> list[FunctionTool]:
    if tool_runner is None:
        return []

    tools: list[FunctionTool] = []
    for definition in TOOL_DEFINITIONS:
        function = definition["function"]

        async def invoke(
            _context: Any,
            arguments_json: str,
            *,
            tool_name: str = function["name"],
        ) -> str:
            arguments, error = _parse_arguments(arguments_json)
            if error is not None:
                return json.dumps({"error": error}, ensure_ascii=False)
            result = await tool_runner.execute(tool_name, arguments)
            return json.dumps(result, ensure_ascii=False)

        tools.append(
            FunctionTool(
                name=function["name"],
                description=function["description"],
                params_json_schema=function["parameters"],
                on_invoke_tool=invoke,
                strict_json_schema=False,
            )
        )

    return tools


def _build_agent(
    config: LlmConfig,
    tool_runner: ToolRunner | None,
    model: OpenAIChatCompletionsModel,
    instructions: str,
) -> Agent:
    settings: dict[str, Any] = {}
    if config.temperature is not None:
        settings["temperature"] = config.temperature
    if config.max_tokens is not None:
        settings["max_tokens"] = config.max_tokens

    return Agent(
        name="Niub Shopping Assistant",
        instructions=instructions,
        tools=_build_tools(tool_runner),
        model=model,
        model_settings=ModelSettings(**settings),
    )


def _create_model(
    config: LlmConfig,
    client: AsyncOpenAI,
) -> OpenAIChatCompletionsModel:
    return OpenAIChatCompletionsModel(
        model=config.model,
        openai_client=client,
        strict_feature_validation=False,
    )


async def stream_chat(
    messages: Sequence[dict[str, str]],
    config: LlmConfig,
    tool_runner: ToolRunner | None,
    instructions: str,
) -> AsyncIterator[StreamEvent]:
    """Run a ReAct loop with the OpenAI Agents SDK and stream its progress."""
    client = AsyncOpenAI(
        api_key=config.api_key.get_secret_value(),
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        max_retries=1,
    )

    try:
        agent = _build_agent(
            config,
            tool_runner,
            _create_model(config, client),
            instructions,
        )
        result = Runner.run_streamed(
            agent,
            input=list(messages),
            max_turns=config.max_turns,
            run_config=RunConfig(tracing_disabled=True),
        )

        call_names: dict[str, str] = {}

        async for event in result.stream_events():
            if isinstance(event, RawResponsesStreamEvent):
                if (
                    isinstance(event.data, ResponseTextDeltaEvent)
                    and event.data.delta
                ):
                    yield TextDelta(event.data.delta)
                continue

            if isinstance(event, RunItemStreamEvent):
                item = event.item

                if isinstance(item, ToolCallItem):
                    raw = item.raw_item
                    call_id = _raw_field(raw, "call_id")
                    name = _raw_field(raw, "name")
                    call_names[call_id] = name
                    arguments, _ = _parse_arguments(
                        _raw_field(raw, "arguments")
                    )
                    yield ToolCall(name=name, arguments=arguments)

                elif isinstance(item, ToolCallOutputItem):
                    raw = item.raw_item
                    call_id = _raw_field(raw, "call_id")
                    yield ToolResult(
                        name=call_names.get(call_id, ""),
                        result=_parse_tool_output(item.output),
                    )
    finally:
        await client.close()


async def complete_chat(
    messages: Sequence[dict[str, str]],
    config: LlmConfig,
    tool_runner: ToolRunner | None,
    instructions: str,
) -> str:
    """Run the same agent loop without streaming and return the final text."""
    client = AsyncOpenAI(
        api_key=config.api_key.get_secret_value(),
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        max_retries=1,
    )

    try:
        agent = _build_agent(
            config,
            tool_runner,
            _create_model(config, client),
            instructions,
        )
        result = await Runner.run(
            agent,
            input=list(messages),
            max_turns=config.max_turns,
            run_config=RunConfig(tracing_disabled=True),
        )
        output = result.final_output
        if output is None:
            return ""
        return output if isinstance(output, str) else str(output)
    finally:
        await client.close()