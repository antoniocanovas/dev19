# -*- coding: utf-8 -*-

from odoo import models, fields, api


class WorkflowConfig(models.Model):
    _name = 'workflow.config'
    _description = 'Workflow Manager Configuration'
    _rec_name = 'document_type'
    
    document_type = fields.Selection([
        ('sale_order', 'Sale Order'),
        ('purchase_order', 'Purchase Order'),
        ('invoice_out', 'Customer Invoice'),
        ('invoice_in', 'Vendor Bill'),
        ('picking', 'Stock Transfer'),
                ('pos_order', 'POS Order'),
                ('helpdesk', 'Helpdesk Ticket'),
                ('baby_list_item', 'Gift List Item'),
    ], string='Document Type', required=True)
    
    logging_enabled = fields.Boolean(
        string='Enable Logging',
        default=True,
        help='Enable workflow action logging for this document type'
    )
    
    retention_months = fields.Integer(
        string='Retention (Months)',
        default=12,
        help='Number of months to keep actions before archiving'
    )
    
    log_state_changes = fields.Boolean(
        string='Log State Changes',
        default=True,
    )
    
    log_creation = fields.Boolean(
        string='Log Document Creation',
        default=True,
    )
    
    log_api_events = fields.Boolean(
        string='Log API Events',
        default=True,
    )
    
    _sql_constraints = [
        ('unique_document_type', 'unique(document_type)', 'Document type configuration must be unique!'),
    ]

