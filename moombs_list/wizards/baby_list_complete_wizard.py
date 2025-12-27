# -*- coding: utf-8 -*-
"""
baby.list.complete.wizard Model
================================

Transient wizard to confirm list completion when pending items exist.

Story: LST-007
"""

from odoo import api, fields, models, _


class BabyListCompleteWizard(models.TransientModel):
    _name = 'baby.list.complete.wizard'
    _description = 'Complete List Confirmation'

    # ═══════════════════════════════════════════════════════════════
    # FIELDS
    # ═══════════════════════════════════════════════════════════════

    list_id = fields.Many2one(
        'baby.list',
        string='List',
        required=True,
        readonly=True,
    )

    pending_count = fields.Integer(
        string='Pending Items',
        readonly=True,
    )

    pending_amount = fields.Monetary(
        string='Pending Amount',
        readonly=True,
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='list_id.currency_id',
        readonly=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════

    def action_confirm(self):
        """Confirm completion despite pending items."""
        self.ensure_one()
        self.list_id._action_complete_confirmed()
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        """Cancel and return to list."""
        return {'type': 'ir.actions.act_window_close'}
