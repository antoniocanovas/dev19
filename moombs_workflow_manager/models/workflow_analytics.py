# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict


class WorkflowAnalytics(models.TransientModel):
    _name = 'workflow.analytics'
    _description = 'Workflow Performance Analytics'
    
    # Computed fields for dashboard display
    avg_fulfillment_time = fields.Float(string="Avg Fulfillment Time", compute="_compute_analytics", store=False)
    on_time_delivery_rate = fields.Float(string="On-Time Delivery Rate", compute="_compute_analytics", store=False)
    avg_payment_time = fields.Float(string="Avg Payment Time", compute="_compute_analytics", store=False)
    api_response_time = fields.Float(string="API Response Time", compute="_compute_analytics", store=False)
    fulfillment_stats = fields.Text(string="Fulfillment Stats", compute="_compute_analytics", store=False)
    transition_stats = fields.Text(string="Transition Stats", compute="_compute_analytics", store=False)
    api_performance = fields.Text(string="API Performance", compute="_compute_analytics", store=False)
    bottleneck_analysis = fields.Text(string="Bottleneck Analysis", compute="_compute_analytics", store=False)
    
    @api.depends_context()
    def _compute_analytics(self):
        """Compute analytics fields - placeholder implementation"""
        for record in self:
            # These will be populated by the action_refresh_analytics method
            record.avg_fulfillment_time = 0.0
            record.on_time_delivery_rate = 0.0
            record.avg_payment_time = 0.0
            record.api_response_time = 0.0
            record.fulfillment_stats = ""
            record.transition_stats = ""
            record.api_performance = ""
            record.bottleneck_analysis = ""
    
    def action_refresh_analytics(self):
        """Refresh analytics data"""
        # This method will be called by the button
        # For now, just recompute the fields
        self._compute_analytics()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Analytics Refreshed',
                'message': 'Analytics data has been refreshed.',
                'type': 'success',
            }
        }
    
    def get_order_fulfillment_time(self, date_from, date_to):
        """Calculate average time from order confirmation to delivery
        
        Returns:
            dict: Statistics with avg, min, max, median fulfillment times
        """
        confirmed = self.env['document.workflow.action'].search([
            ('action_type', '=', 'order_confirmed'),
            ('date_logged', '>=', date_from),
            ('date_logged', '<=', date_to),
            ('is_archived', '=', False),
        ])
        
        delivered = self.env['document.workflow.action'].search([
            ('action_type', '=', 'delivery_validated'),
            ('date_logged', '>=', date_from),
            ('date_logged', '<=', date_to),
            ('is_archived', '=', False),
        ])
        
        # Match confirmed orders to deliveries by document_ref
        fulfillment_times = []
        confirmed_by_ref = {c.document_ref: c for c in confirmed}
        
        for delivery in delivered:
            if delivery.document_ref in confirmed_by_ref:
                confirmed_action = confirmed_by_ref[delivery.document_ref]
                duration = (delivery.date_logged - confirmed_action.date_logged).total_seconds()
                if duration > 0:
                    fulfillment_times.append(duration)
        
        if not fulfillment_times:
            return {
                'avg': 0,
                'min': 0,
                'max': 0,
                'median': 0,
                'count': 0,
            }
        
        fulfillment_times.sort()
        count = len(fulfillment_times)
        
        return {
            'avg': sum(fulfillment_times) / count,
            'min': min(fulfillment_times),
            'max': max(fulfillment_times),
            'median': fulfillment_times[count // 2] if count > 0 else 0,
            'count': count,
        }
    
    def get_state_transition_stats(self, document_type):
        """Analyze state transition patterns
        
        Returns:
            dict: Transition matrix and statistics
        """
        transitions = self.env['document.workflow.action'].read_group(
            [
                ('document_type', '=', document_type),
                ('action_type', '=', 'state_change'),
                ('is_archived', '=', False),
            ],
            ['state_from', 'state_to'],
            ['state_from', 'state_to'],
        )
        
        # Build transition matrix
        transition_matrix = defaultdict(lambda: defaultdict(int))
        for transition in transitions:
            state_from = transition.get('state_from', 'None')
            state_to = transition.get('state_to', 'None')
            count = transition.get('__count', 0)
            transition_matrix[state_from][state_to] = count
        
        # Identify most common paths
        common_paths = []
        for state_from, to_states in transition_matrix.items():
            for state_to, count in to_states.items():
                common_paths.append({
                    'from': state_from,
                    'to': state_to,
                    'count': count,
                })
        common_paths.sort(key=lambda x: x['count'], reverse=True)
        
        return {
            'transition_matrix': dict(transition_matrix),
            'common_paths': common_paths[:10],  # Top 10
            'total_transitions': sum(sum(to_states.values()) for to_states in transition_matrix.values()),
        }
    
    def get_api_performance(self, api_provider, date_from, date_to):
        """Analyze external API performance
        
        Returns:
            dict: Performance metrics
        """
        api_actions = self.env['document.workflow.action'].search([
            ('api_provider', '=', api_provider),
            ('action_source', '=', 'api'),
            ('date_logged', '>=', date_from),
            ('date_logged', '<=', date_to),
            ('is_archived', '=', False),
        ])
        
        if not api_actions:
            return {
                'total_requests': 0,
                'by_action_type': {},
                'avg_duration': 0,
            }
        
        by_action_type = defaultdict(int)
        durations = []
        
        for action in api_actions:
            by_action_type[action.action_type] += 1
            if action.duration_seconds:
                durations.append(action.duration_seconds)
        
        return {
            'total_requests': len(api_actions),
            'by_action_type': dict(by_action_type),
            'avg_duration': sum(durations) / len(durations) if durations else 0,
            'min_duration': min(durations) if durations else 0,
            'max_duration': max(durations) if durations else 0,
        }
    
    def get_bottleneck_analysis(self, document_type=None):
        """Identify workflow bottlenecks
        
        Returns:
            dict: Bottleneck analysis
        """
        domain = [('is_archived', '=', False)]
        if document_type:
            domain.append(('document_type', '=', document_type))
        
        actions = self.env['document.workflow.action'].search(domain, order='date_logged asc')
        
        # Group by document and calculate time in each state
        document_states = defaultdict(list)
        for action in actions:
            if action.action_type == 'state_change' and action.state_to:
                document_states[action.document_ref].append({
                    'state': action.state_to,
                    'date': action.date_logged,
                })
        
        # Calculate time in each state
        state_durations = defaultdict(list)
        for doc_ref, states in document_states.items():
            for i in range(len(states) - 1):
                current_state = states[i]['state']
                next_date = states[i + 1]['date']
                current_date = states[i]['date']
                duration = (next_date - current_date).total_seconds()
                state_durations[current_state].append(duration)
        
        # Calculate averages
        avg_durations = {}
        for state, durations in state_durations.items():
            if durations:
                avg_durations[state] = sum(durations) / len(durations)
        
        # Sort by average duration (longest first = bottleneck)
        bottlenecks = sorted(avg_durations.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'avg_time_by_state': dict(avg_durations),
            'bottlenecks': bottlenecks[:5],  # Top 5 bottlenecks
        }

