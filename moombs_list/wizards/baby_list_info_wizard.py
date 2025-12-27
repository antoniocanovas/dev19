# -*- coding: utf-8 -*-
"""
baby.list_info_wizard Model
==============================

Transient wizard to display list information in a popup modal.
Triggered from progress bar click.

Story: LST-002
"""

from odoo import fields, models


class BabyListInfoWizard(models.TransientModel):
    _name = 'baby.list.info.wizard'
    _description = 'List Info Popup'

    # ═══════════════════════════════════════════════════════════════
    # FIELDS
    # ═══════════════════════════════════════════════════════════════

    list_id = fields.Many2one(
        'baby.list',
        string='List',
        readonly=True,
        required=True,
    )

    name = fields.Char(
        string='Reference',
        related='list_id.name',
        readonly=True,
    )

    list_type = fields.Selection(
        string='Type',
        related='list_id.list_type',
        readonly=True,
    )

    expected_date = fields.Date(
        string='Expected Date',
        related='list_id.expected_date',
        readonly=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Beneficiary 1',
        related='list_id.partner_id',
        readonly=True,
    )

    partner_phone = fields.Char(
        string='Phone',
        related='list_id.partner_id.phone',
        readonly=True,
    )

    partner2_id = fields.Many2one(
        'res.partner',
        string='Beneficiary 2',
        related='list_id.partner2_id',
        readonly=True,
    )

    partner2_phone = fields.Char(
        string='Phone',
        related='list_id.partner2_id.phone',
        readonly=True,
    )

    weeks_progress = fields.Integer(
        string='Weeks Progress',
        related='list_id.weeks_progress',
        readonly=True,
    )

    weeks_total = fields.Integer(
        string='Total Weeks',
        related='list_id.weeks_total',
        readonly=True,
    )

    days_remaining = fields.Integer(
        string='Days Remaining',
        related='list_id.days_remaining',
        readonly=True,
    )

    is_overdue = fields.Boolean(
        string='Overdue',
        related='list_id.is_overdue',
        readonly=True,
    )
