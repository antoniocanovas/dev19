# -*- coding: utf-8 -*-
"""
Baby List Item Extension for Workflow Manager
==============================================

Adds workflow action tracking to baby.list.item
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class BabyListItem(models.Model):
    _inherit = 'baby.list.item'
    
    workflow_action_ids = fields.One2many(
        'document.workflow.action',
        'baby_list_item_id',
        string='Workflow Actions',
        readonly=True,
    )
    
    workflow_action_count = fields.Integer(
        string='Workflow Actions',
        compute='_compute_workflow_action_count',
    )
    
    def _compute_workflow_action_count(self):
        """Compute number of workflow actions for this item"""
        for item in self:
            item.workflow_action_count = len(item.workflow_action_ids)
    
    def action_view_item_workflow_actions(self):
        """Open workflow actions for this gift list item"""
        self.ensure_one()
        action = self.env.ref('moombs_workflow_manager.action_document_workflow_action').read()[0]
        action['domain'] = [('baby_list_item_id', '=', self.id)]
        action['context'] = {
            'default_baby_list_item_id': self.id,
            'default_document_type': 'baby_list_item',
        }
        action['name'] = f'Workflow Actions - {self.display_name}'
        return action
    
    def write(self, vals):
        """Override write to automatically link workflow actions when documents are linked"""
        res = super().write(vals)
        
        # Auto-link workflow actions when documents are linked to this item
        for item in self:
            documents_to_link = []
            
            # Check if sale_order_id was just set
            if 'sale_order_id' in vals and item.sale_order_id:
                documents_to_link.append(('sale_order', item.sale_order_id.id))
            
            # Check if purchase_order_id was just set
            if 'purchase_order_id' in vals and item.purchase_order_id:
                documents_to_link.append(('purchase_order', item.purchase_order_id.id))
            
            # Check if picking_out_id was just set
            if 'picking_out_id' in vals and item.picking_out_id:
                documents_to_link.append(('picking', item.picking_out_id.id))
            
            # Check if picking_in_id was just set
            if 'picking_in_id' in vals and item.picking_in_id:
                documents_to_link.append(('picking', item.picking_in_id.id))
            
            # Check if picking_pending_id was just set
            if 'picking_pending_id' in vals and item.picking_pending_id:
                documents_to_link.append(('picking', item.picking_pending_id.id))
            
            # Check if pos_order_id was just set
            if 'pos_order_id' in vals and item.pos_order_id:
                documents_to_link.append(('pos_order', item.pos_order_id.id))
            
            # Check if pos_downpayment_id was just set
            if 'pos_downpayment_id' in vals and item.pos_downpayment_id:
                documents_to_link.append(('pos_order', item.pos_downpayment_id.id))
            
            # Link all workflow actions for these documents
            for doc_type, doc_id in documents_to_link:
                unlinked_actions = self.env['document.workflow.action'].search([
                    ('document_type', '=', doc_type),
                    ('res_id', '=', doc_id),
                    ('baby_list_item_id', '=', False),  # Not yet linked
                ])
                
                if unlinked_actions:
                    unlinked_actions.write({
                        'baby_list_item_id': item.id,
                        'baby_list_id': item.list_id.id if item.list_id else False,
                        'sequence': item.id,  # Use item ID for unique ordering
                    })
                    _logger.info("[Workflow] Auto-linked %s workflow actions for %s %s to item %s", 
                               len(unlinked_actions), doc_type, doc_id, item.id)
                    # Recalculate sequences immediately after linking
                    self.env['document.workflow.action']._recalculate_item_sequences(item)
        
        # Recalculate sequences for all affected items (if any document links changed)
        if any(k in vals for k in ['sale_order_id', 'purchase_order_id', 'picking_out_id', 'picking_in_id', 'picking_pending_id', 'pos_order_id', 'pos_downpayment_id']):
            # Get all items that need recalculation
            items_to_recalc = self
            # Also include items that might have been affected by the linking above
            for item in self:
                if item.sale_order_id or item.purchase_order_id or item.picking_out_id or item.picking_in_id or item.picking_pending_id or item.pos_order_id or item.pos_downpayment_id:
                    items_to_recalc |= item
            if items_to_recalc:
                self.env['document.workflow.action']._recalculate_item_sequences(items_to_recalc)
        
        return res

