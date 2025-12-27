# -*- coding: utf-8 -*-
"""
Baby List Extension for Workflow Manager
=========================================

Adds workflow action tracking to baby.list
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class BabyList(models.Model):
    _inherit = 'baby.list'
    
    workflow_action_ids = fields.One2many(
        'document.workflow.action',
        'baby_list_id',
        string='Workflow Actions',
        readonly=True,
    )
    
    workflow_action_count = fields.Integer(
        string='Workflow Actions',
        compute='_compute_workflow_action_count',
    )
    
    def _compute_workflow_action_count(self):
        """Compute number of workflow actions for this list"""
        for record in self:
            record.workflow_action_count = len(record.workflow_action_ids)
    
    def action_link_workflow_actions(self):
        """Retroactively link workflow actions to gift list items"""
        self.ensure_one()
        
        # Find all workflow actions for SOs/POs/Pickings related to this list's items
        items = self.item_ids
        linked_count = 0
        
        for item in items:
            # Find workflow actions for this item's documents
            actions_to_link = []
            
            # Check sale order
            if item.sale_order_id:
                actions = self.env['document.workflow.action'].search([
                    ('document_type', '=', 'sale_order'),
                    ('res_id', '=', item.sale_order_id.id),
                    ('baby_list_item_id', '=', False),  # Not yet linked
                ])
                actions_to_link.extend(actions)
            
            # Check purchase order
            if item.purchase_order_id:
                actions = self.env['document.workflow.action'].search([
                    ('document_type', '=', 'purchase_order'),
                    ('res_id', '=', item.purchase_order_id.id),
                    ('baby_list_item_id', '=', False),
                ])
                actions_to_link.extend(actions)
            
            # Check pickings
            for picking_field in ['picking_out_id', 'picking_in_id', 'picking_pending_id']:
                picking = getattr(item, picking_field, None)
                if picking:
                    actions = self.env['document.workflow.action'].search([
                        ('document_type', '=', 'picking'),
                        ('res_id', '=', picking.id),
                        ('baby_list_item_id', '=', False),
                    ])
                    actions_to_link.extend(actions)
            
            # Check POS orders (downpayment and final payment)
            if item.pos_downpayment_id:
                actions = self.env['document.workflow.action'].search([
                    ('document_type', '=', 'pos_order'),
                    ('res_id', '=', item.pos_downpayment_id.id),
                    ('baby_list_item_id', '=', False),
                ])
                actions_to_link.extend(actions)
            
            if item.pos_order_id:
                actions = self.env['document.workflow.action'].search([
                    ('document_type', '=', 'pos_order'),
                    ('res_id', '=', item.pos_order_id.id),
                    ('baby_list_item_id', '=', False),
                ])
                actions_to_link.extend(actions)
            
            # Update actions with item and list references
            for action in actions_to_link:
                action.write({
                    'baby_list_item_id': item.id,
                    'baby_list_id': self.id,
                    'sequence': item.id,  # Use item ID for unique ordering
                })
                linked_count += 1
        
        # Recalculate action sequences for all affected items
        if linked_count > 0:
            self.env['document.workflow.action']._recalculate_item_sequences(items)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Workflow Actions Linked',
                'message': f'Successfully linked {linked_count} workflow actions to gift list items.',
                'type': 'success',
                'sticky': False,
            }
        }

