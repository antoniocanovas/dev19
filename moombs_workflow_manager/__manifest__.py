# -*- coding: utf-8 -*-
{
    'name': 'MOOMBS Workflow Manager',
    'version': '19.0.1.0.0',
    'category': 'Operations',
    'summary': 'Comprehensive workflow action tracking and analytics',
    'description': """
MOOMBS Workflow Manager
=======================

Unified action tracking system for all operational documents:
- State change tracking (SO, PO, Invoices, Pickings, POS Orders)
- External API event logging (shipping, payments)
- Customer-facing wish list timeline
- Operational analytics and KPIs
- Performance monitoring

**Features:**
- Automatic logging via base automation
- API webhook framework for external integrations
- Customer portal integration
- Analytics dashboard with KPIs
- Data archiving for scalability
    """,
    'author': 'MOOMBS',
    'website': 'https://moombs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'base_automation',
        'mail',
        'portal',
        'sale',          # For sale.order extensions
        'purchase',      # For purchase.order extensions
        'stock',         # For stock.picking extensions
        'account',       # For account.move extensions
        'point_of_sale', # For pos.order extensions
        'moombs_list',   # Gift list integration
    ],
    'external_dependencies': {
        'python': ['json'],
    },
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/ir.rule.xml',
        # Data
        'data/workflow_config.xml',
        # Note: base_automation.xml removed - using method overrides instead
        'data/email_templates.xml',
        # Views
        'views/document_workflow_action_views.xml',
        # 'views/document_smart_buttons.xml',  # Hidden - workflow tracking focused on gift list tab
        'views/workflow_analytics_views.xml',
        'views/workflow_config_views.xml',
        'views/customer_portal_views.xml',
        'views/gift_list_workflow_tab.xml',
        # Wizards (must be before menus that reference them)
        'wizards/archive_wizard_views.xml',
        # Menus (must be after all actions/views are defined)
        'views/menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {
        'web.assets_backend': [
            'moombs_workflow_manager/static/src/css/workflow_manager.css',
        ],
    },
}

