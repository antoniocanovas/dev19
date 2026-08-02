from odoo import models


class AiDomainChatWizard(models.TransientModel):
    """Standalone twin of 'Chat IA' (ai_chat_wizard.py), kept only for
    debugging/comparison — its menu entry is debug-only
    (groups="base.group_no_one" on mcp_gateway_menu_domain_chat).

    All logic lives in MercasDomainChatMixin (domain_chat_mixin.py); this
    class only picks its own conversation key ('domain-<uid>', separate
    from Chat IA's 'backend-<uid>') so both wizards can be used side by
    side without sharing history.
    """

    _name = 'mercas.mcp.domain.chat.wizard'
    _inherit = ['mercas.mcp.domain.chat.mixin']
    _description = 'Consultas IA (debug — Ventas / Compras / Facturación / Stock)'
    _conversation_prefix = 'domain'
