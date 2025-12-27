# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
import json
import logging
import time

_logger = logging.getLogger(__name__)

# Simple rate limiting (can be enhanced with Redis, etc.)
_rate_limit_cache = {}


class WorkflowWebhookController(http.Controller):
    
    def _check_rate_limit(self, provider_key, max_requests=100, window_seconds=60):
        """Check rate limit for webhook requests
        
        Args:
            provider_key: Unique key for provider + IP
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        
        Returns:
            bool: True if allowed, False if rate limited
        """
        current_time = time.time()
        
        if provider_key in _rate_limit_cache:
            requests, last_time = _rate_limit_cache[provider_key]
            if current_time - last_time < window_seconds:
                if requests >= max_requests:
                    return False
                _rate_limit_cache[provider_key] = (requests + 1, last_time)
            else:
                _rate_limit_cache[provider_key] = (1, current_time)
        else:
            _rate_limit_cache[provider_key] = (1, current_time)
        
        return True
    
    @http.route('/workflow/webhook/shipping/<provider>', type='json', auth='api_key', methods=['POST'], csrf=False)
    def shipping_webhook(self, provider, **kwargs):
        """Handle shipping provider webhooks (DHL, FedEx, etc.)
        
        Expected payload:
        {
            "tracking_number": "1234567890",
            "status": "in_transit" | "delivered" | "exception",
            "document_ref": "WH/OUT/00001",
            "timestamp": "2025-01-15T10:30:00Z",
            "location": "Madrid, Spain",
            "estimated_delivery": "2025-01-20"
        }
        """
        try:
            # Rate limiting
            provider_key = f"{provider}_{request.httprequest.remote_addr}"
            if not self._check_rate_limit(provider_key):
                _logger.warning("[Workflow] Rate limit exceeded for %s", provider_key)
                return {'error': 'Rate limit exceeded', 'success': False}
            
            data = request.jsonrequest
            
            # Validate required fields
            if not data.get('tracking_number') or not data.get('status'):
                return {'error': 'Missing required fields: tracking_number, status', 'success': False}
            
            tracking_number = data.get('tracking_number')
            status = data.get('status')
            document_ref = data.get('document_ref')
            
            # Find picking by reference
            picking = request.env['stock.picking'].search([
                ('name', '=', document_ref)
            ], limit=1)
            
            if not picking:
                _logger.warning("[Workflow] Webhook: Picking not found: %s", document_ref)
                return {'error': 'Picking not found', 'document_ref': document_ref, 'success': False}
            
            # Map status to action_type
            action_type_map = {
                'in_transit': 'api_shipment_in_transit',
                'delivered': 'api_shipment_delivered',
                'exception': 'api_shipment_exception',
                'created': 'api_shipment_created',
            }
            
            action_type = action_type_map.get(status, 'api_shipment_created')
            
            # Use service layer for logging
            try:
                from odoo.addons.moombs_workflow_manager.services.action_logger import ActionLogger
                
                action = ActionLogger.log_api_event(
                    request.env,
                    document_type='picking',
                    document_ref=picking.name,
                    res_id=picking.id,
                    api_provider=provider,
                    api_response_id=tracking_number,
                    action_type=action_type,
                    state_to=status,
                    api_webhook_data=json.dumps(data),
                    partner_id=picking.partner_id.id if picking.partner_id else False,
                    company_id=picking.company_id.id,
                    note=f"Webhook from {provider}: {status} - {data.get('location', '')}",
                )
                
                _logger.info("[Workflow] Webhook processed: %s - %s - %s", provider, document_ref, status)
                return {'success': True, 'action_logged': True, 'action_id': action.id if action else None}
                
            except ImportError:
                # Fallback if service layer not available
                action = request.env['document.workflow.action'].create({
                    'document_type': 'picking',
                    'document_ref': picking.name,
                    'res_id': picking.id,
                    'action_type': action_type,
                    'action_source': 'api',
                    'state_to': status,
                    'date_logged': fields.Datetime.now(),
                    'api_provider': provider,
                    'api_response_id': tracking_number,
                    'api_webhook_data': json.dumps(data),
                    'partner_id': picking.partner_id.id if picking.partner_id else False,
                    'company_id': picking.company_id.id,
                    'note': f"Webhook from {provider}: {status}",
                })
                return {'success': True, 'action_logged': True, 'action_id': action.id}
                
        except Exception as e:
            _logger.error("[Workflow] Webhook error: %s", str(e), exc_info=True)
            return {'error': str(e), 'success': False}
    
    @http.route('/workflow/webhook/payment/<provider>', type='json', auth='api_key', methods=['POST'], csrf=False)
    def payment_webhook(self, provider, **kwargs):
        """Handle payment gateway webhooks (Stripe, PayPal, etc.)
        
        Expected payload:
        {
            "payment_id": "pay_1234567890",
            "status": "authorized" | "captured" | "failed",
            "amount": 100.00,
            "currency": "EUR",
            "document_ref": "INV/2025/001",
            "res_id": 123
        }
        """
        try:
            # Rate limiting
            provider_key = f"{provider}_{request.httprequest.remote_addr}"
            if not self._check_rate_limit(provider_key):
                _logger.warning("[Workflow] Rate limit exceeded for %s", provider_key)
                return {'error': 'Rate limit exceeded', 'success': False}
            
            data = request.jsonrequest
            
            # Extract payment information
            payment_id = data.get('payment_id')
            status = data.get('status')
            amount = data.get('amount')
            currency = data.get('currency')
            document_ref = data.get('document_ref')
            res_id = data.get('res_id')
            
            if not payment_id or not status:
                return {'error': 'Missing required fields: payment_id, status', 'success': False}
            
            action_type_map = {
                'authorized': 'api_payment_authorized',
                'captured': 'api_payment_captured',
                'failed': 'api_payment_failed',
            }
            
            action_type = action_type_map.get(status, 'api_payment_authorized')
            
            # Determine document type (default to invoice_out)
            document_type = data.get('document_type', 'invoice_out')
            
            currency_id = False
            if currency:
                currency_record = request.env['res.currency'].search([
                    ('name', '=', currency)
                ], limit=1)
                currency_id = currency_record.id if currency_record else False
            
            # Use service layer for logging
            try:
                from odoo.addons.moombs_workflow_manager.services.action_logger import ActionLogger
                
                action = ActionLogger.log_api_event(
                    request.env,
                    document_type=document_type,
                    document_ref=document_ref or '',
                    res_id=res_id or 0,
                    api_provider=provider,
                    api_response_id=payment_id,
                    action_type=action_type,
                    amount_total=amount,
                    currency_id=currency_id,
                    api_webhook_data=json.dumps(data),
                    note=f"Payment webhook from {provider}: {status}",
                )
                
                _logger.info("[Workflow] Payment webhook processed: %s - %s", provider, status)
                return {'success': True, 'action_logged': True, 'action_id': action.id if action else None}
                
            except ImportError:
                # Fallback
                action = request.env['document.workflow.action'].create({
                    'document_type': document_type,
                    'document_ref': document_ref or '',
                    'res_id': res_id or 0,
                    'action_type': action_type,
                    'action_source': 'api',
                    'date_logged': fields.Datetime.now(),
                    'api_provider': provider,
                    'api_response_id': payment_id,
                    'api_webhook_data': json.dumps(data),
                    'amount_total': amount,
                    'currency_id': currency_id,
                    'note': f"Payment webhook from {provider}: {status}",
                })
                return {'success': True, 'action_logged': True, 'action_id': action.id}
                
        except Exception as e:
            _logger.error("[Workflow] Payment webhook error: %s", str(e), exc_info=True)
            return {'error': str(e), 'success': False}

