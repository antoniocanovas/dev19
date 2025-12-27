# -*- coding: utf-8 -*-
"""
baby.list Model
=================

Main gift list model for MOOMBS Lists.

Stories: LST-001, LST-002, LST-003, LST-005, LST-006, LST-007, LST-008
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta


class BabyList(models.Model):
    _name = 'baby.list'
    _description = 'Gift List'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expected_date desc, id desc'

    # ═══════════════════════════════════════════════════════════════
    # BASIC FIELDS
    # ═══════════════════════════════════════════════════════════════

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Beneficiary 1',
        required=True,
        tracking=True,
        index=True,
    )

    partner2_id = fields.Many2one(
        'res.partner',
        string='Beneficiary 2',
        tracking=True,
    )

    list_type = fields.Selection(
        selection=[
            ('birth', 'Birth'),
            ('wedding', 'Wedding'),
            ('other', 'Other'),
        ],
        string='Type',
        default='birth',
        required=True,
        tracking=True,
    )

    expected_date = fields.Date(
        string='Expected Date',
        required=True,
        tracking=True,
        index=True,
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('completed', 'Completed'),
        ],
        string='Status',
        default='active',
        required=True,
        tracking=True,
        index=True,
    )

    store_id = fields.Many2one(
        'res.partner',
        string='Store',
        domain=[('is_company', '=', True)],
        tracking=True,
    )

    advisor_id = fields.Many2one(
        'res.users',
        string='Advisor',
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # RELATIONAL FIELDS
    # ═══════════════════════════════════════════════════════════════

    item_ids = fields.One2many(
        'baby.list.item',
        'list_id',
        string='Items',
    )

    wallet_id = fields.Many2one(
        'loyalty.card',
        string='Wallet',
        copy=False,
    )

    family_ids = fields.One2many(
        'baby.list.family',
        'list_id',
        string='Family Members',
    )

    # ═══════════════════════════════════════════════════════════════
    # COMPUTED FIELDS - COUNTS
    # ═══════════════════════════════════════════════════════════════

    item_count = fields.Integer(
        string='Items',
        compute='_compute_item_count',
        store=True,
    )

    family_count = fields.Integer(
        string='Family Members',
        compute='_compute_family_count',
        store=True,
    )

    delivery_count = fields.Integer(
        string='Deliveries',
        compute='_compute_delivery_count',
    )

    transaction_count = fields.Integer(
        string='Transactions',
        compute='_compute_transaction_count',
    )

    # ═══════════════════════════════════════════════════════════════
    # COMPUTED FIELDS - AMOUNTS
    # ═══════════════════════════════════════════════════════════════

    amount_total = fields.Monetary(
        string='Total Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    amount_ordered = fields.Monetary(
        string='Ordered Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    amount_paid = fields.Monetary(
        string='Paid Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    amount_delivered = fields.Monetary(
        string='Delivered Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    # ═══════════════════════════════════════════════════════════════
    # COMPUTED FIELDS - WALLET
    # ═══════════════════════════════════════════════════════════════

    wallet_balance = fields.Monetary(
        string='Wallet Balance',
        compute='_compute_wallet',
        currency_field='currency_id',
    )

    wallet_committed = fields.Monetary(
        string='Committed',
        compute='_compute_wallet',
        currency_field='currency_id',
        help='25% of ordered items price',
    )

    wallet_available = fields.Monetary(
        string='Available',
        compute='_compute_wallet',
        currency_field='currency_id',
        help='Balance minus committed',
    )

    # ═══════════════════════════════════════════════════════════════
    # COMPUTED FIELDS - PROGRESS (LST-003)
    # ═══════════════════════════════════════════════════════════════

    weeks_progress = fields.Integer(
        string='Weeks Progress',
        compute='_compute_progress',
        help='Pregnancy weeks (for birth type)',
    )

    weeks_total = fields.Integer(
        string='Total Weeks',
        compute='_compute_progress',
        default=40,
    )

    days_remaining = fields.Integer(
        string='Days Remaining',
        compute='_compute_progress',
        help='Days until expected date',
    )

    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_progress',
        store=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # SQL CONSTRAINTS
    # ═══════════════════════════════════════════════════════════════

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'List reference must be unique!'),
    ]

    # ═══════════════════════════════════════════════════════════════
    # COMPUTE METHODS
    # ═══════════════════════════════════════════════════════════════

    @api.depends('item_ids')
    def _compute_item_count(self):
        for record in self:
            record.item_count = len(record.item_ids)

    @api.depends('family_ids')
    def _compute_family_count(self):
        for record in self:
            record.family_count = len(record.family_ids)

    def _compute_delivery_count(self):
        for record in self:
            # Epic 5: Use document-based approach (picking_out_id.state == 'done')
            record.delivery_count = len(
                record.item_ids.filtered(lambda i: i.picking_out_id and i.picking_out_id.state == 'done')
            )

    def _compute_transaction_count(self):
        """Count wallet transactions for this list."""
        for record in self:
            if record.wallet_id:
                # Count loyalty history entries for this wallet
                record.transaction_count = self.env['loyalty.history'].search_count([
                    ('card_id', '=', record.wallet_id.id),
                ])
            else:
                record.transaction_count = 0

    @api.depends('item_ids.price_final', 'item_ids.state')
    def _compute_amounts(self):
        for record in self:
            items = record.item_ids
            record.amount_total = sum(items.mapped('price_final'))
            record.amount_ordered = sum(
                items.filtered(
                    lambda i: i.state in ('ordered', 'reserved', 'paid', 'delivered')
                ).mapped('price_final')
            )
            record.amount_paid = sum(
                items.filtered(
                    lambda i: i.state in ('paid', 'delivered')
                ).mapped('price_final')
            )
            record.amount_delivered = sum(
                items.filtered(
                    lambda i: i.state == 'delivered'
                ).mapped('price_final')
            )

    @api.depends('wallet_id', 'wallet_id.points', 'item_ids.price_final', 'item_ids.state')
    def _compute_wallet(self):
        """Compute wallet balance and availability (LST-008).

        For multiple lists sharing the same wallet (same beneficiary),
        the committed amount includes ordered items from ALL lists.
        """
        for record in self:
            balance = record.wallet_id.points if record.wallet_id else 0.0

            # LST-008: Calculate committed across ALL lists sharing this wallet
            if record.wallet_id:
                # Find all lists sharing this wallet
                sibling_lists = self.search([
                    ('wallet_id', '=', record.wallet_id.id),
                    ('state', 'in', ('active', 'inactive')),  # Not completed
                ])
                # Sum ordered items from all sibling lists
                all_ordered_items = sibling_lists.mapped('item_ids').filtered(
                    lambda i: i.state in ('ordered', 'reserved')
                )
                committed = sum(all_ordered_items.mapped('price_final')) * 0.25
            else:
                committed = 0.0

            record.wallet_balance = balance
            record.wallet_committed = committed
            record.wallet_available = balance - committed

    @api.depends('expected_date', 'list_type')
    def _compute_progress(self):
        today = date.today()
        for record in self:
            if not record.expected_date:
                record.weeks_progress = 0
                record.weeks_total = 40
                record.days_remaining = 0
                record.is_overdue = False
                continue

            days_until = (record.expected_date - today).days
            record.days_remaining = max(0, days_until)
            record.is_overdue = days_until < 0

            if record.list_type == 'birth':
                # Pregnancy is ~40 weeks (280 days)
                record.weeks_total = 40
                # Calculate weeks elapsed (assuming 40 weeks before expected date)
                days_elapsed = 280 - days_until
                weeks_elapsed = max(0, min(40, days_elapsed // 7))
                record.weeks_progress = weeks_elapsed
            else:
                record.weeks_total = 0
                record.weeks_progress = 0

    # ═══════════════════════════════════════════════════════════════
    # ONCHANGE METHODS
    # ═══════════════════════════════════════════════════════════════

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Auto-select or create wallet when beneficiary is selected."""
        if self.partner_id and not self.wallet_id:
            # Check if partner already has a wallet
            LoyaltyCard = self.env['loyalty.card']
            existing_wallet = LoyaltyCard.search([
                ('partner_id', '=', self.partner_id.id),
            ], limit=1)

            if existing_wallet:
                self.wallet_id = existing_wallet
            else:
                # Auto-create wallet with fixed name "Wishlist Wallet Moombs"
                # The _create_wallet() method will be called on save, but we can trigger it here too
                # For onchange, we'll just set a flag or let write() handle it
                pass  # Wallet creation will happen in write() or create()

    # ═══════════════════════════════════════════════════════════════
    # CRUD OVERRIDES
    # ═══════════════════════════════════════════════════════════════

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Generate sequence if not provided
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('baby.list') or _('New')

        records = super().create(vals_list)

        for record in records:
            # Create wallet for beneficiary (LST-001)
            record._create_wallet()

        return records

    def write(self, vals):
        """Override write to enforce state constraints (LST-005).

        Prevents modifications to inactive/completed lists except for
        state changes and allowed administrative fields.
        Also auto-selects/creates wallet when beneficiary changes.
        """
        # Fields that can always be modified (administrative)
        always_allowed = {
            'state',
            'message_main_attachment_id',
            'message_follower_ids',
            'activity_ids',
        }

        # Check if trying to modify restricted fields on inactive/completed list
        restricted_fields = set(vals.keys()) - always_allowed
        if restricted_fields:
            for record in self:
                if record.state in ('inactive', 'completed'):
                    raise UserError(
                        _("Cannot modify %s list. Reactivate it first.") % record.state
                    )

        # Auto-select/create wallet when beneficiary changes
        if 'partner_id' in vals and vals['partner_id']:
            for record in self:
                if not record.wallet_id or record.wallet_id.partner_id.id != vals['partner_id']:
                    # Temporarily set partner_id to check for existing wallet
                    temp_partner_id = vals['partner_id']
                    LoyaltyCard = self.env['loyalty.card']
                    existing_wallet = LoyaltyCard.search([
                        ('partner_id', '=', temp_partner_id),
                    ], limit=1)

                    if existing_wallet:
                        vals['wallet_id'] = existing_wallet.id
                    else:
                        # Will be created after write via _create_wallet()
                        pass

        res = super().write(vals)

        # Create wallet if partner_id changed and no wallet exists
        if 'partner_id' in vals:
            for record in self:
                if record.partner_id and not record.wallet_id:
                    record._create_wallet()

        return res

    # ═══════════════════════════════════════════════════════════════
    # ACTION METHODS
    # ═══════════════════════════════════════════════════════════════

    def action_activate(self):
        """Activate the list (LST-006).

        Reactivates an inactive list. Cannot reactivate completed lists.
        """
        for record in self:
            if record.state == 'completed':
                raise UserError(_("Cannot reactivate a completed list."))
            if record.state == 'inactive':
                record.state = 'active'
        return True

    def action_deactivate(self):
        """Deactivate the list (LST-005).

        Temporarily pauses list operations. Cannot deactivate completed lists.
        """
        for record in self:
            if record.state == 'completed':
                raise UserError(_("Cannot deactivate a completed list."))
            if record.state == 'active':
                record.state = 'inactive'
        return True

    def action_complete(self):
        """Complete/close the list (LST-007).

        Opens confirmation wizard if there are pending items.
        """
        self.ensure_one()
        # Check for pending items
        pending_items = self.item_ids.filtered(
            lambda i: i.state in ('ordered', 'reserved')
        )
        if pending_items:
            # Open confirmation wizard
            return {
                'type': 'ir.actions.act_window',
                'name': _('Complete List'),
                'res_model': 'baby.list.complete.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_list_id': self.id,
                    'default_pending_count': len(pending_items),
                    'default_pending_amount': sum(pending_items.mapped('price_final')),
                },
            }
        # No pending items, complete directly
        self._action_complete_confirmed()
        return True

    def _action_complete_confirmed(self):
        """Internal method to complete the list."""
        self.ensure_one()
        self.state = 'completed'
        self.message_post(
            body=_("List completed by %s.") % self.env.user.name,
            message_type='notification',
        )

    def action_view_items(self):
        """Open items list view."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('List Items'),
            'res_model': 'baby.list.item',
            'view_mode': 'tree,form',
            'domain': [('list_id', '=', self.id)],
            'context': {'default_list_id': self.id},
        }

    def action_view_wallet(self):
        """Open wallet transactions modal (LST-100)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Wallet Transactions'),
            'res_model': 'baby.list.wallet.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_list_id': self.id},
        }

    def action_view_family(self):
        """Open family modal (LST-090)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Family Members'),
            'res_model': 'baby.list.family',
            'view_mode': 'list,form',
            'domain': [('list_id', '=', self.id)],
            'context': {'default_list_id': self.id},
            'target': 'new',
        }

    def action_view_deliveries(self):
        """Open deliveries modal (LST-092)."""
        self.ensure_one()
        # Epic 5: Use document-based approach (picking_out_id.state == 'done')
        delivered_items = self.item_ids.filtered(lambda i: i.picking_out_id and i.picking_out_id.state == 'done')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Deliveries'),
            'res_model': 'baby.list.item',
            'view_mode': 'tree',
            'domain': [('id', 'in', delivered_items.ids)],
            'target': 'new',
        }

    def action_view_info(self):
        """Open list info popup (LST-002)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('List Information'),
            'res_model': 'baby.list.info.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_list_id': self.id},
        }

    # ═══════════════════════════════════════════════════════════════
    # PRIVATE METHODS
    # ═══════════════════════════════════════════════════════════════

    def _create_wallet(self):
        """Create or link eWallet for beneficiary (LST-001)."""
        self.ensure_one()
        if self.wallet_id:
            return self.wallet_id

        # Check if partner already has a wallet
        LoyaltyCard = self.env['loyalty.card']
        existing_wallet = LoyaltyCard.search([
            ('partner_id', '=', self.partner_id.id),
        ], limit=1)

        if existing_wallet:
            self.wallet_id = existing_wallet
        else:
            # Get wallet program from Sales Settings (company-level)
            LoyaltyProgram = self.env['loyalty.program']
            company = self.company_id or self.env.company
            wallet_program_id = self.env['ir.config_parameter'].sudo().get_param(
                f'moombs_list.gift_list_wallet_program_id.{company.id}'
            )
            
            if wallet_program_id:
                # Use the configured wallet program
                program = LoyaltyProgram.browse(int(wallet_program_id))
                if not program.exists() or program.program_type != 'ewallet' or not program.active:
                    # Fallback to default behavior if configured program is invalid
                    program = self._get_default_wallet_program()
            else:
                # Fallback to default behavior if no setting configured
                program = self._get_default_wallet_program()

            # Create wallet card (name will be auto-generated by Odoo)
            wallet = LoyaltyCard.create({
                'partner_id': self.partner_id.id,
                'program_id': program.id,
                'points': 0,
            })
            self.wallet_id = wallet

        return self.wallet_id

    def _get_default_wallet_program(self):
        """Get or create default wallet program (fallback when setting not configured)."""
        LoyaltyProgram = self.env['loyalty.program']
        program = LoyaltyProgram.search([
            ('name', '=', 'Wishlist Wallet Moombs'),
        ], limit=1)

        if not program:
            # Create default eWallet program if it doesn't exist
            report_action = self.env.ref('moombs_list.action_report_wallet_receipt', raise_if_not_found=False)
            program_vals = {
                'name': 'Wishlist Wallet Moombs',
                'program_type': 'ewallet',
                'trigger': 'auto',
                'applies_on': 'both',
            }
            # Link print report if available
            if report_action:
                program_vals['pos_report_id'] = report_action.id
            program = LoyaltyProgram.create(program_vals)
        else:
            # Update existing program to include report if missing
            if not program.pos_report_id:
                report_action = self.env.ref('moombs_list.action_report_wallet_receipt', raise_if_not_found=False)
                if report_action:
                    program.pos_report_id = report_action.id

        return program

    # ═══════════════════════════════════════════════════════════════
    # NAME SEARCH (LST-004)
    # ═══════════════════════════════════════════════════════════════

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None):
        """Extended search by name, phone, or reference."""
        domain = domain or []

        if name:
            # Search in reference, partner name, or phone
            domain = ['|', '|', '|',
                ('name', operator, name),
                ('partner_id.name', operator, name),
                ('partner_id.phone', operator, name),
                ('partner_id.mobile', operator, name),
            ] + domain

        return self._search(domain, limit=limit, order=order)
