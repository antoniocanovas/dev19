import html
import logging

from odoo import _, api, fields, models

from odoo.addons.odoo_mcp_manager.services.bot_gateway_service import LLMRouter

from ..prompts import BASE_BUSINESS_INSTRUCTIONS

_logger = logging.getLogger(__name__)

_OUT_OF_SCOPE_REPLY = (
    'Sólo puedo responder preguntas de VENTAS, COMPRAS, FACTURACIÓN, STOCK, '
    'EXISTENCIAS, CAJAS y LOTES.'
)

_DOMAIN_TOOL = {
    'ventas': 'sales_report',
    'compras': 'purchase_report',
    'facturacion': 'invoice_report',
    'stock': 'stock_report',
    'existencias': 'stock_lookup',
    'cajas': 'box_stock_report',
    'lote': 'lot_report',
}

_CLASSIFY_PROMPT = (
    'Classify the user message into exactly one business domain and extract query '
    'parameters. Return ONLY a valid JSON object, no markdown, no explanation:\n'
    '{{"domain": "ventas"|"compras"|"facturacion"|"stock"|"existencias"|"cajas"|"lote"|"otro", '
    '"partner": "<nombre parcial de cliente/proveedor o null>", '
    '"product": "<nombre parcial o referencia interna (código) de producto, o null>", '
    '"lot": "<nombre exacto del lote si se menciona uno, o null, solo relevante para lote>", '
    '"only_boxes": true|false, '
    '"pending": true|false, '
    '"date_from": "<YYYY-MM-DD o null>", "date_to": "<YYYY-MM-DD o null>", '
    '"group_by": "<uno de los valores permitidos para ESE dominio, ver abajo — o null si el '
    'dominio no usa group_by>", '
    '"move_type": "customer"|"vendor"|"all", '
    '"direction": "in"|"out"|"internal"|null}}\n\n'
    'DOMINIOS (con su "group_by" permitido — nunca uses uno que no esté en la lista de ese '
    'dominio):\n'
    '- ventas [group_by permitido: customer, day, customer_day, product, product_day, total — '
    'por defecto customer]: pedidos de venta (sale.order) a clientes. Por defecto totaliza '
    'importes; si preguntan qué PRODUCTOS o el DETALLE de lo vendido (no solo el total), pon '
    '"group_by": "product" o "product_day".\n'
    '- compras [group_by permitido: customer, day, customer_day, product, product_day, total — '
    'por defecto customer]: pedidos de compra (purchase.order) a proveedores. Por defecto '
    'totaliza importes; si preguntan qué PRODUCTOS o el DETALLE de lo comprado (no solo el '
    'total), pon "group_by": "product" o "product_day".\n'
    '- facturacion [group_by permitido: customer, day, customer_day, product, product_day, '
    'detail, total — por defecto customer]: facturas emitidas o recibidas (account.move). Si '
    'pregunta lo que SE DEBE o queda PENDIENTE de pagar (sobre todo a proveedores; también '
    '"deuda de clientes" con move_type=customer), pon "pending": true. Si pregunta qué '
    'PRODUCTOS se facturaron, pon "group_by": "product" o "product_day". Si pregunta el ESTADO '
    'de facturas concretas (pagada, pendiente, parcial...) en vez de un total, pon '
    '"group_by": "detail".\n'
    '- stock [group_by permitido: product, day, product_day, total — por defecto product]: '
    'movimientos de stock (stock.move) en un rango de fechas — entradas, salidas, cuánto ha '
    'entrado/salido/movido de un producto. Nunca uses "customer" ni "customer_day" aquí.\n'
    '- existencias [group_by: no aplica a este dominio, pon siempre null]: cantidad disponible '
    'AHORA MISMO de un producto (no un rango de fechas, no movimientos) — "¿cuánto tenemos de '
    'X?", "¿qué stock queda de X?".\n'
    '- cajas [group_by: no aplica a este dominio, pon siempre null]: cajas/envases en depósito '
    'en el almacén de un cliente o proveedor concreto (no un producto que se llame "caja") — '
    'usa "partner" para el nombre.\n'
    '- lote [group_by: no aplica a este dominio, pon siempre null]: cualquier pregunta sobre '
    'un lote (stock.lot) concreto, o sobre el LISTADO de todos los lotes que hay en stock '
    'ahora mismo — de dónde viene, cuándo entró, caducidad, cuánto queda, a qué clientes se '
    'ha vendido. Usa "lot" para el número de lote si se menciona, "product" si solo se '
    'nombra el producto, o deja ambos en null si piden el listado completo de lotes en '
    'stock.\n'
    '- otro: cualquier otra cosa que no sea ninguno de los anteriores.\n\n'
    'EJEMPLOS (sigue exactamente este formato de respuesta):\n'
    'P: "¿Cuánto le hemos vendido a Bar Pepe este mes?"\n'
    'R: {{"domain":"ventas","partner":"Bar Pepe","product":null,"lot":null,"only_boxes":false,'
    '"pending":false,"date_from":"<primer día del mes actual>","date_to":"<hoy>",'
    '"group_by":"customer","move_type":"all","direction":null}}\n'
    'P: "¿Cuántas cajas tiene Frutas García en su almacén?" (envase retornable, NO un '
    'producto que se llame "caja")\n'
    'R: {{"domain":"cajas","partner":"Frutas García","product":null,"lot":null,'
    '"only_boxes":true,"pending":false,"date_from":null,"date_to":null,"group_by":null,'
    '"move_type":"all","direction":null}}\n'
    'P: "¿Cuánto stock tenemos de Caja1?" (aquí "Caja1" SÍ es el nombre de un producto '
    'concreto del catálogo, no el envase genérico — no es el dominio "cajas")\n'
    'R: {{"domain":"existencias","partner":null,"product":"Caja1","lot":null,'
    '"only_boxes":false,"pending":false,"date_from":null,"date_to":null,"group_by":null,'
    '"move_type":"all","direction":null}}\n'
    'P: "¿Cuánto queda por facturar del lote L00023?"\n'
    'R: {{"domain":"lote","partner":null,"product":null,"lot":"L00023","only_boxes":false,'
    '"pending":false,"date_from":null,"date_to":null,"group_by":null,"move_type":"all",'
    '"direction":null}}\n'
    'P: "¿Cuánto nos deben los clientes?"\n'
    'R: {{"domain":"facturacion","partner":null,"product":null,"lot":null,"only_boxes":false,'
    '"pending":true,"date_from":null,"date_to":null,"group_by":"customer",'
    '"move_type":"customer","direction":null}}\n'
    'P: "¿Qué productos le hemos comprado a Almacenes Ruiz este mes?"\n'
    'R: {{"domain":"compras","partner":"Almacenes Ruiz","product":null,"lot":null,'
    '"only_boxes":false,"pending":false,"date_from":"<primer día del mes actual>",'
    '"date_to":"<hoy>","group_by":"product","move_type":"all","direction":null}}\n'
    'P: "¿Qué tiempo hace hoy?"\n'
    'R: {{"domain":"otro","partner":null,"product":null,"lot":null,"only_boxes":false,'
    '"pending":false,"date_from":null,"date_to":null,"group_by":null,"move_type":"all",'
    '"direction":null}}\n\n'
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
    def _render_history(conversation, extra=None):
        """Render *conversation*'s persisted messages, optionally followed by
        *extra* ad-hoc {'role', 'content'} dicts that are shown but never
        saved — used for the "not authorized" reply, which (same as in
        Discuss) must never touch ai.bot.conversation or cost an LLM call."""
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
        entries = [
            {'role': msg.role, 'content': msg.content}
            for msg in ordered if msg.role in ('user', 'assistant')
        ]
        entries += extra or []
        for entry in entries:
            who = _('Tú') if entry['role'] == 'user' else _('IA')
            align = 'right' if entry['role'] == 'user' else 'left'
            bg = '#e7f0ff' if entry['role'] == 'user' else '#f1f1f1'
            safe = html.escape(entry.get('content') or '').replace('\n', '<br/>')
            rows.append(
                f'<div style="text-align:{align};margin:6px 0;">'
                f'<div style="display:inline-block;max-width:92%;padding:8px 12px;'
                f'border-radius:8px;background:{bg};text-align:left;">'
                f'<b>{who}</b><br/>{safe}</div></div>'
            )
        return ''.join(rows) or (
            f'<p><i>{_("Pregunta sobre ventas, compras, facturación, stock, "
                       "existencias, cajas o lotes.")}</i></p>'
        )

    def action_send(self):
        self.ensure_one()
        text = (self.message or '').strip()
        if not text:
            return self._reload()

        # Same gate as Discuss (chat_ia.group_ai_chat_user) — before this fix
        # the wizard answered anyone with base.group_user regardless of the
        # group, while Discuss already blocked them. Checked *before* ever
        # calling _get_conversation(), so a rejected user never causes an
        # ai.bot.conversation row to be created either — same as
        # chat_ia.ChatIaBot._apply_logic, which checks the group before its
        # own get_or_create(). No LLM call, no history entry, no DB write.
        if not self.env.user.has_group('chat_ia.group_ai_chat_user'):
            self.message = False
            self.history_display = self._render_history(
                self.env['ai.bot.conversation'], extra=[
                    {'role': 'user', 'content': text},
                    {'role': 'assistant', 'content': self.env['chat.ia.bot']._not_authorized_reply()},
                ])
            return self._reload()

        conversation = self._get_conversation()
        history = conversation.get_recent_messages(limit=6)

        try:
            parsed = self._classify(text, history)
        except Exception:
            _logger.exception('mercas_ai: domain classification failed')
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
            'mercas_ai.custom_instructions', ''
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
        # temperature=0: this call classifies + extracts parameters, it never needs
        # creativity, and consistency matters more here than for a free-form reply —
        # the same question asked twice should route to the same domain/params.
        extra = {'temperature': 0}
        if provider.service == 'ollama':
            extra['json_mode'] = True
        raw = provider.chat([{'role': 'user', 'content': prompt}], model=model_name, **extra)
        return LLMRouter._extract_json(raw)

    @staticmethod
    def _build_tool_params(domain_key, parsed):
        date_from = parsed.get('date_from')
        date_to = parsed.get('date_to')
        group_by = (parsed.get('group_by') or '').strip().lower()

        if domain_key == 'ventas':
            allowed = {'customer', 'day', 'customer_day', 'total', 'product', 'product_day'}
            return {
                'customer': parsed.get('partner'),
                'product': parsed.get('product'),
                'date_from': date_from, 'date_to': date_to,
                'group_by': group_by if group_by in allowed else 'customer',
            }
        if domain_key == 'compras':
            allowed = {'customer', 'day', 'customer_day', 'total', 'product', 'product_day'}
            return {
                'vendor': parsed.get('partner'),
                'product': parsed.get('product'),
                'date_from': date_from, 'date_to': date_to,
                'group_by': group_by if group_by in allowed else 'customer',
            }
        if domain_key == 'facturacion':
            allowed = {
                'customer', 'day', 'customer_day', 'total',
                'product', 'product_day', 'detail',
            }
            return {
                'partner': parsed.get('partner'),
                'product': parsed.get('product'),
                'date_from': date_from, 'date_to': date_to,
                'group_by': group_by if group_by in allowed else 'customer',
                'move_type': parsed.get('move_type') or 'all',
                'pending': bool(parsed.get('pending')),
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
        if domain_key == 'existencias':
            return {'product': parsed.get('product')}
        if domain_key == 'cajas':
            return {'partner': parsed.get('partner')}
        if domain_key == 'lote':
            return {'lot': parsed.get('lot'), 'product': parsed.get('product')}
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
            _logger.warning('mercas_ai: %s failed: %s', tool_name, exc)
            return _('[Error] %s') % exc
        return self._format_result(domain_key, result)

    @staticmethod
    def _format_lot_lines(lots, uom_suffix=''):
        """Shared lot listing for 'stock' and 'existencias': lote, proveedor,
        caducidad, cantidad original comprada y cantidad actual en stock —
        every quantity/lot answer must carry both, not just the current qty."""
        lines = []
        for entry in lots:
            parts = [entry['lot']]
            if entry.get('supplier'):
                parts.append(_('proveedor: %s') % entry['supplier'])
            parts.append(
                _('caduca: %s') % entry['expiration']
                if entry.get('expiration') else _('sin fecha de caducidad')
            )
            parts.append(_('original: %(o).2f%(u)s') % {
                'o': entry.get('original', 0.0), 'u': uom_suffix,
            })
            parts.append(_('en stock: %(q).2f%(u)s') % {
                'q': entry.get('qty', 0.0), 'u': uom_suffix,
            })
            lines.append('• ' + ' — '.join(parts))
        return lines

    @staticmethod
    def _format_result(domain_key, result):
        if domain_key == 'cajas':
            if not result.get('found'):
                return _('No encuentro ningún cliente/proveedor que coincida con "%s".') % (
                    result.get('searched') or ''
                )
            qty = result.get('box_qty', 0.0)
            qty_str = str(int(qty)) if qty == int(qty) else '%.2f' % qty
            return _('%(partner)s tiene %(qty)s cajas en su almacén.') % {
                'partner': result['partner'], 'qty': qty_str,
            }

        if domain_key == 'existencias':
            if not result.get('found'):
                return _('No encuentro ningún producto que coincida con "%s".') % (
                    result.get('searched') or ''
                )
            rows = result.get('rows') or []
            # Different sizes/attributes of the same product name often match
            # (e.g. several product.product variants) — most may be at 0
            # while just one holds the actual stock. Hide zero rows once at
            # least one has real quantity, so the reply isn't 8 empty lines
            # for 1 useful one; if everything is 0, show that plainly instead.
            nonzero = [r for r in rows if r.get('qty')]
            shown = nonzero or rows
            lines = ['• %(name)s: %(qty).2f %(uom)s' % row for row in shown]
            if result.get('general'):
                if not shown:
                    return _('No hay ningún producto con existencias ahora mismo.')
                text = _('Productos con existencias (los que más stock tienen primero):') \
                    + '\n' + '\n'.join(lines)
                return text
            text = '\n'.join(lines)
            uoms = {row['uom'] for row in shown}
            if len(shown) > 1 and len(uoms) == 1:
                total = sum(row['qty'] for row in shown)
                text += '\n\n' + _('Total: %(qty).2f %(uom)s') % {
                    'qty': total, 'uom': shown[0]['uom'],
                }

            lots = result.get('lots')
            if lots:
                uom_suffix = (' ' + shown[0]['uom']) if shown else ''
                lot_lines = MercasDomainChatMixin._format_lot_lines(lots, uom_suffix)
                text += '\n\n' + _('Lotes en stock (por caducidad):') + '\n' + '\n'.join(lot_lines)

            return text

        if domain_key == 'lote':
            if not result.get('found'):
                return _('No encuentro ningún lote/producto que coincida con "%s".') % (
                    result.get('searched') or ''
                )
            details = sorted(
                result.get('details') or [],
                key=lambda d: (
                    (d['product_id'][1] if d.get('product_id') else '').lower(),
                    d['name'],
                ),
            )
            blocks = []
            for d in details:
                uom = d.get('uom') or ''
                product_name = d['product_id'][1] if d.get('product_id') else ''
                lines = [
                    _('Lote: %s') % d['name'],
                    _('Producto: %s') % product_name,
                    _('En almacén: %(qty).2f %(uom)s') % {
                        'qty': d.get('product_qty', 0.0), 'uom': uom,
                    },
                ]
                if d.get('origin_country_id'):
                    lines.append(_('País: %s') % d['origin_country_id'][1])
                if d.get('origin_state_id'):
                    lines.append(_('Provincia: %s') % d['origin_state_id'][1])
                if d.get('partner_id'):
                    lines.append(_('Proveedor: %s') % d['partner_id'][1])
                if d.get('entry'):
                    lines.append(_('Entrada: %s') % d['entry'])
                if d.get('expiration_date'):
                    lines.append(_('Caducidad: %s') % d['expiration_date'].strftime('%Y-%m-%d'))
                sales = d.get('sales') or []
                if sales:
                    lines.append(_('Ventas:'))
                    for s in sales:
                        lines.append(
                            '  • %(partner)s: %(qty).2f %(uom)s (%(order)s, %(date)s)' % s
                        )
                blocks.append('\n'.join(lines))
            separator = '\n' + '-' * 30 + '\n'
            return separator.join(blocks)

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
                lot_lines = MercasDomainChatMixin._format_lot_lines(lots, uom)
                text += '\n\n' + _('Lotes en stock (por caducidad):') + '\n' + '\n'.join(lot_lines)

            return text

        if result.get('product_detail'):
            rows = sorted(result.get('rows') or [], key=lambda r: r.get('amount', 0), reverse=True)
            currency = result.get('currency') or ''
            summary = _('Total: %(total).2f %(currency)s (%(count)s líneas)') % {
                'total': result.get('grand_amount', 0.0), 'currency': currency,
                'count': result.get('count', 0),
            }
            lines = []
            for row in rows:
                label = ' — '.join(
                    part for part in (row.get('product'), row.get('day')) if part
                ) or _('Total')
                uom = row.get('uom') or ''
                uom_suffix = (' ' + uom) if uom else ''
                price_suffix = (
                    ' (%(price).2f %(currency)s/%(uom)s)' % {
                        'price': row['unit_price'], 'currency': currency, 'uom': uom,
                    }
                    if row.get('unit_price') and uom else ''
                )
                lines.append('• %(label)s: %(qty).2f%(uom)s — %(amount).2f %(currency)s%(price)s' % {
                    'label': label, 'qty': row.get('qty', 0.0), 'uom': uom_suffix,
                    'amount': row.get('amount', 0.0), 'currency': currency,
                    'price': price_suffix,
                })
                # Cada línea con lote lleva su cantidad original comprada y lo
                # que queda ahora en stock, no solo la cantidad de esta línea.
                if row.get('lot'):
                    lines.append('    ' + _(
                        'Lote %(lot)s — original: %(o).2f%(u)s — en stock: %(s).2f%(u)s'
                    ) % {
                        'lot': row['lot'], 'o': row.get('lot_original', 0.0),
                        's': row.get('lot_stock', 0.0), 'u': uom,
                    })
            return summary + ('\n\n' + '\n'.join(lines) if lines else '')

        if result.get('invoice_detail'):
            rows = result.get('rows') or []
            currency = result.get('currency') or ''
            if not rows:
                return _('No hay facturas que coincidan con esa búsqueda.')
            lines = []
            for row in rows:
                lines.append(_(
                    '• %(name)s — %(partner)s — %(date)s — %(total).2f %(currency)s '
                    '(pendiente: %(residual).2f %(currency)s, %(state)s)'
                ) % {
                    'name': row['name'], 'partner': row['partner'], 'date': row['date'],
                    'total': row['total'], 'residual': row['residual'],
                    'currency': currency, 'state': row['payment_state'],
                })
            return '\n'.join(lines)

        unit = _('facturas') if domain_key == 'facturacion' else _('pedidos')
        label_total = _('Pendiente') if result.get('pending') else _('Total')
        rows = sorted(result.get('rows') or [], key=lambda r: r.get('amount', 0), reverse=True)
        currency = result.get('currency') or ''
        summary = _('%(label)s: %(total).2f %(currency)s (%(count)s %(unit)s)') % {
            'label': label_total, 'total': result.get('grand_amount', 0.0),
            'currency': currency, 'count': result.get('count', 0), 'unit': unit,
        }
        lines = []
        for row in rows:
            label = ' — '.join(
                part for part in (row.get('partner'), row.get('day')) if part
            ) or _('Total')
            lines.append('• %(label)s: %(amount).2f %(currency)s (%(count)s %(unit)s)' % {
                'label': label, 'amount': row.get('amount', 0.0), 'currency': currency,
                'count': row.get('count', 0), 'unit': unit,
            })
        return summary + ('\n\n' + '\n'.join(lines) if lines else '')
