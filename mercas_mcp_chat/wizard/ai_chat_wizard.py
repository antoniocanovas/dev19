import html
import logging

from odoo import _, api, fields, models

from odoo.addons.odoo_mcp_manager import utils as mcp_utils
from odoo.addons.odoo_mcp_manager.services.bot_gateway_service import (
    BotGatewayService,
    LLMRouter,
)

_logger = logging.getLogger(__name__)

# Tools whose output is already human-readable text — no need to humanize it.
_TEXT_TOOLS = {'ask_ai', 'analyze_records'}


class AiChatWizard(models.TransientModel):
    """Backend console to talk to the MCP AI stack without leaving Odoo.

    Reuses the same LLM-routing / tool-dispatch logic as the bot gateway
    (Telegram, WhatsApp, Web Widget) but calls ai.tool.execute() directly
    instead of going through the /mcp_gateway HTTP loopback, so no MCP API
    key needs to be configured just to use this screen.
    """

    _name = 'mercas.mcp.chat.wizard'
    _description = 'Consulta a la IA (MCP)'

    message = fields.Text(string='Mensaje')
    history_display = fields.Html(string='Conversación', readonly=True, sanitize=False)

    @api.model
    def default_get(self, field_names):
        res = super().default_get(field_names)
        if 'history_display' in field_names:
            res['history_display'] = self._render_history(self._get_conversation())
        return res

    def _get_conversation(self):
        return self.env['ai.bot.conversation'].sudo().get_or_create(
            'web',
            f'backend-{self.env.uid}',
            platform_user_name=self.env.user.name,
        )

    @staticmethod
    def _render_history(conversation):
        rows = []
        for msg in conversation.message_ids.sorted('create_date'):
            if msg.role not in ('user', 'assistant'):
                continue
            who = _('Tú') if msg.role == 'user' else _('IA')
            align = 'right' if msg.role == 'user' else 'left'
            bg = '#e7f0ff' if msg.role == 'user' else '#f1f1f1'
            safe = html.escape(msg.content or '').replace('\n', '<br/>')
            rows.append(
                f'<div style="text-align:{align};margin:6px 0;">'
                f'<div style="display:inline-block;max-width:75%;padding:8px 12px;'
                f'border-radius:8px;background:{bg};text-align:left;">'
                f'<b>{who}</b><br/>{safe}</div></div>'
            )
        return ''.join(rows) or f'<p><i>{_("Escribe un mensaje para empezar la conversación.")}</i></p>'

    def action_send(self):
        self.ensure_one()
        text = (self.message or '').strip()
        if not text:
            return self._reload()

        conversation = self._get_conversation()
        history = conversation.get_recent_messages(limit=10)

        try:
            tool_name, tool_args = LLMRouter(self.env).route(text, history)
        except Exception:
            _logger.exception('mercas_mcp_chat: LLM routing failed, falling back to ask_ai')
            tool_name, tool_args = 'ask_ai', {'prompt': text}

        raw_result = self._call_tool(tool_name, tool_args)

        if tool_name not in _TEXT_TOOLS and not str(raw_result).startswith('[Error]'):
            reply = BotGatewayService(self.env)._humanize(text, tool_name, raw_result)
        else:
            reply = raw_result

        conversation.sudo().add_message('user', text, None)
        conversation.sudo().add_message('assistant', reply, tool_name)

        self.message = False
        self.history_display = self._render_history(conversation)
        return self._reload()

    def action_reset(self):
        """Archive the current conversation and start a fresh one."""
        self.ensure_one()
        self._get_conversation().sudo().write({'active': False})
        self.message = False
        self.history_display = self._render_history(self._get_conversation())
        return self._reload()

    def _call_tool(self, tool_name, tool_args):
        tool = self.env['ai.tool'].sudo().search(
            [('name', '=', tool_name), ('active', '=', True)], limit=1
        )
        if not tool:
            return _('[Error] Herramienta "%s" no encontrada') % tool_name
        try:
            with self.env.cr.savepoint():
                result = tool.execute(tool_args)
        except Exception as exc:
            _logger.warning('mercas_mcp_chat: tool %s failed: %s', tool_name, exc)
            return _('[Error] %s') % exc
        return mcp_utils.dumps(result) if isinstance(result, (dict, list)) else str(result)

    def _reload(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }
