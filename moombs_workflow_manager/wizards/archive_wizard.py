# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ArchiveWizard(models.TransientModel):
    _name = 'workflow.archive.wizard'
    _description = 'Workflow Archive Wizard'
    
    retention_months = fields.Integer(
        string='Retention Period (Months)',
        default=12,
        required=True,
        help='Archive actions older than this many months'
    )
    
    document_type = fields.Selection([
        ('all', 'All Document Types'),
        ('sale_order', 'Sale Order'),
        ('purchase_order', 'Purchase Order'),
        ('invoice_out', 'Customer Invoice'),
        ('invoice_in', 'Vendor Bill'),
        ('picking', 'Stock Transfer'),
                ('pos_order', 'POS Order'),
                ('helpdesk', 'Helpdesk Ticket'),
                ('baby_list_item', 'Gift List Item'),
    ], string='Document Type', default='all', required=True)
    
    archive_count = fields.Integer(
        string='Actions to Archive',
        compute='_compute_archive_count',
    )
    
    @api.depends('retention_months', 'document_type')
    def _compute_archive_count(self):
        """Compute number of actions that will be archived"""
        from dateutil.relativedelta import relativedelta
        cutoff_date = fields.Datetime.now() - relativedelta(months=self.retention_months)
        
        domain = [
            ('date_logged', '<', cutoff_date),
            ('is_archived', '=', False),
        ]
        
        if self.document_type != 'all':
            domain.append(('document_type', '=', self.document_type))
        
        self.archive_count = self.env['document.workflow.action'].search_count(domain)
    
    def action_archive(self):
        """Archive actions based on wizard settings"""
        self.ensure_one()
        
        if self.archive_count == 0:
            raise UserError(_('No actions to archive with the selected criteria.'))
        
        if self.document_type == 'all':
            archived_count = self.env['workflow.archive'].archive_old_actions(self.retention_months)
        else:
            archived_count = self.env['workflow.archive'].archive_by_document_type(
                self.document_type,
                self.retention_months
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Archive Complete'),
                'message': _('%d actions have been archived.') % archived_count,
                'type': 'success',
                'sticky': False,
            }
        }

