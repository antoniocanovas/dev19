from odoo import models


class AiTool(models.Model):
    """Deterministic built-in report tools: plain read_group aggregations with
    real figures (amount_total / quantity), instead of relying on the LLM to
    compute totals from a raw record dump — which it cannot do reliably,
    since search_records never even exposes financial fields to it."""

    _inherit = 'ai.tool'

    def _execute_builtin(self, parameters):
        handler = {
            'sales_report': self._builtin_sales_report,
            'purchase_report': self._builtin_purchase_report,
            'invoice_report': self._builtin_invoice_report,
            'stock_report': self._builtin_stock_report,
        }.get(self.name)
        if handler:
            return handler(parameters)
        return super()._execute_builtin(parameters)

    # ── Shared helpers ──────────────────────────────────────────────────────

    def _partner_domain(self, name, partner_field='partner_id'):
        value = (name or '').strip()
        if not value:
            return []
        partner = self.env['res.partner'].sudo().search([('name', 'ilike', value)], limit=1)
        if partner:
            return [(partner_field, '=', partner.id)]
        return [(f'{partner_field}.name', 'ilike', value)]

    def _date_domain(self, parameters, field):
        domain = []
        date_from = (parameters.get('date_from') or '').strip()
        date_to = (parameters.get('date_to') or '').strip()
        if date_from:
            domain.append((field, '>=', date_from))
        if date_to:
            domain.append((field, '<=', date_to))
        return domain

    def _read_group_amount(self, records, domain, date_field, group_by, partner_field):
        """Group *records* by partner and/or day, summing amount_total."""
        groupby_fields = []
        if group_by in ('customer', 'customer_day'):
            groupby_fields.append(partner_field)
        if group_by in ('day', 'customer_day'):
            groupby_fields.append(f'{date_field}:day')

        data = records.formatted_read_group(
            domain, groupby=groupby_fields, aggregates=['amount_total:sum', '__count']
        )
        rows = []
        grand_amount = 0.0
        count = 0
        for row in data:
            amount = round(row.get('amount_total:sum') or 0.0, 2)
            n = row.get('__count', 0)
            grand_amount += amount
            count += n
            entry = {'count': n, 'amount': amount}
            partner = row.get(partner_field)
            if partner:
                entry['partner'] = partner[1]
            day = row.get(f'{date_field}:day')
            if day:
                entry['day'] = day[1]
            rows.append(entry)
        return rows, round(grand_amount, 2), count

    # ── Ventas ──────────────────────────────────────────────────────────────

    def _builtin_sales_report(self, parameters):
        domain = self._partner_domain(parameters.get('customer')) + \
            self._date_domain(parameters, 'date_order')
        group_by = (parameters.get('group_by') or 'customer').strip().lower()
        rows, grand_amount, count = self._read_group_amount(
            self.env['sale.order'].sudo(), domain, 'date_order', group_by, 'partner_id'
        )
        return {
            'rows': rows, 'grand_amount': grand_amount, 'count': count,
            'currency': self.env.company.currency_id.symbol,
        }

    # ── Compras ─────────────────────────────────────────────────────────────

    def _builtin_purchase_report(self, parameters):
        domain = self._partner_domain(parameters.get('vendor')) + \
            self._date_domain(parameters, 'date_order')
        group_by = (parameters.get('group_by') or 'customer').strip().lower()
        rows, grand_amount, count = self._read_group_amount(
            self.env['purchase.order'].sudo(), domain, 'date_order', group_by, 'partner_id'
        )
        return {
            'rows': rows, 'grand_amount': grand_amount, 'count': count,
            'currency': self.env.company.currency_id.symbol,
        }

    # ── Facturación ─────────────────────────────────────────────────────────

    _INVOICE_TYPES = {
        'customer': ['out_invoice', 'out_refund'],
        'vendor': ['in_invoice', 'in_refund'],
        'all': ['out_invoice', 'out_refund', 'in_invoice', 'in_refund'],
    }

    def _builtin_invoice_report(self, parameters):
        move_type = (parameters.get('move_type') or 'all').strip().lower()
        domain = [
            ('move_type', 'in', self._INVOICE_TYPES.get(move_type, self._INVOICE_TYPES['all'])),
            ('state', '=', 'posted'),
        ]
        domain += self._partner_domain(parameters.get('partner')) + \
            self._date_domain(parameters, 'invoice_date')
        group_by = (parameters.get('group_by') or 'customer').strip().lower()
        rows, grand_amount, count = self._read_group_amount(
            self.env['account.move'].sudo(), domain, 'invoice_date', group_by, 'partner_id'
        )
        return {
            'rows': rows, 'grand_amount': grand_amount, 'count': count,
            'currency': self.env.company.currency_id.symbol,
        }

    # ── Stock ───────────────────────────────────────────────────────────────

    _STOCK_DIRECTIONS = {'in': 'incoming', 'incoming': 'incoming',
                          'out': 'outgoing', 'outgoing': 'outgoing',
                          'internal': 'internal'}

    def _builtin_stock_report(self, parameters):
        stock_move = self.env['stock.move'].sudo()
        domain = [('state', '=', 'done')]

        product = (parameters.get('product') or '').strip()
        if product:
            domain.append(('product_id.name', 'ilike', product))
        if parameters.get('only_boxes'):
            domain.append(('product_id.is_box', '=', True))

        direction = self._STOCK_DIRECTIONS.get((parameters.get('direction') or '').strip().lower())
        if direction:
            domain.append(('picking_type_id.code', '=', direction))

        domain += self._date_domain(parameters, 'date')

        group_by = (parameters.get('group_by') or 'product').strip().lower()
        groupby_fields = []
        if group_by in ('product', 'product_day'):
            groupby_fields.append('product_id')
        if group_by in ('day', 'product_day'):
            groupby_fields.append('date:day')

        data = stock_move.formatted_read_group(
            domain, groupby=groupby_fields, aggregates=['quantity:sum', '__count']
        )
        rows = []
        grand_qty = 0.0
        count = 0
        for row in data:
            qty = round(row.get('quantity:sum') or 0.0, 2)
            n = row.get('__count', 0)
            grand_qty += qty
            count += n
            entry = {'count': n, 'qty': qty}
            if row.get('product_id'):
                entry['product'] = row['product_id'][1]
            day = row.get('date:day')
            if day:
                entry['day'] = day[1]
            rows.append(entry)

        uom = ''
        if product:
            prod = self.env['product.product'].sudo().search(
                [('name', 'ilike', product)], limit=1
            )
            uom = prod.uom_id.name if prod else ''

        return {'rows': rows, 'grand_qty': round(grand_qty, 2), 'count': count, 'uom': uom}
