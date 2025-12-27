# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    workflow_action_count = fields.Integer(
        string='Workflow Actions',
        compute='_compute_workflow_action_count',
    )
    
    def _compute_workflow_action_count(self):
        """Compute number of workflow actions for this sale order"""
        for order in self:
            order.workflow_action_count = self.env['document.workflow.action'].search_count([
                ('document_type', '=', 'sale_order'),
                ('res_id', '=', order.id),
                ('is_archived', '=', False),
            ])
    
    def action_view_workflow_actions(self):
        """Open workflow actions for this sale order"""
        self.ensure_one()
        action = self.env.ref('moombs_workflow_manager.action_document_workflow_action').read()[0]
        action['domain'] = [
            ('document_type', '=', 'sale_order'),
            ('res_id', '=', self.id),
        ]
        action['context'] = {
            'default_document_type': 'sale_order',
            'default_document_ref': self.name,
            'default_res_id': self.id,
            'search_default_state_changes': 1,
        }
        return action
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to log creation"""
        records = super().create(vals_list)
        
        # Log creation for each record
        for record in records:
            try:
                # Try to find linked baby.list.item
                baby_list_item_id = False
                baby_list_id = False
                sequence = 10
                try:
                    # Method 1: Check if SO has baby_list_id directly (from moombs_list)
                    if hasattr(record, 'baby_list_id') and record.baby_list_id:
                        baby_list_id = record.baby_list_id.id
                        # Find items from this list that might be linked (check by product match)
                        # CRITICAL: Search for items that are NOT yet linked (sale_order_id = False)
                        # This catches items that were just created and SO is being created for them
                        if record.order_line:
                            for line in record.order_line:
                                # First try: Find item with matching product that's not yet linked
                                item = self.env['baby.list.item'].search([
                                    ('list_id', '=', baby_list_id),
                                    ('product_id', '=', line.product_id.id),
                                    ('sale_order_id', '=', False),  # Not yet linked
                                ], limit=1, order='id desc')  # Get most recent
                                
                                # If not found, try finding by sale_order_line_id (in case it was linked via line)
                                if not item:
                                    item = self.env['baby.list.item'].search([
                                        ('sale_order_line_id', '=', line.id)
                                    ], limit=1)
                                
                                if item:
                                    baby_list_item_id = item.id
                                    sequence = item.id  # Use item ID for unique ordering
                                    break
                    
                    # Method 2: Try to find already linked item (in case it was linked before this runs)
                    if not baby_list_item_id:
                        item = self.env['baby.list.item'].search([
                            ('sale_order_id', '=', record.id)
                        ], limit=1)
                        if not item and record.order_line:
                            # Check via SO lines
                            for line in record.order_line:
                                item = self.env['baby.list.item'].search([
                                    ('sale_order_line_id', '=', line.id)
                                ], limit=1)
                                if item:
                                    break
                        if item:
                            baby_list_item_id = item.id
                            baby_list_id = item.list_id.id if item.list_id else baby_list_id
                            sequence = item.id  # Use item ID for unique ordering
                except Exception as e:
                    _logger.debug("Could not find baby.list.item for sale.order %s: %s", record.name, e)
                
                action_vals = {
                    'document_type': 'sale_order',
                    'document_ref': record.name,
                    'res_id': record.id,
                    'action_type': 'creation',
                    'action_source': 'system',
                    'state_to': record.state,
                    'date_logged': fields.Datetime.now(),
                    'user_id': self.env.uid,
                    'partner_id': record.partner_id.id if record.partner_id else False,
                    'company_id': record.company_id.id,
                    'amount_total': record.amount_total,
                    'currency_id': record.currency_id.id if record.currency_id else False,
                }
                # Add gift list references if found
                if baby_list_item_id:
                    action_vals['baby_list_item_id'] = baby_list_item_id
                if baby_list_id:
                    action_vals['baby_list_id'] = baby_list_id
                if sequence:
                    action_vals['sequence'] = sequence
                
                self.env['document.workflow.action'].create(action_vals)
            except Exception as e:
                _logger.warning("[Workflow] Failed to log sale order creation: %s", str(e))
        
        return records
    
    def write(self, vals):
        """Override write to log state changes"""
        # Capture state before write
        state_before = {}
        if 'state' in vals:
            for record in self:
                state_before[record.id] = record.state
        
        # Execute write
        res = super().write(vals)
        
        # Also update existing workflow actions if item was just linked
        # (This handles cases where SO was created before item was linked)
        # Run on EVERY write to catch linking that happens after creation
        for record in self:
            try:
                # Check if SO has baby_list_id - try to link actions
                if hasattr(record, 'baby_list_id') and record.baby_list_id:
                    # Find unlinked workflow actions for this SO
                    unlinked_actions = self.env['document.workflow.action'].search([
                        ('document_type', '=', 'sale_order'),
                        ('res_id', '=', record.id),
                        ('baby_list_item_id', '=', False),  # Not yet linked
                    ])
                    if unlinked_actions:
                        # Try to find linked item
                        item = self.env['baby.list.item'].search([
                            ('sale_order_id', '=', record.id)
                        ], limit=1)
                        if not item and record.order_line:
                            # Check via SO lines
                            for line in record.order_line:
                                item = self.env['baby.list.item'].search([
                                    ('sale_order_line_id', '=', line.id)
                                ], limit=1)
                                if item:
                                    break
                        # Also try to find by product match if not found
                        if not item and record.order_line:
                            for line in record.order_line:
                                item = self.env['baby.list.item'].search([
                                    ('list_id', '=', record.baby_list_id.id),
                                    ('product_id', '=', line.product_id.id),
                                    ('sale_order_id', '=', False),  # Not yet linked
                                ], limit=1, order='id desc')
                                if item:
                                    break
                        if item:
                            # Update all unlinked actions
                            unlinked_actions.write({
                                'baby_list_item_id': item.id,
                                'baby_list_id': record.baby_list_id.id,
                                'sequence': item.id,  # Use item ID for unique ordering
                            })
                            # Recalculate sequences immediately
                            self.env['document.workflow.action']._recalculate_item_sequences(item)
            except Exception:
                pass
        
        # Log state changes after write
        if 'state' in vals:
            for record in self:
                if record.id in state_before and state_before[record.id] != record.state:
                    try:
                        # Try to find linked baby.list.item
                        baby_list_item_id = False
                        baby_list_id = False
                        sequence = 10
                        try:
                            # Method 1: Check if SO is linked directly to an item
                            item = self.env['baby.list.item'].search([
                                ('sale_order_id', '=', record.id)
                            ], limit=1)
                            if not item and record.order_line:
                                # Method 2: Check via SO lines
                                for line in record.order_line:
                                    item = self.env['baby.list.item'].search([
                                        ('sale_order_line_id', '=', line.id)
                                    ], limit=1)
                                    if item:
                                        break
                            # Method 3: Check if SO has baby_list_id and find item by product match
                            if not item and hasattr(record, 'baby_list_id') and record.baby_list_id and record.order_line:
                                for line in record.order_line:
                                    item = self.env['baby.list.item'].search([
                                        ('list_id', '=', record.baby_list_id.id),
                                        ('product_id', '=', line.product_id.id),
                                        ('sale_order_id', '=', record.id),  # Must be linked now
                                    ], limit=1)
                                    if item:
                                        break
                            if item:
                                baby_list_item_id = item.id
                                baby_list_id = item.list_id.id if item.list_id else False
                                sequence = item.id  # Use item ID for unique ordering
                        except Exception:
                            # moombs_list not installed - skip linking
                            pass
                        
                        action_vals = {
                            'document_type': 'sale_order',
                            'document_ref': record.name,
                            'res_id': record.id,
                            'action_type': 'state_change',
                            'action_source': 'user',
                            'state_from': state_before[record.id],
                            'state_to': record.state,
                            'date_logged': fields.Datetime.now(),
                            'user_id': self.env.uid,
                            'partner_id': record.partner_id.id if record.partner_id else False,
                            'company_id': record.company_id.id,
                            'amount_total': record.amount_total,
                            'currency_id': record.currency_id.id if record.currency_id else False,
                        }
                        # Add gift list references if found
                        if baby_list_item_id:
                            action_vals['baby_list_item_id'] = baby_list_item_id
                        if baby_list_id:
                            action_vals['baby_list_id'] = baby_list_id
                        if sequence:
                            action_vals['sequence'] = sequence
                        
                        self.env['document.workflow.action'].create(action_vals)
                    except Exception as e:
                        _logger.warning("[Workflow] Failed to log sale order state change: %s", str(e))
        
        return res


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    workflow_action_count = fields.Integer(
        string='Workflow Actions',
        compute='_compute_workflow_action_count',
    )
    
    def _compute_workflow_action_count(self):
        """Compute number of workflow actions for this purchase order"""
        for order in self:
            order.workflow_action_count = self.env['document.workflow.action'].search_count([
                ('document_type', '=', 'purchase_order'),
                ('res_id', '=', order.id),
                ('is_archived', '=', False),
            ])
    
    def action_view_workflow_actions(self):
        """Open workflow actions for this purchase order"""
        self.ensure_one()
        action = self.env.ref('moombs_workflow_manager.action_document_workflow_action').read()[0]
        action['domain'] = [
            ('document_type', '=', 'purchase_order'),
            ('res_id', '=', self.id),
        ]
        action['context'] = {
            'default_document_type': 'purchase_order',
            'default_document_ref': self.name,
            'default_res_id': self.id,
            'search_default_state_changes': 1,
        }
        return action
    
    def action_rfq_send(self):
        """Override to log when PO is sent to vendor"""
        res = super().action_rfq_send()
        
        # Log PO sent action
        for record in self:
            try:
                # Try to find linked baby.list.item
                baby_list_item_id = False
                baby_list_id = False
                sequence = 10
                try:
                    item = self.env['baby.list.item'].search([
                        ('purchase_order_id', '=', record.id)
                    ], limit=1)
                    if item:
                        baby_list_item_id = item.id
                        baby_list_id = item.list_id.id if item.list_id else False
                        sequence = item.id  # Use item ID for unique ordering
                except Exception:
                    pass
                
                action_vals = {
                    'document_type': 'purchase_order',
                    'document_ref': record.name,
                    'res_id': record.id,
                    'action_type': 'po_sent',
                    'action_source': 'user',
                    'state_from': 'purchase',  # PO is confirmed before sending
                    'state_to': 'sent',
                    'date_logged': fields.Datetime.now(),
                    'user_id': self.env.uid,
                    'partner_id': record.partner_id.id if record.partner_id else False,
                    'company_id': record.company_id.id,
                    'amount_total': record.amount_total,
                    'currency_id': record.currency_id.id if record.currency_id else False,
                }
                # Add gift list references if found
                if baby_list_item_id:
                    action_vals['baby_list_item_id'] = baby_list_item_id
                if baby_list_id:
                    action_vals['baby_list_id'] = baby_list_id
                if sequence:
                    action_vals['sequence'] = sequence
                
                self.env['document.workflow.action'].create(action_vals)
            except Exception as e:
                _logger.warning("[Workflow] Failed to log PO sent: %s", str(e))
        
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to log creation"""
        records = super().create(vals_list)
        
        # Log creation for each record
        for record in records:
            try:
                # Try to find linked baby.list.item
                baby_list_item_id = False
                baby_list_id = False
                sequence = 10
                try:
                    item = self.env['baby.list.item'].search([
                        ('purchase_order_id', '=', record.id)
                    ], limit=1)
                    if item:
                        baby_list_item_id = item.id
                        baby_list_id = item.list_id.id if item.list_id else False
                        sequence = item.id  # Use item ID for unique ordering
                except Exception:
                    pass
                
                action_vals = {
                    'document_type': 'purchase_order',
                    'document_ref': record.name,
                    'res_id': record.id,
                    'action_type': 'creation',
                    'action_source': 'system',
                    'state_to': record.state,
                    'date_logged': fields.Datetime.now(),
                    'user_id': self.env.uid,
                    'partner_id': record.partner_id.id if record.partner_id else False,
                    'company_id': record.company_id.id,
                    'amount_total': record.amount_total,
                    'currency_id': record.currency_id.id if record.currency_id else False,
                }
                # Add gift list references if found
                if baby_list_item_id:
                    action_vals['baby_list_item_id'] = baby_list_item_id
                if baby_list_id:
                    action_vals['baby_list_id'] = baby_list_id
                if sequence:
                    action_vals['sequence'] = sequence
                
                self.env['document.workflow.action'].create(action_vals)
            except Exception as e:
                _logger.warning("[Workflow] Failed to log purchase order creation: %s", str(e))
        
        return records
    
    def write(self, vals):
        """Override write to log state changes"""
        state_before = {}
        if 'state' in vals:
            for record in self:
                state_before[record.id] = record.state
        
        res = super().write(vals)
        
        if 'state' in vals:
            for record in self:
                if record.id in state_before and state_before[record.id] != record.state:
                    try:
                        # Try to find linked baby.list.item
                        baby_list_item_id = False
                        baby_list_id = False
                        sequence = 10
                        try:
                            item = self.env['baby.list.item'].search([
                                ('purchase_order_id', '=', record.id)
                            ], limit=1)
                            if item:
                                baby_list_item_id = item.id
                                baby_list_id = item.list_id.id if item.list_id else False
                                sequence = item.id  # Use item ID for unique ordering
                        except Exception:
                            pass
                        
                        action_vals = {
                            'document_type': 'purchase_order',
                            'document_ref': record.name,
                            'res_id': record.id,
                            'action_type': 'state_change',
                            'action_source': 'user',
                            'state_from': state_before[record.id],
                            'state_to': record.state,
                            'date_logged': fields.Datetime.now(),
                            'user_id': self.env.uid,
                            'partner_id': record.partner_id.id if record.partner_id else False,
                            'company_id': record.company_id.id,
                            'amount_total': record.amount_total,
                            'currency_id': record.currency_id.id if record.currency_id else False,
                        }
                        # Add gift list references if found
                        if baby_list_item_id:
                            action_vals['baby_list_item_id'] = baby_list_item_id
                        if baby_list_id:
                            action_vals['baby_list_id'] = baby_list_id
                        if sequence:
                            action_vals['sequence'] = sequence
                        
                        self.env['document.workflow.action'].create(action_vals)
                    except Exception as e:
                        _logger.warning("[Workflow] Failed to log purchase order state change: %s", str(e))
        
        return res


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    workflow_action_count = fields.Integer(
        string='Workflow Actions',
        compute='_compute_workflow_action_count',
    )
    
    def _compute_workflow_action_count(self):
        """Compute number of workflow actions for this picking"""
        for picking in self:
            picking.workflow_action_count = self.env['document.workflow.action'].search_count([
                ('document_type', '=', 'picking'),
                ('res_id', '=', picking.id),
                ('is_archived', '=', False),
            ])
    
    def action_view_workflow_actions(self):
        """Open workflow actions for this picking"""
        self.ensure_one()
        action = self.env.ref('moombs_workflow_manager.action_document_workflow_action').read()[0]
        action['domain'] = [
            ('document_type', '=', 'picking'),
            ('res_id', '=', self.id),
        ]
        action['context'] = {
            'default_document_type': 'picking',
            'default_document_ref': self.name,
            'default_res_id': self.id,
            'search_default_state_changes': 1,
        }
        return action
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to log creation"""
        records = super().create(vals_list)
        
        # Log creation for each record
        for record in records:
            try:
                # Try to find linked baby.list.item
                baby_list_item_id = False
                baby_list_id = False
                sequence = 10
                transfer_type = False
                
                try:
                    # Check if picking has baby_list_item_id directly (from moombs_list)
                    if hasattr(record, 'baby_list_item_id') and record.baby_list_item_id:
                        item = record.baby_list_item_id
                        baby_list_item_id = item.id
                        baby_list_id = item.list_id.id if item.list_id else False
                        sequence = item.id  # Use item ID for unique ordering
                        
                        # Determine transfer type based on picking type
                        if record.picking_type_id:
                            picking_code = record.picking_type_id.code
                            if picking_code == 'incoming':
                                transfer_type = 'receipt_to_warehouse'
                            elif picking_code == 'outgoing':
                                transfer_type = 'warehouse_to_delivery'
                            elif picking_code == 'internal':
                                # Check if it's to pending delivery location
                                if record.location_dest_id and 'pending' in record.location_dest_id.name.lower():
                                    transfer_type = 'warehouse_to_pending'
                                else:
                                    transfer_type = 'internal'
                    
                    # If not found, search for items linked to this picking
                    if not baby_list_item_id:
                        item = self.env['baby.list.item'].search([
                            '|', '|',
                            ('picking_out_id', '=', record.id),
                            ('picking_in_id', '=', record.id),
                            ('picking_pending_id', '=', record.id),
                        ], limit=1)
                        
                        if item:
                            baby_list_item_id = item.id
                            baby_list_id = item.list_id.id if item.list_id else False
                            sequence = item.id  # Use item ID for unique ordering
                            
                            # Determine transfer type
                            if record.picking_type_id:
                                picking_code = record.picking_type_id.code
                                if picking_code == 'incoming':
                                    transfer_type = 'receipt_to_warehouse'
                                elif picking_code == 'outgoing':
                                    transfer_type = 'warehouse_to_delivery'
                                elif picking_code == 'internal':
                                    if record.location_dest_id and 'pending' in record.location_dest_id.name.lower():
                                        transfer_type = 'warehouse_to_pending'
                                    else:
                                        transfer_type = 'internal'
                except Exception:
                    pass
                
                # Determine action type based on transfer type
                action_type = 'creation'
                if transfer_type:
                    action_type_map = {
                        'receipt_to_warehouse': 'transfer_receipt_to_warehouse',
                        'warehouse_to_delivery': 'transfer_warehouse_to_delivery',
                        'warehouse_to_pending': 'transfer_pending',
                        'internal': 'transfer_internal',
                    }
                    action_type = action_type_map.get(transfer_type, 'creation')
                
                action_vals = {
                    'document_type': 'picking',
                    'document_ref': record.name,
                    'res_id': record.id,
                    'action_type': action_type,
                    'action_source': 'system',
                    'state_to': record.state if hasattr(record, 'state') else 'draft',
                    'date_logged': fields.Datetime.now(),
                    'user_id': self.env.uid,
                    'partner_id': record.partner_id.id if record.partner_id else False,
                    'company_id': record.company_id.id,
                    'transfer_type': transfer_type if transfer_type else False,
                }
                # Add gift list references if found
                if baby_list_item_id:
                    action_vals['baby_list_item_id'] = baby_list_item_id
                if baby_list_id:
                    action_vals['baby_list_id'] = baby_list_id
                if sequence:
                    action_vals['sequence'] = sequence
                
                self.env['document.workflow.action'].create(action_vals)
            except Exception as e:
                _logger.warning("[Workflow] Failed to log picking creation: %s", str(e))
        
        return records
    
    def write(self, vals):
        """Override write to log state changes"""
        state_before = {}
        if 'state' in vals:
            for record in self:
                state_before[record.id] = record.state
        
        res = super().write(vals)
        
        # Also update existing workflow actions if item was just linked
        # (This handles cases where picking was created before item was linked)
        if not any(k in vals for k in ['state']):
            for record in self:
                try:
                    # Find items linked to this picking
                    items = self.env['baby.list.item'].search([
                        '|', '|',
                        ('picking_out_id', '=', record.id),
                        ('picking_in_id', '=', record.id),
                        ('picking_pending_id', '=', record.id),
                    ])
                    
                    # Also check if picking has baby_list_item_id directly
                    if not items and hasattr(record, 'baby_list_item_id') and record.baby_list_item_id:
                        items = record.baby_list_item_id
                    
                    if items:
                        # Update all unlinked workflow actions for this picking
                        unlinked_actions = self.env['document.workflow.action'].search([
                            ('document_type', '=', 'picking'),
                            ('res_id', '=', record.id),
                            ('baby_list_item_id', '=', False),
                        ])
                        
                        # Link to the first matching item (usually there's only one)
                        if unlinked_actions and items:
                            item = items[0] if isinstance(items, list) else items
                            unlinked_actions.write({
                                'baby_list_item_id': item.id,
                                'baby_list_id': item.list_id.id if item.list_id else False,
                                'sequence': item.sequence if item.sequence else 10,
                            })
                except Exception:
                    pass
        
        if 'state' in vals:
            for record in self:
                if record.id in state_before and state_before[record.id] != record.state:
                    try:
                        # Try to find linked baby.list.item
                        baby_list_item_id = False
                        baby_list_id = False
                        sequence = 10
                        try:
                            # Method 1: Check if picking has baby_list_item_id directly (from moombs_list)
                            if hasattr(record, 'baby_list_item_id') and record.baby_list_item_id:
                                item = record.baby_list_item_id
                                baby_list_item_id = item.id
                                baby_list_id = item.list_id.id if item.list_id else False
                                sequence = item.id  # Use item ID for unique ordering
                            
                            # Method 2: Check all picking fields on baby.list.item
                            if not baby_list_item_id:
                                item = self.env['baby.list.item'].search([
                                    '|', '|',
                                    ('picking_out_id', '=', record.id),
                                    ('picking_in_id', '=', record.id),
                                    ('picking_pending_id', '=', record.id),
                                ], limit=1)
                                
                                if item:
                                    baby_list_item_id = item.id
                                    baby_list_id = item.list_id.id if item.list_id else False
                                    sequence = item.id  # Use item ID for unique ordering
                            
                            # Method 3: Try via sale_line_id in moves
                            if not baby_list_item_id and record.move_ids:
                                for move in record.move_ids:
                                    if move.sale_line_id:
                                        item = self.env['baby.list.item'].search([
                                            ('sale_order_line_id', '=', move.sale_line_id.id)
                                        ], limit=1)
                                        if item:
                                            baby_list_item_id = item.id
                                            baby_list_id = item.list_id.id if item.list_id else False
                                            sequence = item.id  # Use item ID for unique ordering
                                            break
                        except Exception:
                            pass
                        
                        # Determine transfer type based on picking type
                        transfer_type = False
                        if record.picking_type_id:
                            picking_code = record.picking_type_id.code
                            if picking_code == 'incoming':
                                transfer_type = 'receipt_to_warehouse'
                            elif picking_code == 'outgoing':
                                transfer_type = 'warehouse_to_delivery'
                            elif picking_code == 'internal':
                                # Check if it's to pending delivery location
                                if record.location_dest_id and 'pending' in record.location_dest_id.name.lower():
                                    transfer_type = 'warehouse_to_pending'
                                else:
                                    transfer_type = 'internal'
                        
                        # Log state change ALWAYS (even if not linked yet - can link later)
                        action_vals = {
                            'document_type': 'picking',
                            'document_ref': record.name,
                            'res_id': record.id,
                            'action_type': 'state_change',
                            'action_source': 'user',
                            'state_from': state_before[record.id],
                            'state_to': record.state,
                            'date_logged': fields.Datetime.now(),
                            'user_id': self.env.uid,
                            'partner_id': record.partner_id.id if record.partner_id else False,
                            'company_id': record.company_id.id,
                            'transfer_type': transfer_type if transfer_type else False,
                        }
                        # Add gift list references if found
                        if baby_list_item_id:
                            action_vals['baby_list_item_id'] = baby_list_item_id
                        if baby_list_id:
                            action_vals['baby_list_id'] = baby_list_id
                        if sequence:
                            action_vals['sequence'] = sequence
                        
                        action = self.env['document.workflow.action'].create(action_vals)
                        
                        # If not linked yet, try to link after creation (in case item gets linked later)
                        if not baby_list_item_id:
                            # Try one more time after a short delay (in case item was just linked)
                            try:
                                item = self.env['baby.list.item'].search([
                                    '|', '|',
                                    ('picking_out_id', '=', record.id),
                                    ('picking_in_id', '=', record.id),
                                    ('picking_pending_id', '=', record.id),
                                ], limit=1)
                                if not item and hasattr(record, 'baby_list_item_id') and record.baby_list_item_id:
                                    item = record.baby_list_item_id
                                
                                if item:
                                    action.write({
                                        'baby_list_item_id': item.id,
                                        'baby_list_id': item.list_id.id if item.list_id else False,
                                        'sequence': item.sequence if item.sequence else 10,
                                    })
                            except Exception:
                                pass
                    except Exception as e:
                        _logger.warning("[Workflow] Failed to log picking state change: %s", str(e))
        
        return res
    
    def button_validate(self):
        """Override to log validation (state change to 'done')"""
        # Capture state before validation
        state_before = {}
        for record in self:
            state_before[record.id] = record.state
        
        # Call super() which will change state to 'done'
        res = super().button_validate()
        
        # Log validation for each picking that changed to 'done'
        for record in self:
            if record.id in state_before and state_before[record.id] != 'done' and record.state == 'done':
                try:
                    # Try to find linked baby.list.item
                    baby_list_item_id = False
                    baby_list_id = False
                    sequence = 10
                    try:
                        # Method 1: Check if picking has baby_list_item_id directly
                        if hasattr(record, 'baby_list_item_id') and record.baby_list_item_id:
                            item = record.baby_list_item_id
                            baby_list_item_id = item.id
                            baby_list_id = item.list_id.id if item.list_id else False
                            sequence = item.id
                        
                        # Method 2: Check all picking fields on baby.list.item
                        if not baby_list_item_id:
                            item = self.env['baby.list.item'].search([
                                '|', '|',
                                ('picking_out_id', '=', record.id),
                                ('picking_in_id', '=', record.id),
                                ('picking_pending_id', '=', record.id),
                            ], limit=1)
                            
                            if item:
                                baby_list_item_id = item.id
                                baby_list_id = item.list_id.id if item.list_id else False
                                sequence = item.id
                        
                        # Method 3: Try via sale_line_id in moves
                        if not baby_list_item_id and record.move_ids:
                            for move in record.move_ids:
                                if move.sale_line_id:
                                    item = self.env['baby.list.item'].search([
                                        ('sale_order_line_id', '=', move.sale_line_id.id)
                                    ], limit=1)
                                    if item:
                                        baby_list_item_id = item.id
                                        baby_list_id = item.list_id.id if item.list_id else False
                                        sequence = item.id
                                        break
                    except Exception:
                        pass
                    
                    # Determine transfer type and action type
                    transfer_type = False
                    action_type = 'state_change'
                    if record.picking_type_id:
                        picking_code = record.picking_type_id.code
                        if picking_code == 'incoming':
                            transfer_type = 'receipt_to_warehouse'
                            action_type = 'receipt_validated'  # Receipt validated
                        elif picking_code == 'outgoing':
                            transfer_type = 'warehouse_to_delivery'
                            action_type = 'delivery_delivered'  # Delivery completed
                        elif picking_code == 'internal':
                            if record.location_dest_id and 'pending' in record.location_dest_id.name.lower():
                                transfer_type = 'warehouse_to_pending'
                            else:
                                transfer_type = 'internal'
                            action_type = 'internal_transfer_validated'  # Internal transfer validated
                    
                    action_vals = {
                        'document_type': 'picking',
                        'document_ref': record.name,
                        'res_id': record.id,
                        'action_type': action_type,
                        'action_source': 'user',
                        'state_from': state_before[record.id],
                        'state_to': 'done',
                        'date_logged': fields.Datetime.now(),
                        'user_id': self.env.uid,
                        'partner_id': record.partner_id.id if record.partner_id else False,
                        'company_id': record.company_id.id,
                        'transfer_type': transfer_type if transfer_type else False,
                    }
                    # Add gift list references if found
                    if baby_list_item_id:
                        action_vals['baby_list_item_id'] = baby_list_item_id
                    if baby_list_id:
                        action_vals['baby_list_id'] = baby_list_id
                    if sequence:
                        action_vals['sequence'] = sequence
                    
                    action = self.env['document.workflow.action'].create(action_vals)
                    
                    # If not linked yet, try to link after creation
                    if not baby_list_item_id:
                        try:
                            item = self.env['baby.list.item'].search([
                                '|', '|',
                                ('picking_out_id', '=', record.id),
                                ('picking_in_id', '=', record.id),
                                ('picking_pending_id', '=', record.id),
                            ], limit=1)
                            if not item and hasattr(record, 'baby_list_item_id') and record.baby_list_item_id:
                                item = record.baby_list_item_id
                            
                            if item:
                                action.write({
                                    'baby_list_item_id': item.id,
                                    'baby_list_id': item.list_id.id if item.list_id else False,
                                    'sequence': item.id,
                                })
                        except Exception:
                            pass
                except Exception as e:
                    _logger.warning("[Workflow] Failed to log picking validation: %s", str(e))
        
        return res


class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    workflow_action_count = fields.Integer(
        string='Workflow Actions',
        compute='_compute_workflow_action_count',
    )
    
    def _compute_workflow_action_count(self):
        """Compute number of workflow actions for this POS order"""
        for order in self:
            order.workflow_action_count = self.env['document.workflow.action'].search_count([
                ('document_type', '=', 'pos_order'),
                ('res_id', '=', order.id),
                ('is_archived', '=', False),
            ])
    
    def action_view_workflow_actions(self):
        """Open workflow actions for this POS order"""
        self.ensure_one()
        action = self.env.ref('moombs_workflow_manager.action_document_workflow_action').read()[0]
        action['domain'] = [
            ('document_type', '=', 'pos_order'),
            ('res_id', '=', self.id),
        ]
        action['context'] = {
            'default_document_type': 'pos_order',
            'default_document_ref': self.name,
            'default_res_id': self.id,
            'search_default_state_changes': 1,
        }
        return action
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to log creation"""
        records = super().create(vals_list)
        
        # Log creation for each record (note: linking happens later when pos_order_id/pos_downpayment_id is set)
        for record in records:
            try:
                action_vals = {
                    'document_type': 'pos_order',
                    'document_ref': getattr(record, 'pos_reference', False) or record.name or f'POS-{record.id}',
                    'res_id': record.id,
                    'action_type': 'creation',
                    'action_source': 'system',
                    'state_to': record.state if hasattr(record, 'state') else 'draft',
                    'date_logged': fields.Datetime.now(),
                    'user_id': self.env.uid,
                    'partner_id': record.partner_id.id if record.partner_id else False,
                    'company_id': record.company_id.id,
                    'amount_total': record.amount_total,
                    'currency_id': record.currency_id.id if record.currency_id else False,
                }
                self.env['document.workflow.action'].create(action_vals)
            except Exception as e:
                _logger.warning("[Workflow] Failed to log POS order creation: %s", str(e))
        
        return records
    
    def write(self, vals):
        """Override write to log state changes and link to gift list items"""
        state_before = {}
        if 'state' in vals:
            for record in self:
                state_before[record.id] = record.state
        
        res = super().write(vals)
        
        # Also update existing workflow actions if item was just linked
        # (This handles cases where POS order was created before item was linked)
        if not any(k in vals for k in ['state']):
            for record in self:
                try:
                    # Find items linked to this POS order (either as downpayment or final payment)
                    items = self.env['baby.list.item'].search([
                        '|',
                        ('pos_downpayment_id', '=', record.id),
                        ('pos_order_id', '=', record.id),
                    ])
                    
                    if items:
                        # Update all unlinked workflow actions for this POS order
                        unlinked_actions = self.env['document.workflow.action'].search([
                            ('document_type', '=', 'pos_order'),
                            ('res_id', '=', record.id),
                            ('baby_list_item_id', '=', False),
                        ])
                        
                        # Link to the first matching item (usually there's only one)
                        if unlinked_actions and items:
                            item = items[0]
                            unlinked_actions.write({
                                'baby_list_item_id': item.id,
                                'baby_list_id': item.list_id.id if item.list_id else False,
                                'sequence': item.sequence if item.sequence else 10,
                            })
                except Exception:
                    pass
        
        if 'state' in vals:
            for record in self:
                if record.id in state_before and state_before[record.id] != record.state:
                    try:
                        # Try to find linked baby.list.item
                        baby_list_item_id = False
                        baby_list_id = False
                        sequence = 10
                        try:
                            # Check if POS order is linked as downpayment or final payment
                            item = self.env['baby.list.item'].search([
                                '|',
                                ('pos_downpayment_id', '=', record.id),
                                ('pos_order_id', '=', record.id),
                            ], limit=1)
                            
                            if item:
                                baby_list_item_id = item.id
                                baby_list_id = item.list_id.id if item.list_id else False
                                sequence = item.id  # Use item ID for unique ordering
                        except Exception:
                            pass
                        
                        action_vals = {
                            'document_type': 'pos_order',
                            'document_ref': record.name,
                            'res_id': record.id,
                            'action_type': 'state_change',
                            'action_source': 'user',
                            'state_from': state_before[record.id],
                            'state_to': record.state,
                            'date_logged': fields.Datetime.now(),
                            'user_id': self.env.uid,
                            'partner_id': record.partner_id.id if record.partner_id else False,
                            'company_id': record.company_id.id,
                            'amount_total': record.amount_total,
                            'currency_id': record.currency_id.id if record.currency_id else False,
                        }
                        # Add gift list references if found
                        if baby_list_item_id:
                            action_vals['baby_list_item_id'] = baby_list_item_id
                        if baby_list_id:
                            action_vals['baby_list_id'] = baby_list_id
                        if sequence:
                            action_vals['sequence'] = sequence
                        
                        self.env['document.workflow.action'].create(action_vals)
                    except Exception as e:
                        _logger.warning("[Workflow] Failed to log POS order state change: %s", str(e))
        
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    workflow_action_count = fields.Integer(
        string='Workflow Actions',
        compute='_compute_workflow_action_count',
    )
    
    @api.depends('move_type')
    def _compute_workflow_action_count(self):
        """Compute number of workflow actions for this invoice"""
        for move in self:
            document_type = 'invoice_out' if move.move_type in ['out_invoice', 'out_refund'] else 'invoice_in'
            move.workflow_action_count = self.env['document.workflow.action'].search_count([
                ('document_type', '=', document_type),
                ('res_id', '=', move.id),
                ('is_archived', '=', False),
            ])
    
    def action_view_workflow_actions(self):
        """Open workflow actions for this invoice"""
        self.ensure_one()
        document_type = 'invoice_out' if self.move_type in ['out_invoice', 'out_refund'] else 'invoice_in'
        action = self.env.ref('moombs_workflow_manager.action_document_workflow_action').read()[0]
        action['domain'] = [
            ('document_type', '=', document_type),
            ('res_id', '=', self.id),
        ]
        action['context'] = {
            'default_document_type': document_type,
            'default_document_ref': self.name,
            'default_res_id': self.id,
            'search_default_state_changes': 1,
        }
        return action
    
    def write(self, vals):
        """Override write to log state changes"""
        state_before = {}
        if 'state' in vals:
            for record in self:
                # Only log for invoices/bills
                if record.move_type in ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']:
                    state_before[record.id] = record.state
        
        res = super().write(vals)
        
        if 'state' in vals:
            for record in self:
                if record.id in state_before and state_before[record.id] != record.state:
                    try:
                        document_type = 'invoice_out' if record.move_type in ['out_invoice', 'out_refund'] else 'invoice_in'
                        self.env['document.workflow.action'].create({
                            'document_type': document_type,
                            'document_ref': record.name,
                            'res_id': record.id,
                            'action_type': 'state_change',
                            'action_source': 'user',
                            'state_from': state_before[record.id],
                            'state_to': record.state,
                            'date_logged': fields.Datetime.now(),
                            'user_id': self.env.uid,
                            'partner_id': record.partner_id.id if record.partner_id else False,
                            'company_id': record.company_id.id,
                            'amount_total': record.amount_total,
                            'currency_id': record.currency_id.id if record.currency_id else False,
                        })
                    except Exception as e:
                        _logger.warning("[Workflow] Failed to log invoice state change: %s", str(e))
        
        return res

