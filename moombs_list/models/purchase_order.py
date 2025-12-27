# -*- coding: utf-8 -*-
"""
purchase.order Extension
========================

Epic 5: Handle PO state changes to update baby list item status.

SIMPLER APPROACH: Hook into button_confirm() instead of action_rfq_send().
When PO is confirmed (state='purchase'), we update baby list items immediately.
This is more reliable than trying to catch the 'sent' state change.

FOLLOWS DELIVERY VALIDATION PATTERN:
- Delivery: button_validate() → super() → _handle_customer_delivery() → item._compute_state()
- PO Confirmed: button_confirm() → super() → _handle_po_confirmed() → item._compute_state()
"""

from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        """Override to update baby list items when PO is confirmed.
        
        When PO is confirmed (state changes to 'purchase'), we update baby list items.
        This ensures items are updated immediately when PO is confirmed.
        
        FOLLOWS DELIVERY VALIDATION PATTERN:
        - Delivery: button_validate() → super() → _handle_customer_delivery() → item._compute_state()
        - PO Confirmed: button_confirm() → super() → _handle_po_confirmed() → item._compute_state()
        """
        res = super().button_confirm()
        
        # AFTER super() completes - PO state is now 'purchase'
        for po in self:
            _logger.info("[MOOMBS] button_confirm: PO ID=%s confirmed (state=%s), updating baby list items", 
                        po.id, po.state)
            self._handle_po_confirmed(po)
        
        return res

    def action_rfq_send(self):
        """Override to update baby list items when PO is sent.
        
        When "Send PO" is clicked, this opens the email composer.
        After email is sent, PO state changes to 'sent'.
        We'll also update items here to ensure state is updated when Send PO is clicked.
        
        NOTE: The actual state change to 'sent' happens after email is sent,
        but we can also update items here to ensure they're refreshed.
        """
        res = super().action_rfq_send()
        
        # Log that we're about to send PO
        for po in self:
            _logger.info("[MOOMBS] action_rfq_send: PO ID=%s (current state=%s) - opening email composer", 
                        po.id, po.state)
            # Update items immediately - state will be 'purchase' or 'sent' depending on when this is called
            self._handle_po_confirmed(po)
        
        return res

    def write(self, vals):
        """Override to detect when PO state changes to 'sent' and update baby list items.
        
        CRITICAL: PO state changes to 'sent' AFTER email is sent via mail.compose.message.
        We detect this in write() and trigger state recomputation.
        
        FOLLOWS DELIVERY VALIDATION PATTERN:
        - Delivery: button_validate() → super() → _handle_customer_delivery() → item._compute_state()
        - PO Sent: write() detects state='sent' → _handle_po_sent() → item._compute_state()
        """
        # Check if state is changing to 'sent' BEFORE calling super()
        state_changing_to_sent = False
        po_ids_to_update = []
        
        if 'state' in vals and vals['state'] == 'sent':
            state_changing_to_sent = True
            # CRITICAL: Get PO IDs from self (recordset) - if empty, might be called from different context
            po_ids_to_update = [po.id for po in self] if self else []
            
            # FALLBACK 1: If self is empty, try to get PO ID from context or active_id
            if not po_ids_to_update:
                active_id = self.env.context.get('active_id')
                active_model = self.env.context.get('active_model')
                if active_model == 'purchase.order' and active_id:
                    po_ids_to_update = [active_id]
                    _logger.info("[MOOMBS] write: PO state changing to 'sent' - self is empty, using active_id=%s from context", active_id)
            
            # FALLBACK 2: If still empty, try to get from res_id in context (mail composer uses this)
            if not po_ids_to_update:
                res_id = self.env.context.get('res_id')
                res_model = self.env.context.get('res_model')
                if res_model == 'purchase.order' and res_id:
                    po_ids_to_update = [res_id]
                    _logger.info("[MOOMBS] write: PO state changing to 'sent' - using res_id=%s from context", res_id)
            
            _logger.info("[MOOMBS] write: PO state changing to 'sent' for PO IDs: %s (self count: %s, context: %s)", 
                        po_ids_to_update, len(self), {
                            'active_id': self.env.context.get('active_id'),
                            'active_model': self.env.context.get('active_model'),
                            'res_id': self.env.context.get('res_id'),
                            'res_model': self.env.context.get('res_model'),
                        })
        
        res = super().write(vals)
        
        # CRITICAL: If write() was called with state='sent' but state didn't actually change,
        # it means Odoo's standard behavior didn't change the state.
        # In this case, we need to manually set the state to 'sent' and then process it.
        if state_changing_to_sent and po_ids_to_update:
            for po_id in po_ids_to_update:
                try:
                    fresh_po = self.env['purchase.order'].browse(po_id)
                    if fresh_po.exists():
                        # Check if state is actually 'sent' now
                        if fresh_po.state == 'sent':
                            _logger.info("[MOOMBS] write: PO ID=%s state is 'sent' immediately, processing now", po_id)
                            self._handle_po_sent(fresh_po)
                        else:
                            # State didn't change to 'sent' - manually set it
                            # This happens when mail composer calls write() but Odoo doesn't change state
                            _logger.info("[MOOMBS] write: PO ID=%s state is '%s' (expected 'sent'), manually setting to 'sent'", 
                                      po_id, fresh_po.state)
                            # Use sudo to bypass any access rights, then set state
                            fresh_po.sudo().write({'state': 'sent'})
                            # Now process it
                            fresh_po.invalidate_recordset(['state'])
                            fresh_po_after = self.env['purchase.order'].browse(po_id)
                            if fresh_po_after.state == 'sent':
                                self._handle_po_sent(fresh_po_after)
                            else:
                                _logger.warning("[MOOMBS] write: Failed to set PO ID=%s state to 'sent' (still '%s')", 
                                              po_id, fresh_po_after.state)
                except Exception as e:
                    _logger.warning("[MOOMBS] write: Error processing PO ID=%s (non-critical): %s", po_id, e)
        
        return res

    def _handle_po_confirmed(self, po):
        """Handle PO confirmed state update (same pattern as _handle_customer_delivery).
        
        SIMPLE APPROACH:
        1. Find items linked to this PO
        2. Invalidate cache and recompute state
        3. State should change to 'po_draft' (Priority 9) or 'po_sent' if already sent
        
        CRITICAL: Use fresh environment to avoid cache issues.
        """
        try:
            po_id = po.id
            po_state = po.state  # Read state after button_confirm() completes
            
            _logger.info("[MOOMBS] _handle_po_confirmed: PO ID=%s confirmed (state=%s), finding items", 
                        po_id, po_state)
            
            # Find baby list items linked to this PO
            items = po.env['baby.list.item'].search([
                ('purchase_order_id', '=', po_id),
            ])
            
            if items:
                _logger.info("[MOOMBS] _handle_po_confirmed: Found %s items, updating state", len(items))
                
                # CRITICAL: For stored computed fields, we need to trigger recomputation by writing to a dependency
                # Following the same pattern as stock_picking.py which uses item.write() to trigger recomputation
                # We'll do a no-op write to purchase_order_id to trigger Odoo's automatic recomputation
                # This ensures the computed state is actually stored in the database
                for item in items:
                    # Force refresh PO state in cache
                    if item.purchase_order_id:
                        item.purchase_order_id.invalidate_recordset(['state'])
                    
                    # CRITICAL: Write to dependency field to trigger automatic recomputation and storage
                    # This is the same pattern used in stock_picking.py
                    # Writing to purchase_order_id (even if same value) triggers recomputation of state
                    item.write({'purchase_order_id': item.purchase_order_id.id})
                
                # Now read the recomputed state (it should be stored in DB now)
                _logger.info("[MOOMBS] _handle_po_confirmed: State updated for items: %s", 
                            [(item.id, item.state) for item in items])
                
                # Verify state is correct
                for item in items:
                    if item.picking_in_id:
                        # Receipt exists - state should be 'pending' (Priority 7.5) or 'received' (Priority 7)
                        _logger.info("[MOOMBS] _handle_po_confirmed: Item ID=%s has receipt, state=%s (expected 'pending' or 'received')", 
                                    item.id, item.state)
                    elif item.state in ['po_draft', 'po_sent']:
                        _logger.info("[MOOMBS] _handle_po_confirmed: ✓ Item ID=%s state is correctly '%s'", item.id, item.state)
                    else:
                        _logger.warning("[MOOMBS] _handle_po_confirmed: Item ID=%s state is '%s' (expected 'po_draft' or 'po_sent')", 
                                      item.id, item.state)
            else:
                _logger.info("[MOOMBS] _handle_po_confirmed: No items found for PO ID=%s", po_id)
                
        except Exception as e:
            # Log error but don't break PO workflow (same as delivery validation pattern)
            _logger.warning("[MOOMBS] _handle_po_confirmed: Could not recompute state (non-critical): %s", e)

    def _handle_po_sent(self, po):
        """Handle PO sent state update (same pattern as _handle_customer_delivery).
        
        SIMPLE APPROACH:
        1. Find items linked to this PO
        2. Invalidate cache and recompute state
        3. State should change to 'po_sent' (Priority 8)
        
        CRITICAL: Use fresh environment to avoid cache issues.
        """
        try:
            po_id = po.id
            po_state = po.state  # Read state after write() completes
            
            _logger.info("[MOOMBS] _handle_po_sent: PO ID=%s sent (state=%s), finding items", 
                        po_id, po_state)
            
            # CRITICAL: Verify PO state is actually 'sent' before proceeding
            if po_state != 'sent':
                _logger.warning("[MOOMBS] _handle_po_sent: PO ID=%s state is '%s' (expected 'sent'), skipping", 
                              po_id, po_state)
                return
            
            # Find baby list items linked to this PO
            # Same pattern as _handle_customer_delivery() - simple search
            # Use fresh environment to avoid cache issues
            items = po.env['baby.list.item'].search([
                ('purchase_order_id', '=', po_id),
            ])
            
            if items:
                _logger.info("[MOOMBS] _handle_po_sent: Found %s items, updating state", len(items))
                
                # CRITICAL: For stored computed fields, we need to trigger recomputation by writing to a dependency
                # Following the same pattern as stock_picking.py which uses item.write() to trigger recomputation
                # We'll do a no-op write to purchase_order_id to trigger Odoo's automatic recomputation
                # This ensures the computed state is actually stored in the database
                for item in items:
                    # Force refresh PO state in cache
                    if item.purchase_order_id:
                        item.purchase_order_id.invalidate_recordset(['state'])
                    
                    # CRITICAL: Write to dependency field to trigger automatic recomputation and storage
                    # This is the same pattern used in stock_picking.py
                    # Writing to purchase_order_id (even if same value) triggers recomputation of state
                    item.write({'purchase_order_id': item.purchase_order_id.id})
                
                # Now read the recomputed state (it should be stored in DB now)
                _logger.info("[MOOMBS] _handle_po_sent: State updated for items: %s", 
                            [(item.id, item.state) for item in items])
                
                # Verify state is 'po_sent' (if receipt not created yet)
                for item in items:
                    if item.picking_in_id:
                        # Receipt exists - state should be 'pending' (Priority 7.5) or 'received' (Priority 7)
                        _logger.info("[MOOMBS] _handle_po_sent: Item ID=%s has receipt, state=%s (expected 'pending' or 'received')", 
                                    item.id, item.state)
                    elif item.state == 'po_sent':
                        _logger.info("[MOOMBS] _handle_po_sent: ✓ Item ID=%s state is correctly 'po_sent'", item.id)
                    else:
                        _logger.warning("[MOOMBS] _handle_po_sent: Item ID=%s state is '%s' (expected 'po_sent')", 
                                      item.id, item.state)
            else:
                _logger.info("[MOOMBS] _handle_po_sent: No items found for PO ID=%s", po_id)
                
        except Exception as e:
            # Log error but don't break PO workflow (same as delivery validation pattern)
            _logger.warning("[MOOMBS] _handle_po_sent: Could not recompute state (non-critical): %s", e)
