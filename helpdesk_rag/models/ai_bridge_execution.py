import logging
import traceback
from io import StringIO

import requests

from odoo import models

_logger = logging.getLogger(__name__)

# El bridge de OCA llama con `timeout=30` fijo, y su vía de escape está rota: al
# expandir `_execute_kwargs()` sobre la misma llamada, un `timeout` ahí dentro
# llegaría duplicado a `requests.post` y reventaría con TypeError. Treinta
# segundos se quedan cortos con un modelo local: la respuesta de "cómo
# transferir archivos a otro ordenador desde macbook" son 2.177 caracteres y
# tarda 31,6 s, así que Odoo cortaba la conexión y mostraba "AI Bridge Failed"
# aunque n8n la hubiera completado bien.
TIEMPO_ESPERA_POR_DEFECTO = 180


class AiBridgeExecution(models.Model):
    _inherit = "ai.bridge.execution"

    def _rag_timeout(self):
        """Segundos de espera, configurables en 'helpdesk_rag.bridge_timeout'."""
        valor = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("helpdesk_rag.bridge_timeout")
        )
        try:
            return int(valor) if valor else TIEMPO_ESPERA_POR_DEFECTO
        except (TypeError, ValueError):
            _logger.warning(
                "helpdesk_rag.bridge_timeout no es un número (%r); se usan %ss",
                valor,
                TIEMPO_ESPERA_POR_DEFECTO,
            )
            return TIEMPO_ESPERA_POR_DEFECTO

    def _execute(self, **kwargs):
        """Copia del método de OCA cambiando solo el timeout.

        Se reimplementa entero porque el original fija el valor en la propia
        llamada a `requests.post` y no hay forma de inyectarlo desde fuera. Si
        OCA cambia este método, hay que revisar esta copia.
        """
        self.ensure_one()
        record = None
        if self.res_id and self.model_id:
            record = self.env[self.sudo().model_id.model].browse(self.res_id)
        payload = self.ai_bridge_id._prepare_payload(
            record=record,
            res_id=self.res_id,
            model=self.sudo().model_id.model,
            **kwargs,
        )
        payload = self._add_extra_payload_fields(payload)
        kwargs_extra = self._execute_kwargs(**kwargs)
        # Si algún día OCA arregla su override, mandaría 'timeout' aquí dentro y
        # llegaría duplicado: gana el suyo y esta copia no estorba.
        kwargs_extra.pop("timeout", None)
        try:
            response = requests.post(
                self.ai_bridge_id.url,
                json=payload,
                auth=self._get_auth(),
                headers=self._get_headers(),
                timeout=self._rag_timeout(),
                **kwargs_extra,
            )
            self.result = response.content
            response.raise_for_status()
            self.state = "done"
            self.payload = payload
            if self.ai_bridge_id.result_kind == "immediate":
                return self._process_response(response.json())
        except Exception:
            self.state = "error"
            self.payload = payload
            buff = StringIO()
            traceback.print_exc(file=buff)
            self.error = buff.getvalue()
            buff.close()
