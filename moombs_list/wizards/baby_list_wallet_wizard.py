# -*- coding: utf-8 -*-
"""
Wallet Transactions Wizard (LST-100)
====================================

Displays wallet balance and transaction history for a gift list.
"""

from odoo import api, fields, models, _


class BabyListWalletWizard(models.TransientModel):
    _name = 'baby.list.wallet.wizard'
    _description = 'Wallet Transactions Wizard'

    # ═══════════════════════════════════════════════════════════════
    # FIELDS
    # ═══════════════════════════════════════════════════════════════

    list_id = fields.Many2one(
        'baby.list',
        string='Gift List',
        required=True,
        ondelete='cascade',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='list_id.currency_id',
    )

    # Wallet info (readonly)
    wallet_id = fields.Many2one(
        'loyalty.card',
        string='Wallet',
        related='list_id.wallet_id',
    )

    wallet_balance = fields.Monetary(
        string='Balance',
        related='list_id.wallet_balance',
        currency_field='currency_id',
    )

    wallet_committed = fields.Monetary(
        string='Committed (25%)',
        related='list_id.wallet_committed',
        currency_field='currency_id',
    )

    wallet_available = fields.Monetary(
        string='Available',
        related='list_id.wallet_available',
        currency_field='currency_id',
    )

    # Transaction history (POS orders linked to this list)
    transaction_ids = fields.Many2many(
        'pos.order',
        string='Transactions',
        compute='_compute_transactions',
    )

    # Selected transaction for printing
    transaction_id = fields.Many2one(
        'pos.order',
        string='Selected Transaction',
        help='Select a transaction to print receipt',
    )

    # ═══════════════════════════════════════════════════════════════
    # COMPUTE METHODS
    # ═══════════════════════════════════════════════════════════════

    @api.depends('list_id', 'wallet_id')
    def _compute_transactions(self):
        """Load POS orders linked to this baby list."""
        for record in self:
            if not record.list_id:
                record.transaction_ids = False
                continue

            # Find POS orders linked to this list via:
            # 1. Direct link via baby_list_item_ids
            # 2. Via sale orders linked to baby list items
            pos_orders = self.env['pos.order']
            
            # Method 1: Find via baby list items
            items = self.env['baby.list.item'].search([
                ('list_id', '=', record.list_id.id),
            ])
            
            # Get pos orders from items (downpayment and final payment)
            pos_order_ids = items.mapped('pos_downpayment_id').ids
            pos_order_ids.extend(items.mapped('pos_order_id').ids)
            
            if pos_order_ids:
                pos_orders = self.env['pos.order'].browse(list(set(pos_order_ids)))
            
            # Method 2: Find via sale orders (if pos_sale module active)
            # Note: In Odoo 19, pos.order doesn't have sale_order_ids field directly
            # Instead, we check pos.order.line.sale_order_origin_id
            sale_orders = items.mapped('sale_order_id')
            if sale_orders:
                # Search for POS orders via lines with sale_order_origin_id
                pos_lines = self.env['pos.order.line'].search([
                    ('sale_order_origin_id', 'in', sale_orders.ids),
                ])
                pos_orders_via_so = pos_lines.mapped('order_id').filtered(
                    lambda o: o.state == 'paid'
                )
                pos_orders |= pos_orders_via_so
            
            # Order by date descending, limit to 50
            record.transaction_ids = pos_orders.sorted('date_order', reverse=True)[:50]

    # ═══════════════════════════════════════════════════════════════
    # ACTION METHODS
    # ═══════════════════════════════════════════════════════════════

    def action_print_receipt(self):
        """Print receipt for selected transaction (LST-103)."""
        self.ensure_one()
        if not self.transaction_id:
            raise UserError(_("Please select a transaction to print."))
        
        return self.env.ref('moombs_list.action_report_wallet_receipt').report_action(self.transaction_id)
