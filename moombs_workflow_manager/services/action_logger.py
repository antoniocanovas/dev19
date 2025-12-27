# -*- coding: utf-8 -*-

import logging
from odoo import fields

_logger = logging.getLogger(__name__)


class ActionLogger:
    """Centralized service for logging workflow actions with performance optimizations"""
    
    # Configuration: Enable/disable logging per document type (for scalability)
    LOGGING_CONFIG = {
        'sale_order': True,
        'purchase_order': True,
        'invoice_out': True,
        'invoice_in': True,
        'picking': True,
        'pos_order': True,
        'helpdesk': False,  # Optional - can disable if not needed
        'baby_list': True,
        'baby_list_item': True,
    }
    
    @staticmethod
    def _is_logging_enabled(document_type):
        """Check if logging is enabled for this document type"""
        return ActionLogger.LOGGING_CONFIG.get(document_type, True)
    
    @staticmethod
    def log_action(env, **kwargs):
        """Log a workflow action with standardized parameters and error handling
        
        Args:
            env: Odoo environment
            **kwargs: Action parameters (document_type, document_ref, res_id, etc.)
        
        Returns:
            Created record(s) or False if failed
        """
        try:
            # Check if logging is enabled for this document type
            document_type = kwargs.get('document_type')
            if document_type and not ActionLogger._is_logging_enabled(document_type):
                return False
            
            defaults = {
                'date_logged': fields.Datetime.now(),
                'user_id': env.uid if kwargs.get('action_source') == 'user' else False,
                'company_id': env.company.id if env.company else False,
            }
            defaults.update(kwargs)
            
            # Batch create support (if multiple actions provided)
            if isinstance(defaults.get('res_id'), list):
                # Multiple records - batch create
                actions_to_create = []
                for res_id in defaults['res_id']:
                    action_vals = defaults.copy()
                    action_vals['res_id'] = res_id
                    actions_to_create.append(action_vals)
                return env['document.workflow.action'].create(actions_to_create)
            else:
                # Single record
                return env['document.workflow.action'].create(defaults)
                
        except Exception as e:
            # Log error but don't break workflow (non-critical)
            _logger.warning("[Workflow Manager] Failed to log action (non-critical): %s", str(e))
            return False
    
    @staticmethod
    def log_state_change(env, document_type, document_ref, res_id, 
                        state_from, state_to, **kwargs):
        """Convenience method for state changes
        
        Args:
            env: Odoo environment
            document_type: Type of document (e.g., 'sale_order')
            document_ref: Document reference (e.g., 'SO001')
            res_id: Resource ID
            state_from: Previous state
            state_to: New state
            **kwargs: Additional parameters (partner_id, amount_total, etc.)
        
        Returns:
            Created record or False if failed
        """
        return ActionLogger.log_action(
            env,
            document_type=document_type,
            document_ref=document_ref,
            res_id=res_id,
            action_type='state_change',
            action_source=kwargs.pop('action_source', 'user'),
            state_from=state_from,
            state_to=state_to,
            **kwargs
        )
    
    @staticmethod
    def log_transfer(env, picking, transfer_type, **kwargs):
        """Convenience method for transfer actions
        
        Args:
            env: Odoo environment
            picking: stock.picking record
            transfer_type: Type of transfer (e.g., 'warehouse_to_delivery')
            **kwargs: Additional parameters
        
        Returns:
            Created record or False if failed
        """
        return ActionLogger.log_action(
            env,
            document_type='picking',
            document_ref=picking.name,
            res_id=picking.id,
            action_type=f'transfer_{transfer_type}',
            action_source='user',
            transfer_type=transfer_type,
            state_from='assigned',
            state_to='done',
            partner_id=picking.partner_id.id if picking.partner_id else False,
            company_id=picking.company_id.id if picking.company_id else False,
            **kwargs
        )
    
    @staticmethod
    def log_api_event(env, document_type, document_ref, res_id,
                     api_provider, api_response_id, action_type, **kwargs):
        """Convenience method for API events
        
        Args:
            env: Odoo environment
            document_type: Type of document
            document_ref: Document reference
            res_id: Resource ID
            api_provider: API provider name (e.g., 'DHL')
            api_response_id: External tracking/response ID
            action_type: Type of API action (e.g., 'api_shipment_in_transit')
            **kwargs: Additional parameters (api_webhook_data, state_to, etc.)
        
        Returns:
            Created record or False if failed
        """
        return ActionLogger.log_action(
            env,
            document_type=document_type,
            document_ref=document_ref,
            res_id=res_id,
            action_type=action_type,
            action_source='api',
            api_provider=api_provider,
            api_response_id=api_response_id,
            **kwargs
        )
    
    @staticmethod
    def log_creation(env, document_type, document_ref, res_id, **kwargs):
        """Convenience method for document creation
        
        Args:
            env: Odoo environment
            document_type: Type of document
            document_ref: Document reference
            res_id: Resource ID
            **kwargs: Additional parameters
        
        Returns:
            Created record or False if failed
        """
        return ActionLogger.log_action(
            env,
            document_type=document_type,
            document_ref=document_ref,
            res_id=res_id,
            action_type='creation',
            action_source=kwargs.pop('action_source', 'system'),
            **kwargs
        )

