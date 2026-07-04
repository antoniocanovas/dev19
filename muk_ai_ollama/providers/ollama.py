from __future__ import annotations

import json
from collections.abc import Callable

from odoo.addons.muk_ai.providers.base import ProviderBase


class OllamaProvider(ProviderBase):
    """Ollama adapter using the OpenAI-compatible Chat Completions endpoint."""

    name = 'ollama'
    label = 'Ollama'
    default_model = 'llama3.2'
    default_url = 'http://localhost:11434/v1'

    # ----------------------------------------------------------
    # Setup
    # ----------------------------------------------------------

    def __init__(
        self,
        api_key: str = '',
        request_timeout: int = 120,
        idle_timeout: int = 90,
        max_tokens: int = 4096,
        base_url: str | None = None,
    ) -> None:
        super().__init__(api_key, request_timeout, idle_timeout, max_tokens)
        self._base_url = base_url or self.default_url

    @property
    def api_url(self) -> str:
        return self._base_url

    @property
    def api_key(self) -> str:
        # Ollama does not validate the bearer token; fall back to a placeholder
        # so the base class does not raise when no key is configured.
        return self._api_key or 'ollama'

    # ----------------------------------------------------------
    # Contract
    # ----------------------------------------------------------

    def headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def request(
        self,
        inputs,
        tools_schema=None,
        text_schema=None,
        on_delta: Callable | None = None,
        model: str | None = None,
        enable_web_search: bool = False,
        enable_image_generation: bool = False,
        enable_code_interpreter: bool = False,
        extra: dict | None = None,
    ) -> dict:
        messages = self._inputs_to_messages(inputs)
        body: dict = {
            'model': self.model_for(model),
            'messages': messages,
        }
        if self.max_tokens:
            body['max_tokens'] = self.max_tokens
        tools = self._tools_to_openai(tools_schema)
        if tools:
            body['tools'] = tools
            body['tool_choice'] = 'auto'
        if text_schema:
            body['response_format'] = {
                'type': 'json_schema',
                'json_schema': {
                    'name': text_schema.get('name', 'response'),
                    'schema': text_schema['schema'],
                    'strict': True,
                },
            }
        if callable(on_delta):
            return self._stream(body, on_delta)
        return self._parse_response(self._post_json('/chat/completions', body))

    # ----------------------------------------------------------
    # Input conversion  (muk_ai format → Chat Completions messages)
    # ----------------------------------------------------------

    @classmethod
    def _inputs_to_messages(cls, inputs) -> list:
        messages = []
        items = list(inputs or [])
        i = 0
        while i < len(items):
            item = items[i]
            role = item.get('role')
            item_type = item.get('type')

            if role == 'system':
                text = cls._text_from_content(item.get('content'))
                if text:
                    messages.append({'role': 'system', 'content': text})
                i += 1

            elif role == 'user':
                messages.append(
                    {'role': 'user', 'content': cls._user_content(item.get('content'))}
                )
                i += 1

            elif role == 'assistant':
                text = cls._text_from_content(item.get('content'))
                messages.append({'role': 'assistant', 'content': text or ''})
                i += 1

            elif item_type == 'function_call':
                # Group consecutive function_call items into one assistant message so
                # the Chat Completions message sequence stays valid.
                tool_calls = []
                while i < len(items) and items[i].get('type') == 'function_call':
                    fc = items[i]
                    args = fc.get('arguments') or '{}'
                    if not isinstance(args, str):
                        args = json.dumps(args, default=str)
                    tool_calls.append(
                        {
                            'id': fc.get('call_id') or '',
                            'type': 'function',
                            'function': {
                                'name': fc.get('name') or '',
                                'arguments': args,
                            },
                        }
                    )
                    i += 1
                messages.append(
                    {'role': 'assistant', 'content': None, 'tool_calls': tool_calls}
                )

            elif item_type == 'function_call_output':
                output = item.get('output')
                if not isinstance(output, str):
                    output = json.dumps(output, default=str)
                messages.append(
                    {
                        'role': 'tool',
                        'tool_call_id': item.get('call_id') or '',
                        'content': output,
                    }
                )
                i += 1

            else:
                i += 1

        return messages

    @staticmethod
    def _text_from_content(content) -> str:
        if isinstance(content, str):
            return content
        parts = []
        for chunk in content or []:
            if isinstance(chunk, dict) and chunk.get('text'):
                parts.append(chunk['text'])
        return '\n\n'.join(parts)

    @classmethod
    def _user_content(cls, content):
        """Return a plain string or a multimodal list for vision-capable models."""
        if isinstance(content, str):
            return content
        if not content:
            return ''
        text_parts = []
        image_parts = []
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            if chunk.get('type') == 'muk_ai_attachment':
                strategy = chunk.get('strategy')
                mimetype = chunk.get('mimetype') or 'image/jpeg'
                data_b64 = chunk.get('data_b64') or ''
                filename = chunk.get('filename') or 'attachment'
                if strategy == 'image' and data_b64:
                    image_parts.append(
                        {
                            'type': 'image_url',
                            'image_url': {'url': f'data:{mimetype};base64,{data_b64}'},
                        }
                    )
                else:
                    text = chunk.get('inline_text') or ''
                    prefix = f'--- File: {filename} ({mimetype}) ---\n'
                    if chunk.get('truncated'):
                        text += '\n[truncated]'
                    if text:
                        text_parts.append(prefix + text)
            elif chunk.get('text'):
                text_parts.append(chunk['text'])

        joined_text = '\n\n'.join(text_parts)
        if image_parts:
            parts = []
            if joined_text:
                parts.append({'type': 'text', 'text': joined_text})
            parts.extend(image_parts)
            return parts
        return joined_text

    @staticmethod
    def _tools_to_openai(tools_schema) -> list:
        if not tools_schema:
            return []
        seen: set = set()
        out = []
        for tool in tools_schema:
            name = tool.get('name')
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(
                {
                    'type': 'function',
                    'function': {
                        'name': name,
                        'description': tool.get('description') or '',
                        'parameters': tool.get('parameters')
                        or {'type': 'object', 'properties': {}},
                    },
                }
            )
        return out

    # ----------------------------------------------------------
    # Response parsing  (Chat Completions → muk_ai format)
    # ----------------------------------------------------------

    def _parse_response(self, payload: dict) -> dict:
        choice = (payload.get('choices') or [{}])[0]
        message = choice.get('message') or {}
        content = message.get('content') or ''
        tool_calls_raw = message.get('tool_calls') or []

        tool_calls = []
        carry_inputs = []

        if tool_calls_raw:
            for tc in tool_calls_raw:
                fn = tc.get('function') or {}
                raw_args = fn.get('arguments') or '{}'
                args, parse_error = self._parse_tool_arguments(raw_args)
                call_id = tc.get('id') or ''
                name = fn.get('name') or ''
                tool_calls.append(
                    {
                        'call_id': call_id,
                        'name': name,
                        'arguments': args,
                        '_parse_error': parse_error,
                    }
                )
                carry_inputs.append(
                    {
                        'type': 'function_call',
                        'call_id': call_id,
                        'name': name,
                        'arguments': raw_args
                        if isinstance(raw_args, str)
                        else json.dumps(args, default=str),
                    }
                )
        elif content:
            carry_inputs.append(
                {
                    'role': 'assistant',
                    'content': [{'type': 'output_text', 'text': content}],
                }
            )

        usage = payload.get('usage') or {}
        return {
            'text': content.strip() if content else '',
            'tool_calls': tool_calls,
            'carry_inputs': carry_inputs,
            'usage': self._usage(
                input_tokens=usage.get('prompt_tokens'),
                output_tokens=usage.get('completion_tokens'),
            ),
        }

    # ----------------------------------------------------------
    # Streaming
    # ----------------------------------------------------------

    def _stream(self, body: dict, on_delta: Callable) -> dict:
        body = {**body, 'stream': True, 'stream_options': {'include_usage': True}}
        text_parts: list[str] = []
        tool_calls_by_index: dict[int, dict] = {}
        usage: dict = {}

        for event in self._post_stream('/chat/completions', body):
            choices = event.get('choices') or []
            if not choices:
                if event.get('usage'):
                    usage = event['usage']
                continue

            choice = choices[0]
            delta = choice.get('delta') or {}

            if content := delta.get('content'):
                text_parts.append(content)
                self._call_on_delta(on_delta, 'text', {'delta': content})

            for tc_delta in delta.get('tool_calls') or []:
                index = tc_delta.get('index', 0)
                entry = tool_calls_by_index.setdefault(
                    index, {'call_id': '', 'name': '', 'arguments': ''}
                )
                if call_id := tc_delta.get('id'):
                    entry['call_id'] = call_id
                fn = tc_delta.get('function') or {}
                if name := fn.get('name'):
                    if not entry['name']:
                        entry['name'] = name
                        self._call_on_delta(
                            on_delta,
                            'tool_start',
                            {'call_id': entry['call_id'], 'name': name},
                        )
                if args_delta := fn.get('arguments'):
                    entry['arguments'] += args_delta
                    self._call_on_delta(
                        on_delta,
                        'tool_args',
                        {'call_id': entry['call_id'], 'delta': args_delta},
                    )

            if event_usage := event.get('usage'):
                usage = event_usage

        text = ''.join(text_parts).strip()
        tool_calls = []
        carry_inputs = []

        if tool_calls_by_index:
            for index in sorted(tool_calls_by_index):
                entry = tool_calls_by_index[index]
                args, parse_error = self._parse_tool_arguments(entry['arguments'])
                call_id = entry['call_id']
                name = entry['name']
                tool_calls.append(
                    {
                        'call_id': call_id,
                        'name': name,
                        'arguments': args,
                        '_parse_error': parse_error,
                    }
                )
                carry_inputs.append(
                    {
                        'type': 'function_call',
                        'call_id': call_id,
                        'name': name,
                        'arguments': json.dumps(args, default=str),
                    }
                )
        elif text:
            carry_inputs.append(
                {
                    'role': 'assistant',
                    'content': [{'type': 'output_text', 'text': text}],
                }
            )

        return {
            'text': text,
            'tool_calls': tool_calls,
            'carry_inputs': carry_inputs,
            'usage': self._usage(
                input_tokens=usage.get('prompt_tokens'),
                output_tokens=usage.get('completion_tokens'),
            ),
        }
