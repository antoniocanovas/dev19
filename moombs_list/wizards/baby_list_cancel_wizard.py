# -*- coding: utf-8 -*-
"""
Cancel Item Wizard
==================

Wizard for cancelling baby.list.item with reason selection.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BabyListCancelWizard(models.TransientModel):
    _name = 'baby.list.cancel.wizard'
    _description = 'Cancel Item Wizard'

    item_id = fields.Many2one(
        'baby.list.item',
        string='Item',
        required=True,
    )

    product_name = fields.Char(
        related='item_id.product_id.name',
        string='Product',
    )

    cancel_reason = fields.Selection(
        selection=[
            ('opinion', 'Change of mind'),
            ('duplicate', 'Duplicate line'),
            ('unavailable', 'Product unavailable'),
            ('price', 'Incorrect price'),
            ('replaced', 'Replaced by another'),
            ('error', 'Error when adding'),
            ('other', 'Other'),
        ],
        string='Reason',
        required=True,
    )

    cancel_reason_detail = fields.Char(
        string='Detail',
        help='Required when reason is Other',
    )

    @api.constrains('cancel_reason', 'cancel_reason_detail')
    def _check_detail_required(self):
        for rec in self:
            if rec.cancel_reason == 'other' and not rec.cancel_reason_detail:
                raise UserError(_("Please provide detail for 'Other' reason."))

    def action_confirm(self):
        """Cancel the item."""
        self.ensure_one()

        if self.item_id.state in ('paid', 'delivered'):
            raise UserError(_("Cannot cancel %s item.") % self.item_id.state)

        self.item_id.write({
            'is_cancelled': True,
            'date_cancelled': fields.Datetime.now(),
            'cancel_reason': self.cancel_reason,
            'cancel_reason_detail': self.cancel_reason_detail,
        })
        # CRITICAL: Force state recomputation after write (state is computed from is_cancelled)
        self.item_id._compute_state()

        return {'type': 'ir.actions.act_window_close'}
