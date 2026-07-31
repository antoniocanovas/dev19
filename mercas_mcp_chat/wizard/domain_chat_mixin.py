import html
import logging

from odoo import _, api, fields, models

from odoo.addons.odoo_mcp_manager.services.bot_gateway_service import LLMRouter

from ..prompts import BASE_BUSINESS_INSTRUCTIONS

_logger = logging.getLogger(__name__)

_OUT_OF_SCOPE_REPLY = 'Sólo puedo responder preguntas de VENTAS, COMPRAS, FACTURACIÓN Y STOCK.'

_DOMAIN_TOOL = {
    'ventas': 'sales_report',
    'compras': 'purchase_report',
    'facturacion': 'invoice_report',
    'stock': 'stock_report',
}

_CLASSIFY_PROMPT = (
    'Classify the user message into exactly one business domain and extract query '
    'parameters. Return ONLY a valid JSON object, no markdown, no explanation:\n'
    '{{"domain": "ventas"|"compras"|"facturacion"|"stock"|"otro", '
    '"partner": "<nombre parcial de cliente/proveedor o null>", '
    '"product": "<nombre parcial o referencia interna (código) de producto, o null, '
    'solo relevante para stock>", '
    '"only_boxes": true|false, '
    '"date_from": "<YYYY-MM-DD o null>", "date_to": "<YYYY-MM-DD o null>", '
    '"group_by": "customer"|"day"|"customer_day"|"product"|"product_day"|"total", '
    '"move_type": "customer"|"vendor"|"all", '
    '"direction": "in"|"out"|"internal"|null}}\n\n'
    'DOMINIOS:\n'
    '- ventas: pedidos de venta (sale.order) a clientes.\n'
    '- compras: pedidos de compra (purchase.order) a proveedores.\n'
    '- facturacion: facturas emitidas o recibidas (account.move).\n'
    '- stock: movimientos o cantidades de productos (stock.move).\n'
    '- otro: cualquier otra cosa que no sea ventas, compras, facturación o stock.\n\n'
    '{business_instructions}'
    '{custom_instructions}'
    'Today is {today}. Resolve relative dates ("hoy", "ayer", "esta semana", "este mes", '
    '"el mes pasado") against it.\n'
    '{history}'
    'User message: "{text}"'
)


class MercasDomainChatMixin(models.AbstractModel):
    """Everything a ventas/compras/facturación/stock chat console needs.

    Single source of truth shared by 'Chat IA' (mercas.mcp.chat.wizard,
    always-visible menu) and 'Consultas IA' (mercas.mcp.domain.chat.wizard,
    debug-only menu — kept only for side-by-side comparison). Both are
    plain ``_inherit`` of this abstract model; a concrete wizard only needs
    to set ``_name``, ``_description`` and ``_conversation_prefix``. Adding
    a new domain means touching this file once, not two.
    """

    _name = 'mercas.mcp.domain.chat.mixin'
    _description = 'Mercas MCP Chat — Domain Classification Mixin'

    #: Prefix for the ai.bot.conversation platform_user_id, so each
    #: concrete wizard keeps its own independent conversation history.
    _conversation_prefix = 'backend'

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
            f'{self._conversation_prefix}-{self.env.uid}',
            platform_user_name=self.env.user.name,
        )

    @staticmethod
    def _render_history(conversation):
        rows = []
        # message_ids arrives pre-sorted 'create_date desc, id desc' (ai.bot.message._order).
        # Two messages created back-to-back in the same request can land on the exact same
        # create_date (second precision), and Python's sort is stable, so sorting by
        # create_date alone would keep them in their pre-existing (newest-first) relative
        # order — i.e. the assistant reply would render above the user question that
        # triggered it. Break ties by id, same as ai.bot.conversation.get_recent_messages().
        ordered = conversation.message_ids.sorted(
            lambda m: (m.create_date or fields.Datetime.now(), m.id)
        )
        for msg in ordered:
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
        return ''.join(rows) or (
            f'<p><i>{_("Pregunta sobre ventas, compras, facturación o stock.")}</i></p>'
        )

    def action_send(self):
        self.ensure_one()
        text = (self.message or '').strip()
        if not text:
            return self._reload()

        conversation = self._get_conversation()
        history = conversation.get_recent_messages(limit=6)

        try:
            parsed = self._classify(text, history)
        except Exception:
            _logger.exception('mercas_mcp_chat: domain classification failed')
            parsed = {'domain': 'otro'}

        domain_key = (parsed.get('domain') or 'otro').strip().lower()
        tool_name = _DOMAIN_TOOL.get(domain_key)

        if not tool_name:
            reply = _OUT_OF_SCOPE_REPLY
        else:
            params = self._build_tool_params(domain_key, parsed)
            reply = self._run_report(tool_name, domain_key, params)

        conversation.sudo().add_message('user', text, None)
        conversation.sudo().add_message('assistant', reply, tool_name or 'out_of_scope')

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

    def _reload(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def _classify(self, text, history):
        provider, model_name = LLMRouter(self.env)._routing_provider()
        convo = '\n'.join(f"{h['role']}: {h['content']}" for h in (history or [])[-4:])
        custom = self.env['ir.config_parameter'].sudo().get_param(
            'mercas_mcp_chat.custom_instructions', ''
        ).strip()
        prompt = _CLASSIFY_PROMPT.format(
            business_instructions=BASE_BUSINESS_INSTRUCTIONS + '\n',
            custom_instructions=(
                f'INSTRUCCIONES PERSONALIZADAS:\n{custom}\n\n' if custom else ''
            ),
            today=fields.Date.context_today(self).isoformat(),
            history=(f'Conversación previa:\n{convo}\n\n' if convo else ''),
            text=text,
        )
        extra = {'json_mode': True} if provider.service == 'ollama' else {}
        raw = provider.chat([{'role': 'user', 'content': prompt}], model=model_name, **extra)
        return LLMRouter._extract_json(raw)

    @staticmethod
    def _build_tool_params(domain_key, parsed):
        date_from = parsed.get('date_from')
        date_to = parsed.get('date_to')
        group_by = (parsed.get('group_by') or '').strip().lower()

        if domain_key == 'ventas':
            allowed = {'customer', 'day', 'customer_day', 'total'}
            return {
                'customer': parsed.get('partner'),
                'date_from': date_from, 'date_to': date_to,
                'group_by': group_by if group_by in allowed else 'customer',
            }
        if domain_key == 'compras':
            allowed = {'customer', 'day', 'customer_day', 'total'}
            return {
                'vendor': parsed.get('partner'),
                'date_from': date_from, 'date_to': date_to,
                'group_by': group_by if group_by in allowed else 'customer',
            }
        if domain_key == 'facturacion':
            allowed = {'customer', 'day', 'customer_day', 'total'}
            return {
                'partner': parsed.get('partner'),
                'date_from': date_from, 'date_to': date_to,
                'group_by': group_by if group_by in allowed else 'customer',
                'move_type': parsed.get('move_type') or 'all',
            }
        if domain_key == 'stock':
            allowed = {'product', 'day', 'product_day', 'total'}
            return {
                'product': parsed.get('product'),
                'only_boxes': bool(parsed.get('only_boxes')),
                'date_from': date_from, 'date_to': date_to,
                'group_by': group_by if group_by in allowed else 'product',
                'direction': parsed.get('direction'),
            }
        return {}

    def _run_report(self, tool_name, domain_key, params):
        tool = self.env['ai.tool'].sudo().search(
            [('name', '=', tool_name), ('active', '=', True)], limit=1
        )
        if not tool:
            return _('[Error] La herramienta "%s" no está instalada.') % tool_name
        try:
            with self.env.cr.savepoint():
                result = tool.execute(params)
        except Exception as exc:
            _logger.warning('mercas_mcp_chat: %s failed: %s', tool_name, exc)
            return _('[Error] %s') % exc
        return self._format_result(domain_key, result)

    @staticmethod
    def _format_result(domain_key, result):
        if domain_key == 'stock':
            rows = sorted(result.get('rows') or [], key=lambda r: r.get('qty', 0), reverse=True)
            uom = (' ' + result['uom'].strip()) if result.get('uom') else ''
            summary = _('Total: %(qty).2f%(uom)s (%(count)s movimientos)') % {
                'qty': result.get('grand_qty', 0.0), 'uom': uom, 'count': result.get('count', 0),
            }
            lines = []
            for row in rows:
                label = ' — '.join(
                    part for part in (row.get('product'), row.get('day')) if part
                ) or _('Total')
                lines.append('• %(label)s: %(qty).2f%(uom)s (%(count)s movimientos)' % {
                    'label': label, 'qty': row.get('qty', 0.0), 'uom': uom,
                    'count': row.get('count', 0),
                })
            text = summary + ('\n\n' + '\n'.join(lines) if lines else '')

            lots = result.get('lots')
            if lots:
                lot_lines = []
                for entry in lots:
                    parts = [entry['lot']]
                    if entry.get('supplier'):
                        parts.append(_('proveedor: %s') % entry['supplier'])
                    parts.append(
                        _('caduca: %s') % entry['expiration']
                        if entry.get('expiration') else _('sin fecha de caducidad')
                    )
                    parts.append('%.2f%s' % (entry.get('qty', 0.0), uom))
                    lot_lines.append('• ' + ' — '.join(parts))
                text += '\n\n' + _('Lotes en stock (por caducidad):') + '\n' + '\n'.join(lot_lines)

            return text

        rows = sorted(result.get('rows') or [], key=lambda r: r.get('amount', 0), reverse=True)
        currency = result.get('currency') or ''
        summary = _('Total: %(total).2f %(currency)s (%(count)s pedidos)') % {
            'total': result.get('grand_amount', 0.0), 'currency': currency,
            'count': result.get('count', 0),
        }
        lines = []
        for row in rows:
            label = ' — '.join(
                part for part in (row.get('partner'), row.get('day')) if part
            ) or _('Total')
            lines.append('• %(label)s: %(amount).2f %(currency)s (%(count)s pedidos)' % {
                'label': label, 'amount': row.get('amount', 0.0), 'currency': currency,
                'count': row.get('count', 0),
            })
        return summary + ('\n\n' + '\n'.join(lines) if lines else '')
