# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json


class DocumentWorkflowAction(models.Model):
    _name = 'document.workflow.action'
    _description = 'Document Workflow Action'
    _order = 'baby_list_item_id asc, item_action_sequence asc, date_logged asc, id asc'
    _rec_name = 'display_name'

    # Computed display name
    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )

    # Core identification fields
    document_type = fields.Selection([
        ('sale_order', 'Sale Order'),
        ('purchase_order', 'Purchase Order'),
        ('invoice_out', 'Customer Invoice'),
        ('invoice_in', 'Vendor Bill'),
        ('picking', 'Stock Transfer'),
        ('pos_order', 'POS Order'),
        ('helpdesk', 'Helpdesk Ticket'),
        ('baby_list', 'Gift List'),
        ('baby_list_item', 'Gift List Item'),
    ], string='Document Type', required=True, index=True)

    document_ref = fields.Char(
        string='Document Reference',
        required=True,
        index=True,
        help='Document reference (e.g., SO001, WH/OUT/00001)'
    )

    res_id = fields.Integer(
        string='Resource ID',
        required=True,
        index=True,
        help='ID of the original record'
    )

    # Action details
    action_type = fields.Selection([
        # State Changes
        ('state_change', 'State Change'),
        ('creation', 'Document Created'),
        ('cancellation', 'Cancelled'),
        
        # Transfers
        ('transfer_warehouse_to_delivery', 'Transfer: Warehouse → Delivery'),
        ('transfer_receipt_to_warehouse', 'Transfer: Receipt → Warehouse'),
        ('transfer_internal', 'Transfer: Internal'),
        ('transfer_pending', 'Transfer: To Pending Delivery'),
        
        # Financial
        ('payment_received', 'Payment Received'),
        ('payment_refunded', 'Payment Refunded'),
        ('wallet_credit', 'Wallet Credit'),
        ('wallet_debit', 'Wallet Debit'),
        ('invoice_posted', 'Invoice Posted'),
        ('invoice_paid', 'Invoice Paid'),
        
        # Operational
        ('order_confirmed', 'Order Confirmed'),
        ('order_sent', 'Order Sent'),
        ('po_sent', 'PO Sent'),
        ('order_received', 'Order Received'),
        ('receipt_validated', 'Receipt Validated'),
        ('internal_transfer_validated', 'Internal Transfer Validated'),
        ('delivery_validated', 'Delivery Validated'),
        ('delivery_delivered', 'Delivery Delivered'),
        ('return_initiated', 'Return Initiated'),
        ('return_completed', 'Return Completed'),
        
        # External API Events
        ('api_shipment_created', 'API: Shipment Created'),
        ('api_shipment_in_transit', 'API: Shipment In Transit'),
        ('api_shipment_delivered', 'API: Shipment Delivered'),
        ('api_shipment_exception', 'API: Shipment Exception'),
        ('api_payment_authorized', 'API: Payment Authorized'),
        ('api_payment_captured', 'API: Payment Captured'),
        ('api_payment_failed', 'API: Payment Failed'),
        
        # System
        ('system_auto_confirm', 'System: Auto Confirmed'),
        ('system_scheduled_task', 'System: Scheduled Task'),
        ('system_workflow_trigger', 'System: Workflow Trigger'),
    ], string='Action Type', required=True, index=True)

    action_source = fields.Selection([
        ('user', 'User Action'),
        ('system', 'System Generated'),
        ('api', 'External API'),
    ], string='Action Source', required=True, index=True)

    # State information
    state_from = fields.Char(
        string='Previous State',
        help='Previous state (null for creation)'
    )

    state_to = fields.Char(
        string='New State',
        help='New state (null for non-state actions)'
    )

    # Timestamp
    date_logged = fields.Datetime(
        string='Date Logged',
        required=True,
        index=True,
        default=fields.Datetime.now,
    )

    # User and partner
    user_id = fields.Many2one(
        'res.users',
        string='User',
        index=True,
        help='User who triggered the action (null for system/api)'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer/Supplier',
        index=True,
        help='Related customer or supplier'
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    # Financial information
    amount_total = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        help='Document amount at time of action'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
    )

    # Notes
    note = fields.Text(
        string='Notes',
        help='Optional notes or description'
    )

    # API information
    api_provider = fields.Char(
        string='API Provider',
        index=True,
        help='External API provider name (e.g., "DHL", "Stripe")'
    )

    api_response_id = fields.Char(
        string='API Response ID',
        help='External tracking or response ID'
    )

    api_webhook_data = fields.Text(
        string='Webhook Data',
        help='Full webhook payload (JSON format, for debugging)'
    )

    # Transfer information
    transfer_type = fields.Selection([
        ('warehouse_to_delivery', 'Warehouse → Delivery'),
        ('receipt_to_warehouse', 'Receipt → Warehouse'),
        ('warehouse_to_pending', 'Warehouse → Pending Delivery'),
        ('pending_to_delivery', 'Pending → Delivery'),
        ('internal', 'Internal Transfer'),
    ], string='Transfer Type', help='For transfer actions')

    # Performance tracking
    duration_seconds = fields.Integer(
        string='Duration (seconds)',
        help='Time taken for action (for performance tracking)'
    )

    # Relations
    related_action_ids = fields.Many2many(
        'document.workflow.action',
        'workflow_action_relation',
        'action_id',
        'related_action_id',
        string='Related Actions',
        help='Related actions (e.g., refund linked to original payment)'
    )

    # Gift List Integration
    baby_list_id = fields.Many2one(
        'baby.list',
        string='Gift List',
        index=True,
        help='Link to gift list (if applicable)',
        ondelete='set null',
    )
    
    baby_list_item_id = fields.Many2one(
        'baby.list.item',
        string='Gift List Item',
        index=True,
        help='Link to gift list item (if applicable)',
        ondelete='set null',  # Don't cascade delete if item is deleted
    )
    
    sequence = fields.Integer(
        string='Item Sequence',
        index=True,
        help='Item ID from gift list item for ordering (uses item.id for unique ordering)',
        default=10,
    )
    
    # Computed field to show item line number (1, 2, 3, etc.) for display
    item_line_number = fields.Integer(
        string='Item Line #',
        compute='_compute_item_line_number',
        store=True,
        help='Line number of the item in the gift list (1st item, 2nd item, etc.)',
    )
    
    @api.depends('baby_list_item_id', 'baby_list_id')
    def _compute_item_line_number(self):
        """Compute line number based on item's position in the list"""
        for record in self:
            if record.baby_list_item_id and record.baby_list_id:
                # Get all items for this list, ordered by id (creation order)
                all_items = self.env['baby.list.item'].search([
                    ('list_id', '=', record.baby_list_id.id),
                ], order='id asc')
                
                # Find position of this item
                for index, item in enumerate(all_items, start=1):
                    if item.id == record.baby_list_item_id.id:
                        record.item_line_number = index
                        break
                else:
                    record.item_line_number = 0
            else:
                record.item_line_number = 0
    
    # Product information from gift list item
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='baby_list_item_id.product_id',
        store=True,
        readonly=True,
        help='Product from gift list item',
    )
    
    # Sequential action number for this gift list item (1st action, 2nd action, etc.)
    item_action_sequence = fields.Integer(
        string='Action #',
        compute='_compute_item_action_sequence',
        store=True,
        help='Sequential number of this action for the gift list item (1st, 2nd, 3rd, etc.)',
    )

    # Archiving
    is_archived = fields.Boolean(
        string='Archived',
        default=False,
        index=True,
        help='Flag for archived records'
    )

    archived_date = fields.Datetime(
        string='Archived Date',
        help='When record was archived'
    )

    # Constraints
    _sql_constraints = [
        ('res_id_document_type_index', 'index(res_id, document_type)', 'btree'),
        ('partner_date_index', 'index(partner_id, date_logged)', 'btree'),
        ('document_type_action_type_index', 'index(document_type, action_type)', 'btree'),
    ]

    @api.depends('document_type', 'document_ref', 'action_type', 'date_logged')
    def _compute_display_name(self):
        for record in self:
            date_str = fields.Datetime.to_string(record.date_logged) if record.date_logged else ''
            record.display_name = f"{record.document_ref} - {dict(record._fields['action_type'].selection).get(record.action_type, record.action_type)} ({date_str})"
    
    @api.depends('baby_list_item_id', 'date_logged')
    def _compute_item_action_sequence(self):
        """Compute sequential action number for each gift list item (1st, 2nd, 3rd, etc.)"""
        for record in self:
            if record.baby_list_item_id and record.id:
                # Find all actions for this item, ordered by date
                all_actions = self.search([
                    ('baby_list_item_id', '=', record.baby_list_item_id.id),
                    ('is_archived', '=', False),
                ], order='date_logged asc, id asc')
                
                # Find the position of this action in the ordered list
                for index, action in enumerate(all_actions, start=1):
                    if action.id == record.id:
                        record.item_action_sequence = index
                        break
                else:
                    record.item_action_sequence = 0
            else:
                record.item_action_sequence = 0
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to recalculate action sequences"""
        records = super().create(vals_list)
        # Recalculate sequences for affected items (if they were linked immediately)
        items_to_recalc = records.filtered('baby_list_item_id').mapped('baby_list_item_id')
        if items_to_recalc:
            self._recalculate_item_sequences(items_to_recalc)
        
        # Also try to link actions that were created without item reference
        # This handles cases where SO was created before item was linked
        for record in records:
            if not record.baby_list_item_id:
                # Try to find item by document reference
                try:
                    if record.document_type == 'sale_order' and record.res_id:
                        item = self.env['baby.list.item'].search([
                            ('sale_order_id', '=', record.res_id)
                        ], limit=1)
                        if not item:
                            # Try via SO line
                            so = self.env['sale.order'].browse(record.res_id)
                            if so.order_line:
                                for line in so.order_line:
                                    item = self.env['baby.list.item'].search([
                                        ('sale_order_line_id', '=', line.id)
                                    ], limit=1)
                                    if item:
                                        break
                        if item:
                            record.write({
                                'baby_list_item_id': item.id,
                                'baby_list_id': item.list_id.id if item.list_id else False,
                                'sequence': item.id,
                            })
                            self._recalculate_item_sequences(item)
                except Exception:
                    pass
        
        return records
    
    def write(self, vals):
        """Override write to recalculate action sequences if item changes"""
        items_to_recalc = self.env['baby.list.item']
        if 'baby_list_item_id' in vals:
            # If item is being changed, recalc for old and new items
            items_to_recalc |= self.filtered('baby_list_item_id').mapped('baby_list_item_id')
            if vals.get('baby_list_item_id'):
                items_to_recalc |= self.env['baby.list.item'].browse(vals['baby_list_item_id'])
        elif 'date_logged' in vals:
            # If date changes, recalc for items
            items_to_recalc |= self.filtered('baby_list_item_id').mapped('baby_list_item_id')
        
        res = super().write(vals)
        
        if items_to_recalc:
            self._recalculate_item_sequences(items_to_recalc)
        
        return res
    
    @api.model
    def _recalculate_item_sequences(self, items):
        """Recalculate action sequences for given gift list items"""
        for item in items:
            # Get all actions for this item, ordered by date
            all_actions = self.search([
                ('baby_list_item_id', '=', item.id),
                ('is_archived', '=', False),
            ], order='date_logged asc, id asc')
            
            # Update sequences directly in database for performance
            for index, action in enumerate(all_actions, start=1):
                # Use SQL update for performance
                self.env.cr.execute(
                    "UPDATE document_workflow_action SET item_action_sequence = %s WHERE id = %s",
                    (index, action.id)
                )
        
        # Invalidate cache
        self.env.invalidate_all()

    def open_document(self):
        """Open the related document"""
        self.ensure_one()
        model_name = self._get_model_name()
        if not model_name:
            raise UserError(_('Cannot determine model for document type: %s') % self.document_type)
        
        return {
            'type': 'ir.actions.act_window',
            'name': self.document_ref,
            'res_model': model_name,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_model_name(self):
        """Get model name from document_type"""
        model_map = {
            'sale_order': 'sale.order',
            'purchase_order': 'purchase.order',
            'invoice_out': 'account.move',
            'invoice_in': 'account.move',
            'picking': 'stock.picking',
            'pos_order': 'pos.order',
            'helpdesk': 'helpdesk.ticket',
            'baby_list': 'baby.list',
            'baby_list_item': 'baby.list.item',
        }
        return model_map.get(self.document_type, False)

    @api.model
    def get_action_timeline(self, baby_list_item_id):
        """Get chronological action history for a gift list item"""
        actions = self.search([
            ('baby_list_item_id', '=', baby_list_item_id),
            ('is_archived', '=', False),
        ], order='date_logged asc')
        
        timeline = []
        for action in actions:
            timeline.append({
                'date': action.date_logged,
                'action': action.action_type,
                'description': action.note or f"{dict(action._fields['action_type'].selection).get(action.action_type, action.action_type)} on {action.document_ref}",
                'source': action.action_source,
                'document': action.document_ref,
                'document_type': action.document_type,
            })
        
        return timeline

