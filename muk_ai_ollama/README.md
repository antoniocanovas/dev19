# MuK AI Ollama

Adds **Ollama** as a local LLM provider for `muk_ai`. Run any model you
have pulled — **Llama**, **Qwen**, **Phi**, **Gemma**, **Mistral**,
**DeepSeek** — as an AI agent inside Odoo with no API key, no cloud
dependency and no data leaving your infrastructure.

The base URL is configurable from Settings so Ollama can run on
localhost, a LAN host or any remote server. Depends only on `muk_ai`.

## Requirements

[Ollama](https://ollama.com) must be installed and running before the
provider can serve requests:

```bash
ollama serve
```

Pull at least one model that supports tool calling:

```bash
ollama pull llama3.2
```

## Installation

Download the module and add it to your Odoo addons folder alongside the
`muk_ai` modules. Log on to your Odoo server, go to the Apps menu,
enable developer mode, click **Update Apps List** and install
**MuK AI Ollama**.

## Upgrade

Download the module and replace it in your Odoo addons folder. Restart
the server, open the Apps menu and click the upgrade button on
**MuK AI Ollama**.

## What ships

A new **Ollama** provider Selection value and nine pre-seeded
`muk_ai.model` records covering the most common Ollama models. All
cost rates are zero — local inference has no per-token billing.

| Model | Technical name | Context |
|-------|---------------|---------|
| Llama 3.2 | `llama3.2` | 128 K |
| Llama 3.1 | `llama3.1` | 128 K |
| Llama 3.3 | `llama3.3` | 128 K |
| Qwen 2.5 | `qwen2.5` | 32 K |
| Qwen 3 | `qwen3` | 32 K |
| Phi 4 | `phi4` | 16 K |
| Gemma 3 | `gemma3` | 128 K |
| Mistral | `mistral` | 32 K |
| DeepSeek R1 | `deepseek-r1` | 128 K |

The technical name must match exactly what you have pulled in Ollama
(`ollama list`). Add or edit model records freely in
*Settings → MuK AI → Providers → Ollama → Models*.

## Capabilities

Talks to Ollama's **OpenAI-compatible Chat Completions** endpoint
(`POST /v1/chat/completions`) with live token streaming, function/tool
calling against the `muk_mcp` registry, and image input for
vision-capable models (e.g. `llama3.2-vision`, `gemma3`).

Built-in connectors (web search, code interpreter, image generation) are
not available — they are cloud-side features of OpenAI/Mistral that have
no Ollama equivalent.

Not every Ollama model supports tool calling. Models known to work well:
`llama3.2`, `llama3.1`, `qwen2.5`, `qwen3`, `mistral`, `phi4`.

## Configuration

1. Open *Settings → MuK AI*.
2. Set **Ollama Base URL** if Ollama is not on `http://localhost:11434`
   (e.g. `http://192.168.1.10:11434/v1`).
3. Click **Manage AI Providers**, select **Ollama**, choose a default
   model and click **Test Connection**.
4. Back in Settings, set **Default Provider** to *Ollama* and start
   chatting.

No API key is required. If your Ollama instance is configured to require
one, enter it in the provider form.

## Credits

### Authors

* MuK IT

### Maintainer

This module is maintained by [MuK IT GmbH](https://www.mukit.at).
