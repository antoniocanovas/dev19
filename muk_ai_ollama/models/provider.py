from __future__ import annotations

from odoo import models

from odoo.addons.muk_ai_ollama.providers.ollama import OllamaProvider


class AIProviderOllama(models.Model):
    """Override _get_client for ollama so the base URL is read from system parameters."""

    _inherit = 'muk_ai.provider'

    def _get_client(self):
        if self.name != 'ollama':
            return super()._get_client()
        base_url = (
            self.env['ir.config_parameter']
            .sudo()
            .get_param('muk_ai_ollama.base_url', OllamaProvider.default_url)
        )
        context_windows = {
            model.technical_name: model.context_window
            for model in self.sudo().model_ids
            if model.technical_name and model.context_window
        }
        return OllamaProvider(
            env=self.env,
            api_key=self.sudo().api_key or '',
            request_timeout=self.request_timeout,
            idle_timeout=self.idle_timeout,
            max_tokens=self.max_tokens,
            base_url=base_url,
            context_windows=context_windows,
        )
