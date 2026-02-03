"""
SSE Delta Log Parser - Core parsing logic

Extracts and combines fragmented content from SSE delta logs.
Supports multiple formats:
- LLM Orchestrator (OpenAI): choices[0].delta.content
- Anthropic Claude: content_block_delta with delta.text
- Google Gemini: candidates[].content.parts[].text
- Playground: JSON Patch operations (op: add/append)
- MAS Response: Multi-agent workflow with content[].text
- Custom: User-defined JSONPath extraction rules

Follows strict data integrity: only extracts data actually present in logs.
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StreamFormat(str, Enum):
    """Supported stream formats."""
    AUTO = "auto"                    # Auto-detect format
    ORCHESTRATOR = "orchestrator"    # OpenAI: choices[0].delta.content
    ANTHROPIC = "anthropic"          # Anthropic: content_block_delta
    GEMINI = "gemini"                # Google Gemini: candidates[].content.parts[]
    PLAYGROUND = "playground"        # JSON Patch (op: add/append)
    MAS_RESPONSE = "mas_response"    # Multi-agent: content[].text with workflow metadata
    CUSTOM = "custom"                # User-defined extraction rules


@dataclass
class CustomExtractor:
    """User-defined extraction rules using JSONPath-like syntax."""
    name: str
    content_paths: list[str]  # JSONPath expressions for content extraction
    usage_path: str | None = None
    metadata_paths: dict[str, str] = field(default_factory=dict)
    event_filter: dict[str, Any] | None = None  # Filter chunks by field values

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "content_paths": self.content_paths,
            "usage_path": self.usage_path,
            "metadata_paths": self.metadata_paths,
            "event_filter": self.event_filter,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CustomExtractor":
        return cls(
            name=data.get("name", "custom"),
            content_paths=data.get("content_paths", []),
            usage_path=data.get("usage_path"),
            metadata_paths=data.get("metadata_paths", {}),
            event_filter=data.get("event_filter"),
        )


# Pre-defined extractors for known formats
BUILTIN_EXTRACTORS: dict[str, CustomExtractor] = {
    "openai": CustomExtractor(
        name="openai",
        content_paths=["choices[0].delta.content", "choices[0].delta.tool_calls[*].function.arguments"],
        usage_path="usage",
        metadata_paths={
            "id": "id",
            "model": "model",
            "created": "created",
            "object": "object",
            "system_fingerprint": "system_fingerprint",
        },
    ),
    "anthropic": CustomExtractor(
        name="anthropic",
        content_paths=["delta.text"],
        usage_path="usage",
        metadata_paths={
            "type": "type",
            "index": "index",
        },
        event_filter={"type": "content_block_delta"},
    ),
    "gemini": CustomExtractor(
        name="gemini",
        content_paths=["candidates[0].content.parts[0].text"],
        usage_path="usageMetadata",
        metadata_paths={
            "model": "modelVersion",
        },
    ),
}


@dataclass
class ParseResult:
    """Result of parsing SSE delta logs."""
    raw_text: str
    json_data: dict | None = None
    usage: dict | None = None
    metadata: dict | None = None
    chunk_count: int = 0
    errors: list[str] = field(default_factory=list)
    detected_format: str | None = None  # Auto-detected format name


def detect_format(raw_input: str) -> StreamFormat:
    """
    Auto-detect SSE format from log content.

    Analyzes the first few chunks to determine the format.
    """
    # Sample first 5000 chars for detection
    sample = raw_input[:5000]

    # Anthropic format detection
    if '"type"' in sample and '"content_block_delta"' in sample:
        return StreamFormat.ANTHROPIC
    if '"type"' in sample and '"message_start"' in sample:
        return StreamFormat.ANTHROPIC

    # Gemini format detection
    if '"candidates"' in sample and '"content"' in sample and '"parts"' in sample:
        return StreamFormat.GEMINI

    # MAS Response format detection (multi-agent)
    if '"event_type"' in sample and '"workflow_id"' in sample:
        return StreamFormat.MAS_RESPONSE
    if '"node_id"' in sample and '"step"' in sample:
        return StreamFormat.MAS_RESPONSE

    # Playground format detection (JSON Patch)
    if '"op"' in sample and ('"append"' in sample or '"add"' in sample) and '"path"' in sample:
        return StreamFormat.PLAYGROUND

    # OpenAI/Orchestrator format detection (default fallback)
    if '"choices"' in sample and '"delta"' in sample:
        return StreamFormat.ORCHESTRATOR

    # Default to orchestrator if nothing matches
    return StreamFormat.ORCHESTRATOR


def parse_sse_logs(
    raw_input: str,
    format_type: StreamFormat = StreamFormat.ORCHESTRATOR,
    custom_extractor: CustomExtractor | dict | None = None,
) -> ParseResult:
    """
    Parse SSE delta logs and combine fragmented content.

    Args:
        raw_input: Raw SSE log text with multiple delta chunks
        format_type: Stream format to parse (or AUTO for detection)
        custom_extractor: Custom extraction rules (for CUSTOM format)

    Returns:
        ParseResult with combined text and extracted metadata
    """
    # Auto-detect format if requested
    detected = None
    if format_type == StreamFormat.AUTO:
        format_type = detect_format(raw_input)
        detected = format_type.value

    # Route to appropriate parser
    if format_type == StreamFormat.PLAYGROUND:
        result = parse_playground_logs(raw_input)
    elif format_type == StreamFormat.MAS_RESPONSE:
        result = parse_mas_response_logs(raw_input)
    elif format_type == StreamFormat.ANTHROPIC:
        result = parse_anthropic_logs(raw_input)
    elif format_type == StreamFormat.GEMINI:
        result = parse_gemini_logs(raw_input)
    elif format_type == StreamFormat.CUSTOM and custom_extractor:
        if isinstance(custom_extractor, dict):
            custom_extractor = CustomExtractor.from_dict(custom_extractor)
        result = parse_with_custom_extractor(raw_input, custom_extractor)
    else:
        result = parse_orchestrator_logs(raw_input)

    result.detected_format = detected
    return result


def get_nested_value(obj: Any, path: str) -> Any:
    """
    Get nested value from object using JSONPath-like syntax.

    Supports:
    - Simple paths: "foo.bar.baz"
    - Array indices: "foo[0].bar"
    - Wildcards: "foo[*].bar" (returns list of all matches)

    Args:
        obj: Object to extract from
        path: JSONPath-like path string

    Returns:
        Extracted value or None if not found
    """
    if not path or obj is None:
        return None

    parts = re.split(r'\.(?![^\[]*\])', path)
    current = obj

    for part in parts:
        if current is None:
            return None

        # Handle array access
        match = re.match(r'(\w+)\[(\*|\d+)\]', part)
        if match:
            key, index = match.groups()
            if key:
                current = current.get(key) if isinstance(current, dict) else None
            if current is None:
                return None
            if index == '*':
                # Wildcard - return all elements
                if isinstance(current, list):
                    return current
                return None
            else:
                idx = int(index)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
        else:
            # Simple key access
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

    return current


def extract_sse_chunks(raw_input: str) -> list[dict]:
    """
    Extract JSON chunks from SSE log text.

    Args:
        raw_input: Raw SSE log text

    Returns:
        List of parsed JSON objects
    """
    lines = raw_input.strip().split('\n')
    chunks = []

    meta_messages = {
        '[DONE]', 'start', 'end', 'reserved',
        'data: [DONE]', 'data: start', 'data: end', 'data: reserved',
        'data:[DONE]', 'data:start', 'data:end', 'data:reserved',
    }

    for line in lines:
        line = line.strip()

        if not line or line.startswith('event:') or line in meta_messages or line == 'data:':
            continue

        json_str = line
        if line.startswith('data:'):
            json_str = line[5:].strip()

        if not json_str or json_str in meta_messages:
            continue

        if not json_str.startswith('{'):
            continue

        try:
            chunk = json.loads(json_str)
            chunks.append(chunk)
        except json.JSONDecodeError:
            continue

    return chunks


def parse_with_custom_extractor(raw_input: str, extractor: CustomExtractor) -> ParseResult:
    """
    Parse SSE logs using custom extraction rules.

    Args:
        raw_input: Raw SSE log text
        extractor: Custom extraction rules

    Returns:
        ParseResult with extracted content
    """
    chunks = extract_sse_chunks(raw_input)
    contents: list[str] = []
    usage: dict | None = None
    metadata: dict | None = None
    errors: list[str] = []
    chunk_count = 0

    for chunk in chunks:
        # Apply event filter if specified
        if extractor.event_filter:
            matches = True
            for key, value in extractor.event_filter.items():
                if chunk.get(key) != value:
                    matches = False
                    break
            if not matches:
                continue

        chunk_count += 1

        # Extract content using all content paths
        for path in extractor.content_paths:
            value = get_nested_value(chunk, path)
            if value is not None:
                if isinstance(value, list):
                    for v in value:
                        if v is not None:
                            contents.append(str(v))
                else:
                    contents.append(str(value))

        # Extract usage
        if extractor.usage_path and usage is None:
            usage = get_nested_value(chunk, extractor.usage_path)

        # Extract metadata from first matching chunk
        if metadata is None and extractor.metadata_paths:
            metadata = {}
            for meta_key, meta_path in extractor.metadata_paths.items():
                value = get_nested_value(chunk, meta_path)
                if value is not None:
                    metadata[meta_key] = value
            if not metadata:
                metadata = None

    full_text = ''.join(contents)
    json_data = extract_json_from_text(full_text)

    return ParseResult(
        raw_text=full_text,
        json_data=json_data,
        usage=usage,
        metadata=metadata,
        chunk_count=chunk_count,
        errors=errors,
    )


def parse_orchestrator_logs(raw_input: str) -> ParseResult:
    """
    Parse LLM Orchestrator (OpenAI-compatible) SSE logs.

    Extracts data from choices[0].delta.content.
    """
    lines = raw_input.strip().split('\n')
    contents: list[str] = []
    usage: dict | None = None
    metadata: dict | None = None
    errors: list[str] = []
    chunk_count = 0

    metadata_fields = ('id', 'created', 'model', 'object', 'service_tier', 'system_fingerprint')
    meta_messages = {
        '[DONE]', 'start', 'end', 'reserved',
        'data: [DONE]', 'data: start', 'data: end', 'data: reserved',
    }

    for line in lines:
        line = line.strip()

        if not line or line.startswith('event:') or line in meta_messages or line == 'data:':
            continue

        json_str = line
        if line.startswith('data:'):
            json_str = line[5:].strip()

        if not json_str or json_str in meta_messages or not json_str.startswith('{'):
            continue

        try:
            chunk = json.loads(json_str)
            chunk_count += 1

            if metadata is None:
                metadata = {}
                for fld in metadata_fields:
                    if fld in chunk:
                        value = chunk[fld]
                        if fld == 'created' and isinstance(value, int):
                            from datetime import datetime
                            metadata[fld] = value
                            metadata['created_formatted'] = datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            metadata[fld] = value

            choices = chunk.get('choices', [])
            if choices and len(choices) > 0:
                delta = choices[0].get('delta', {})
                content = delta.get('content')
                if content is not None:
                    contents.append(content)

                tool_calls = delta.get('tool_calls', [])
                for tc in tool_calls:
                    func = tc.get('function', {})
                    args = func.get('arguments')
                    if args is not None:
                        contents.append(args)

            if 'usage' in chunk and chunk['usage'] is not None:
                usage = chunk['usage']

        except json.JSONDecodeError as e:
            errors.append(f"JSON parse error: {str(e)[:50]}")
            continue

    full_text = ''.join(contents)
    json_data = extract_json_from_text(full_text)

    return ParseResult(
        raw_text=full_text,
        json_data=json_data,
        usage=usage,
        metadata=metadata,
        chunk_count=chunk_count,
        errors=errors
    )


def parse_anthropic_logs(raw_input: str) -> ParseResult:
    """
    Parse Anthropic Claude SSE logs.

    Extracts content from content_block_delta events.
    Events:
    - message_start: Contains message metadata and usage
    - content_block_start: Start of content block
    - content_block_delta: Delta text content (delta.text)
    - content_block_stop: End of content block
    - message_delta: Message completion with stop_reason and usage
    - message_stop: End of message
    """
    lines = raw_input.strip().split('\n')
    contents: list[str] = []
    usage: dict | None = None
    metadata: dict | None = None
    errors: list[str] = []
    chunk_count = 0

    meta_messages = {
        '[DONE]', 'start', 'end', 'reserved',
        'data: [DONE]', 'data: start', 'data: end', 'data: reserved',
    }

    for line in lines:
        line = line.strip()

        if not line or line.startswith('event:') or line in meta_messages or line == 'data:':
            continue

        json_str = line
        if line.startswith('data:'):
            json_str = line[5:].strip()

        if not json_str or json_str in meta_messages or not json_str.startswith('{'):
            continue

        try:
            chunk = json.loads(json_str)
            event_type = chunk.get('type')

            # Extract metadata from message_start
            if event_type == 'message_start':
                chunk_count += 1
                message = chunk.get('message', {})
                if metadata is None:
                    metadata = {
                        'id': message.get('id'),
                        'type': message.get('type'),
                        'role': message.get('role'),
                        'model': message.get('model'),
                    }
                    # Remove None values
                    metadata = {k: v for k, v in metadata.items() if v is not None}

                # Extract input usage from message_start
                msg_usage = message.get('usage')
                if msg_usage:
                    usage = usage or {}
                    usage['input_tokens'] = msg_usage.get('input_tokens')

            # Extract content from content_block_delta
            elif event_type == 'content_block_delta':
                chunk_count += 1
                delta = chunk.get('delta', {})
                delta_type = delta.get('type')

                if delta_type == 'text_delta':
                    text = delta.get('text')
                    if text is not None:
                        contents.append(text)
                elif delta_type == 'input_json_delta':
                    # Tool use input
                    partial_json = delta.get('partial_json')
                    if partial_json is not None:
                        contents.append(partial_json)

            # Extract output usage from message_delta
            elif event_type == 'message_delta':
                chunk_count += 1
                delta_usage = chunk.get('usage')
                if delta_usage:
                    usage = usage or {}
                    usage['output_tokens'] = delta_usage.get('output_tokens')
                    if usage.get('input_tokens') and usage.get('output_tokens'):
                        usage['total_tokens'] = usage['input_tokens'] + usage['output_tokens']

                # Extract stop reason
                delta = chunk.get('delta', {})
                stop_reason = delta.get('stop_reason')
                if stop_reason and metadata:
                    metadata['stop_reason'] = stop_reason

            # Count other event types
            elif event_type in ('content_block_start', 'content_block_stop', 'message_stop'):
                chunk_count += 1

        except json.JSONDecodeError as e:
            errors.append(f"JSON parse error: {str(e)[:50]}")
            continue

    full_text = ''.join(contents)
    json_data = extract_json_from_text(full_text)

    return ParseResult(
        raw_text=full_text,
        json_data=json_data,
        usage=usage,
        metadata=metadata,
        chunk_count=chunk_count,
        errors=errors,
    )


def parse_gemini_logs(raw_input: str) -> ParseResult:
    """
    Parse Google Gemini SSE logs.

    Extracts content from candidates[0].content.parts[0].text.
    Note: Gemini returns cumulative text, not deltas, so we need to handle this.
    """
    lines = raw_input.strip().split('\n')
    contents: list[str] = []
    usage: dict | None = None
    metadata: dict | None = None
    errors: list[str] = []
    chunk_count = 0
    last_text = ""

    meta_messages = {
        '[DONE]', 'start', 'end', 'reserved',
        'data: [DONE]', 'data: start', 'data: end', 'data: reserved',
    }

    for line in lines:
        line = line.strip()

        if not line or line.startswith('event:') or line in meta_messages or line == 'data:':
            continue

        json_str = line
        if line.startswith('data:'):
            json_str = line[5:].strip()

        if not json_str or json_str in meta_messages or not json_str.startswith('{'):
            continue

        try:
            chunk = json.loads(json_str)
            chunk_count += 1

            # Extract metadata
            if metadata is None:
                metadata = {}
                if 'modelVersion' in chunk:
                    metadata['model'] = chunk['modelVersion']

            # Extract content from candidates
            candidates = chunk.get('candidates', [])
            if candidates and len(candidates) > 0:
                candidate = candidates[0]
                content = candidate.get('content', {})
                parts = content.get('parts', [])

                for part in parts:
                    text = part.get('text')
                    if text is not None:
                        # Gemini returns cumulative text, extract delta
                        if text.startswith(last_text):
                            delta = text[len(last_text):]
                            if delta:
                                contents.append(delta)
                            last_text = text
                        else:
                            # First chunk or non-cumulative
                            contents.append(text)
                            last_text = text

                # Extract finish reason
                finish_reason = candidate.get('finishReason')
                if finish_reason and metadata:
                    metadata['finish_reason'] = finish_reason

            # Extract usage metadata
            usage_meta = chunk.get('usageMetadata')
            if usage_meta:
                usage = {
                    'prompt_tokens': usage_meta.get('promptTokenCount'),
                    'completion_tokens': usage_meta.get('candidatesTokenCount'),
                    'total_tokens': usage_meta.get('totalTokenCount'),
                }
                # Remove None values
                usage = {k: v for k, v in usage.items() if v is not None}

        except json.JSONDecodeError as e:
            errors.append(f"JSON parse error: {str(e)[:50]}")
            continue

    full_text = ''.join(contents)
    json_data = extract_json_from_text(full_text)

    return ParseResult(
        raw_text=full_text,
        json_data=json_data,
        usage=usage if usage else None,
        metadata=metadata if metadata else None,
        chunk_count=chunk_count,
        errors=errors,
    )


def parse_playground_logs(raw_input: str) -> ParseResult:
    """
    Parse Playground SSE logs using JSON Patch format.
    """
    lines = raw_input.strip().split('\n')
    contents: list[str] = []
    errors: list[str] = []
    chunk_count = 0

    meta_messages = {
        'reserved', 'start', 'end',
        'data:reserved', 'data:start', 'data:end',
        'data: reserved', 'data: start', 'data: end',
    }

    for line in lines:
        line = line.strip()

        if not line or line.startswith('event:') or line in meta_messages or line == 'data:':
            continue

        json_str = line
        if line.startswith('data:'):
            json_str = line[5:].strip()

        if not json_str or json_str in meta_messages or not json_str.startswith('{'):
            continue

        try:
            chunk = json.loads(json_str)
            chunk_count += 1

            op = chunk.get('op')
            path = chunk.get('path', '')
            value = chunk.get('value')

            if op == 'add':
                if isinstance(value, dict) and 'content' in value:
                    content = value.get('content')
                    if content is not None:
                        contents.append(str(content))
                elif path.endswith('/content') and value is not None:
                    contents.append(str(value))

            elif op == 'append':
                if path.endswith('/content') and value is not None:
                    contents.append(str(value))

        except json.JSONDecodeError as e:
            errors.append(f"JSON parse error: {str(e)[:50]}")
            continue

    full_text = ''.join(contents)
    json_data = extract_json_from_text(full_text)

    return ParseResult(
        raw_text=full_text,
        json_data=json_data,
        usage=None,
        metadata=None,
        chunk_count=chunk_count,
        errors=errors
    )


def parse_mas_response_logs(raw_input: str) -> ParseResult:
    """
    Parse MAS (Multi-Agent System) Response SSE logs.

    This format is used for multi-agent workflows where:
    - Each agent/node produces stream events
    - Events contain workflow_id, node_id, step for tracking
    - Content is in content[].text where event_type is "stream"
    - Supports multiple content types: text, tool_use, etc.
    """
    lines = raw_input.strip().split('\n')
    contents: list[str] = []
    metadata: dict | None = None
    usage: dict | None = None
    errors: list[str] = []
    chunk_count = 0

    # Track agents/nodes for multi-agent metadata
    agents_seen: dict[str, dict] = {}

    meta_messages = {
        'reserved', 'start', 'end', '[DONE]',
        'data:reserved', 'data:start', 'data:end', 'data:[DONE]',
        'data: reserved', 'data: start', 'data: end', 'data: [DONE]',
    }

    for line in lines:
        line = line.strip()

        if not line or line.startswith('event:') or line in meta_messages or line == 'data:':
            continue

        json_str = line
        if line.startswith('data:'):
            json_str = line[5:].strip()

        if not json_str or json_str in meta_messages or not json_str.startswith('{'):
            continue

        try:
            chunk = json.loads(json_str)

            # Skip connection events
            if 'status' in chunk and chunk.get('status') == 'connected':
                continue

            chunk_count += 1
            event_type = chunk.get('event_type')

            # Track workflow metadata
            workflow_id = chunk.get('workflow_id')
            node_id = chunk.get('node_id')
            step = chunk.get('step')

            # Initialize metadata on first chunk
            if metadata is None:
                metadata = {}
                if workflow_id:
                    metadata['workflow_id'] = workflow_id
                if 'timestamp' in chunk:
                    metadata['started_at'] = chunk['timestamp']

            # Track agent/node information
            if node_id and node_id not in agents_seen:
                agents_seen[node_id] = {
                    'node_id': node_id,
                    'first_step': step,
                }

            # Extract text content from stream events
            if event_type == 'stream':
                content_list = chunk.get('content', [])
                for content_item in content_list:
                    if isinstance(content_item, dict):
                        content_type = content_item.get('type')
                        if content_type == 'text':
                            text = content_item.get('text')
                            if text is not None:
                                contents.append(text)
                        elif content_type == 'tool_use':
                            # Handle tool use content
                            tool_input = content_item.get('input')
                            if tool_input:
                                contents.append(json.dumps(tool_input))

            # Handle workflow completion
            elif event_type == 'workflow_complete':
                if metadata:
                    metadata['completed_at'] = chunk.get('timestamp')
                    metadata['total_steps'] = step

            # Handle node completion (per-agent)
            elif event_type == 'node_complete':
                if node_id and node_id in agents_seen:
                    agents_seen[node_id]['last_step'] = step

            # Extract usage if available
            if 'usage' in chunk and chunk['usage']:
                usage = chunk['usage']

        except json.JSONDecodeError as e:
            errors.append(f"JSON parse error: {str(e)[:50]}")
            continue

    # Add agents info to metadata
    if metadata and agents_seen:
        metadata['agents'] = list(agents_seen.values())
        metadata['agent_count'] = len(agents_seen)

    full_text = ''.join(contents)
    json_data = extract_json_from_text(full_text)

    return ParseResult(
        raw_text=full_text,
        json_data=json_data,
        usage=usage,
        metadata=metadata,
        chunk_count=chunk_count,
        errors=errors
    )


def extract_json_from_text(text: str) -> dict | None:
    """
    Extract JSON object from text if present.
    """
    if not text:
        return None

    start_idx = text.find('{')
    if start_idx == -1:
        return None

    depth = 0
    end_idx = -1
    in_string = False
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                end_idx = i
                break

    if end_idx == -1:
        return None

    json_str = text[start_idx:end_idx + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def format_json(data: Any, indent: int = 2) -> str:
    """Format JSON data with indentation for display."""
    return json.dumps(data, indent=indent, ensure_ascii=False)


def get_supported_formats() -> list[dict]:
    """Get list of supported formats with descriptions."""
    return [
        {
            "id": "auto",
            "name": "Auto Detect",
            "description": "자동으로 포맷을 감지합니다",
        },
        {
            "id": "orchestrator",
            "name": "OpenAI / Orchestrator",
            "description": "OpenAI API 및 호환 API (choices[0].delta.content)",
        },
        {
            "id": "anthropic",
            "name": "Anthropic Claude",
            "description": "Anthropic Claude API (content_block_delta)",
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "description": "Google Gemini API (candidates[].content.parts[])",
        },
        {
            "id": "playground",
            "name": "Playground",
            "description": "JSON Patch 기반 스트리밍 (op: add/append)",
        },
        {
            "id": "mas_response",
            "name": "MAS Response",
            "description": "멀티에이전트 워크플로우 (workflow_id, node_id, step)",
        },
        {
            "id": "custom",
            "name": "Custom",
            "description": "사용자 정의 추출 규칙 (JSONPath)",
        },
    ]
