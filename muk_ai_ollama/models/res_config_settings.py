from __future__ import annotations

from odoo import fields, models

from odoo.addons.muk_ai_ollama.providers.ollama import OllamaProvider


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ollama_base_url = fields.Char(
        string='Ollama Base URL',
        help='Base URL for the Ollama API. Change if Ollama runs on a remote host.',
        config_parameter='muk_ai_ollama.base_url',
        placeholder=OllamaProvider.default_url,
    )
