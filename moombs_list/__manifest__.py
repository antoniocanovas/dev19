# -*- coding: utf-8 -*-
{
    'name': 'MOOMBS Lists',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Baby gift registry and gift lists management',
    'description': """
MOOMBS Lists - Baby Gift Registry
==================================

Enables store advisors to create and manage baby gift lists.
Features:
- Gift list creation and management
- eWallet integration for family contributions
- Full traceability of orders, payments, deliveries
- Beneficiary-sovereign decision making
- POS "Paid By" popup for eWallet topups

**Business Rules:**
- 25% wallet balance required to order
- 100% eWallet payment only
- One line = one unit (qty=1)
- Lines cannot be edited, only cancelled
    """,
    'author': 'MOOMBS',
    'website': 'https://moombs.com',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'stock',
        'product',
        'loyalty',
        'mail',
        'point_of_sale',
        'pos_loyalty',
    ],
    'data': [
        # Security
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        # Data
        'data/sequences.xml',
        'data/stock_locations.xml',
        # Views
        'views/baby_list_views.xml',
        'views/wizard_views.xml',
        'views/pos_order_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        # Reports
        'report/wallet_receipt_report.xml',
        'report/wallet_receipt_template.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'moombs_list/static/src/js/pos_store_extension.js',
            'moombs_list/static/src/js/order_extension.js',
            'moombs_list/static/src/js/paid_by_popup.js',
            'moombs_list/static/src/js/payment_screen_extension.js',
            'moombs_list/static/src/js/product_screen_extension.js',
            'moombs_list/static/src/xml/paid_by_popup_template.xml',
            'moombs_list/static/src/xml/payment_screen_override.xml',
            'moombs_list/static/src/xml/order_receipt_extension.xml',
            'moombs_list/static/src/css/paid_by_popup.css',
        ],
        'point_of_sale.assets_prod': [
            'moombs_list/static/src/js/pos_control_buttons_extension.js',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
