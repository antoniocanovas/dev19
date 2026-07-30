{
    'name': 'MuK AI Ollama',
    'summary': 'Ollama local LLM provider for the MuK AI Assistant',
    'description': """
        Adds Ollama as a provider for muk_ai. Talks to Ollama's OpenAI-compatible
        Chat Completions endpoint so any model you have pulled (Llama, Qwen, Phi,
        Gemma, Mistral, DeepSeek…) is immediately available as an AI agent inside
        Odoo — no API key required, everything stays on your infrastructure.
        The base URL is configurable from Settings in case Ollama runs on a remote
        host or non-default port.
    """,
    'version': '19.0.1.0.2',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'author': 'MuK IT',
    'website': 'http://www.mukit.at',
    'depends': [
        'muk_ai',
    ],
    'data': [
        'data/provider.xml',
        'data/model.xml',
        'views/res_config_settings.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
