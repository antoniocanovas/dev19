{
    'name': 'Custom Bebeplanet - Automated Picking Split',
    'version': '19.0.1.0.0',
    'summary': 'Automates the creation of internal transfers for salespersons.',
    'description': """
        This module replaces the old cron job with a real-time automated action.
        When an outgoing picking is created, it triggers a rule that:
        1. Finds the salesperson associated with the order.
        2. Creates an internal transfer to the salesperson's specific stock location.
        3. Chains the original picking to wait for this new internal transfer.
    """,
    'author': 'Bebeplanet',
    'category': 'Inventory/Automation',
    'depends': [
        'stock',
        'sale_management',
        'point_of_sale',
        'base_automation',
    ],
    'data': [
        'data/ir_actions_server_data.xml',
        'data/base_automation_data.xml',
    ],
    'installable': True,
    'application': False,
}
