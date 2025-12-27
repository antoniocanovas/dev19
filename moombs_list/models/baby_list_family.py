# -*- coding: utf-8 -*-
"""
baby.list_family Model
========================

Family member tracking for gift lists.

Stories: LST-090, LST-091
"""

from odoo import api, fields, models, _


class BabyListFamily(models.Model):
    _name = 'baby.list.family'
    _description = 'Gift List Family Member'
    _order = 'amount_contributed desc, id'

    # ═══════════════════════════════════════════════════════════════
    # BASIC FIELDS
    # ═══════════════════════════════════════════════════════════════

    list_id = fields.Many2one(
        'baby.list',
        string='List',
        required=True,
        ondelete='cascade',
        index=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Family Member',
        required=True,
    )

    relation = fields.Selection(
        selection=[
            ('grandmother', 'Grandmother'),
            ('grandfather', 'Grandfather'),
            ('uncle', 'Uncle'),
            ('aunt', 'Aunt'),
            ('godmother', 'Godmother'),
            ('godfather', 'Godfather'),
            ('friend', 'Friend'),
            ('other', 'Other'),
        ],
        string='Relation',
        default='other',
    )

    is_invited = fields.Boolean(
        string='Invited',
        default=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ═══════════════════════════════════════════════════════════════

    amount_contributed = fields.Monetary(
        string='Contributed',
        compute='_compute_amount_contributed',
        store=True,
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        related='list_id.currency_id',
        store=True,
        string='Currency',
    )

    # ═══════════════════════════════════════════════════════════════
    # COMPUTE METHODS
    # ═══════════════════════════════════════════════════════════════

    @api.depends('list_id.item_ids.paid_by_id', 'list_id.item_ids.price_final')
    def _compute_amount_contributed(self):
        """Calculate total contribution from wallet transactions."""
        for record in self:
            # Sum items paid by this family member
            paid_items = record.list_id.item_ids.filtered(
                lambda i: i.paid_by_id == record.partner_id and i.state in ('paid', 'delivered')
            )
            record.amount_contributed = sum(paid_items.mapped('price_final'))
