# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class APIIntegration(models.AbstractModel):
    """Abstract model for API integration handlers"""
    _name = 'workflow.api.integration'
    _description = 'Workflow API Integration'

    def process_webhook(self, provider, data):
        """Process webhook data from external API
        
        Args:
            provider: API provider name (e.g., 'DHL', 'Stripe')
            data: Webhook payload (dict)
        
        Returns:
            dict: Result with success status and action record
        """
        raise NotImplementedError("Subclasses must implement process_webhook")


class ShippingAPIHandler(models.Model):
    """Handler for shipping provider webhooks"""
    _name = 'workflow.shipping.api'
    _description = 'Shipping API Handler'
    _inherit = 'workflow.api.integration'

    provider = fields.Char(required=True)
    api_key = fields.Char(string='API Key')
    webhook_url = fields.Char(string='Webhook URL')

    def process_webhook(self, provider, data):
        """Process shipping webhook"""
        from ..services.action_logger import ActionLogger
        
        tracking_number = data.get('tracking_number')
        status = data.get('status')
        document_ref = data.get('document_ref')
        
        # Find picking by reference
        picking = self.env['stock.picking'].search([
            ('name', '=', document_ref)
        ], limit=1)
        
        if not picking:
            return {'error': 'Picking not found', 'success': False}
        
        # Map status to action_type
        action_type_map = {
            'in_transit': 'api_shipment_in_transit',
            'delivered': 'api_shipment_delivered',
            'exception': 'api_shipment_exception',
            'created': 'api_shipment_created',
        }
        
        action_type = action_type_map.get(status, 'api_shipment_created')
        
        # Log action
        action = ActionLogger.log_api_event(
            self.env,
            document_type='picking',
            document_ref=picking.name,
            res_id=picking.id,
            api_provider=provider,
            api_response_id=tracking_number,
            action_type=action_type,
            state_to=status,
            api_webhook_data=str(data),
            partner_id=picking.partner_id.id if picking.partner_id else False,
            company_id=picking.company_id.id,
            note=f"Webhook from {provider}: {status}",
        )
        
        return {'success': True, 'action': action}


class PaymentAPIHandler(models.Model):
    """Handler for payment gateway webhooks"""
    _name = 'workflow.payment.api'
    _description = 'Payment API Handler'
    _inherit = 'workflow.api.integration'

    provider = fields.Char(required=True)
    api_key = fields.Char(string='API Key')
    webhook_url = fields.Char(string='Webhook URL')

    def process_webhook(self, provider, data):
        """Process payment webhook"""
        from ..services.action_logger import ActionLogger
        
        payment_id = data.get('payment_id')
        status = data.get('status')
        amount = data.get('amount')
        currency = data.get('currency')
        document_ref = data.get('document_ref')
        res_id = data.get('res_id')
        
        action_type_map = {
            'authorized': 'api_payment_authorized',
            'captured': 'api_payment_captured',
            'failed': 'api_payment_failed',
        }
        
        action_type = action_type_map.get(status, 'api_payment_authorized')
        
        # Determine document type
        document_type = 'invoice_out'  # Default, can be enhanced
        
        currency_id = False
        if currency:
            currency_record = self.env['res.currency'].search([
                ('name', '=', currency)
            ], limit=1)
            currency_id = currency_record.id if currency_record else False
        
        # Log action
        action = ActionLogger.log_api_event(
            self.env,
            document_type=document_type,
            document_ref=document_ref or '',
            res_id=res_id or 0,
            api_provider=provider,
            api_response_id=payment_id,
            action_type=action_type,
            amount_total=amount,
            currency_id=currency_id,
            api_webhook_data=str(data),
            note=f"Payment webhook from {provider}: {status}",
        )
        
        return {'success': True, 'action': action}

