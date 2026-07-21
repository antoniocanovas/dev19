from __future__ import annotations

import contextlib
import json
from collections.abc import Callable

import requests

from odoo.addons.muk_ai.providers.base import ProviderBase


class OllamaProvider(ProviderBase):
    """Ollama adapter using the native /api/chat endpoint.

    The OpenAI-compatible /v1/chat/completions endpoint does not honor a
    per-request context-size override, so it silently runs every model at
    Ollama's server-wide default (commonly 4096 tokens). Once the system
    prompt, tool schemas, and a single tool result are in the conversation
    that budget is gone, Ollama truncates the oldest part of the prompt —
    the instructions and the user's question — and the model degrades into
    generic small talk. The native endpoint accepts `options.num_ctx`, so
    this adapter uses it to apply each model's configured context window.
    """

    name = 'ollama'
    label = 'Ollama'
    default_model = 'qwen3:14b'
    default_url = 'http://localhost:11434'
    default_context_window = 8192

    # ----------------------------------------------------------
    # Setup
    # ----------------------------------------------------------

    def __init__(
        self,
        env,
        api_key: str = '',
        request_timeout: int = 120,
        idle_timeout: int = 90,
        max_tokens: int = 4096,
        base_url: str | None = None,
        context_windows: dict[str, int] | None = None,
    ) -> None:
        super().__init__(env, api_key, request_timeout, idle_timeout, max_tokens)
        base_url = base_url or self.default_url
        # Back-compat: earlier versions of this addon pointed at the
        # OpenAI-compatible /v1 base URL — strip it so saved system
        # parameters keep working against the native API.
        self._base_url = base_url[:-3] if base_url.endswith('/v1') else base_url
        self._context_windows = context_windows or {}

    @property
    def api_url(self) -> str:
        return self._base_url

    def _context_window_for(self, model: str) -> int:
        return self._context_windows.get(model) or self.default_context_window

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
        resolved_model = self.model_for(model)
        options: dict = {'num_ctx': self._context_window_for(resolved_model)}
        if self.max_tokens:
            options['num_predict'] = self.max_tokens
        body: dict = {
            'model': resolved_model,
            'messages': messages,
            'options': options,
        }
        tools = self._tools_to_openai(tools_schema)
        if tools:
            body['tools'] = tools
        if text_schema:
            body['format'] = text_schema['schema']
        if callable(on_delta):
            return self._stream(body, on_delta)
        return self._parse_response(self._post_json('/api/chat', {**body, 'stream': False}))

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
                # the message sequence stays valid. Unlike the OpenAI-compatible
                # endpoint, Ollama's native /api/chat rejects a JSON-encoded
                # string here ("Value looks like object, but can't find closing
                # '}' symbol") — it wants the arguments as an actual object.
                tool_calls = []
                while i < len(items) and items[i].get('type') == 'function_call':
                    fc = items[i]
                    args = fc.get('arguments')
                    if isinstance(args, str):
                        try:
                            args = json.loads(args) if args else {}
                        except ValueError:
                            args = {}
                    elif not isinstance(args, dict):
                        args = {}
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
    # Response parsing  (native /api/chat → muk_ai format)
    # ----------------------------------------------------------

    def _normalize_tool_call(self, tc: dict, fallback_index: int) -> tuple[dict, dict]:
        """Return ``(tool_call, carry_input)`` for one native tool-call entry."""
        fn = tc.get('function') or {}
        raw_args = fn.get('arguments')
        if isinstance(raw_args, str):
            args, parse_error = self._parse_tool_arguments(raw_args)
        else:
            args, parse_error = (raw_args or {}), None
        call_id = tc.get('id') or f'call_{fallback_index}'
        name = fn.get('name') or ''
        tool_call = {
            'call_id': call_id,
            'name': name,
            'arguments': args,
            '_parse_error': parse_error,
        }
        carry_input = {
            'type': 'function_call',
            'call_id': call_id,
            'name': name,
            'arguments': json.dumps(args, default=str),
        }
        return tool_call, carry_input

    def _parse_response(self, payload: dict) -> dict:
        message = payload.get('message') or {}
        content = message.get('content') or ''
        tool_calls_raw = message.get('tool_calls') or []

        tool_calls = []
        carry_inputs = []

        if tool_calls_raw:
            for index, tc in enumerate(tool_calls_raw):
                tool_call, carry_input = self._normalize_tool_call(tc, index)
                tool_calls.append(tool_call)
                carry_inputs.append(carry_input)
        elif content:
            carry_inputs.append(
                {
                    'role': 'assistant',
                    'content': [{'type': 'output_text', 'text': content}],
                }
            )

        return {
            'text': content.strip() if content else '',
            'tool_calls': tool_calls,
            'carry_inputs': carry_inputs,
            'usage': self._usage(
                input_tokens=payload.get('prompt_eval_count'),
                output_tokens=payload.get('eval_count'),
            ),
        }

    # ----------------------------------------------------------
    # Streaming
    # ----------------------------------------------------------

    def _post_ndjson_stream(self, path: str, body: dict):
        """POST a JSON body and yield newline-delimited JSON objects.

        Ollama's native API streams one raw JSON object per line — unlike
        the OpenAI-compatible endpoint, there is no ``data:`` SSE prefix
        and no terminating ``[DONE]`` marker (the last object has
        ``done: true`` instead).

        :raise UserError: on HTTP, transport, or stream-idle errors.
        """
        read_timeout = self.idle_timeout
        try:
            response = requests.post(
                f'{self.api_url}{path}',
                headers=self.headers(),
                json=body,
                timeout=read_timeout,
                stream=True,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            self._raise(getattr(error.response, 'text', '') or str(error))
        except requests.RequestException as error:
            self._raise(error)
        line_iter = response.iter_lines(decode_unicode=True)
        try:
            while True:
                try:
                    raw_line = next(line_iter)
                except StopIteration:
                    break
                except requests.exceptions.ReadTimeout:
                    self._raise(f'Stream idle for {read_timeout}s — aborted')
                except requests.RequestException as error:
                    self._raise(error)
                if not raw_line:
                    continue
                try:
                    yield json.loads(raw_line)
                except ValueError:
                    continue
        finally:
            with contextlib.suppress(Exception):
                response.close()

    def _stream(self, body: dict, on_delta: Callable) -> dict:
        body = {**body, 'stream': True}
        text_parts: list[str] = []
        tool_calls_raw: list[dict] = []
        usage: dict = {}

        for event in self._post_ndjson_stream('/api/chat', body):
            message = event.get('message') or {}

            if content := message.get('content'):
                text_parts.append(content)
                self._call_on_delta(on_delta, 'text', {'delta': content})

            if tc_list := message.get('tool_calls'):
                # The native engine emits each tool call fully formed
                # (not incremental argument deltas), so keep the latest
                # complete list rather than merging by index.
                tool_calls_raw = tc_list

            if event.get('done'):
                usage = {
                    'prompt_eval_count': event.get('prompt_eval_count'),
                    'eval_count': event.get('eval_count'),
                }

        text = ''.join(text_parts).strip()
        tool_calls = []
        carry_inputs = []

        if tool_calls_raw:
            for index, tc in enumerate(tool_calls_raw):
                tool_call, carry_input = self._normalize_tool_call(tc, index)
                self._call_on_delta(
                    on_delta,
                    'tool_start',
                    {'call_id': tool_call['call_id'], 'name': tool_call['name']},
                )
                self._call_on_delta(
                    on_delta,
                    'tool_args',
                    {
                        'call_id': tool_call['call_id'],
                        'delta': carry_input['arguments'],
                    },
                )
                tool_calls.append(tool_call)
                carry_inputs.append(carry_input)
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
                input_tokens=usage.get('prompt_eval_count'),
                output_tokens=usage.get('eval_count'),
            ),
        }
