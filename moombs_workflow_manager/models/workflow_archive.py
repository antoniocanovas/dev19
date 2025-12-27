# -*- coding: utf-8 -*-

from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class WorkflowArchive(models.TransientModel):
    _name = 'workflow.archive'
    _description = 'Workflow Archive Management'
    
    def archive_old_actions(self, retention_months=12):
        """Archive actions older than retention period
        
        Args:
            retention_months: Number of months to retain (default: 12)
        
        Returns:
            int: Number of actions archived
        """
        cutoff_date = fields.Datetime.now() - relativedelta(months=retention_months)
        
        old_actions = self.env['document.workflow.action'].search([
            ('date_logged', '<', cutoff_date),
            ('is_archived', '=', False),
        ])
        
        count = len(old_actions)
        if count > 0:
            old_actions.write({
                'is_archived': True,
                'archived_date': fields.Datetime.now(),
            })
            _logger.info("[Workflow] Archived %d actions older than %s", count, cutoff_date)
        
        return count
    
    def archive_by_document_type(self, document_type, retention_months=12):
        """Archive actions for a specific document type
        
        Args:
            document_type: Document type to archive
            retention_months: Number of months to retain
        
        Returns:
            int: Number of actions archived
        """
        cutoff_date = fields.Datetime.now() - relativedelta(months=retention_months)
        
        old_actions = self.env['document.workflow.action'].search([
            ('document_type', '=', document_type),
            ('date_logged', '<', cutoff_date),
            ('is_archived', '=', False),
        ])
        
        count = len(old_actions)
        if count > 0:
            old_actions.write({
                'is_archived': True,
                'archived_date': fields.Datetime.now(),
            })
            _logger.info("[Workflow] Archived %d %s actions older than %s", count, document_type, cutoff_date)
        
        return count

