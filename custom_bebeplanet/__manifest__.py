{
    'name': 'Custom Bebeplanet - Advanced Warehouse Automation',
    'version': '19.0.2.0.0',
    'summary': 'Automates picking splits for salespersons and consolidates PO references.',
    'author': 'Bebeplanet',
    'category': 'Inventory/Automation',
    'depends': [
        'stock',
        'sale_management',
        'point_of_sale',
        'base_automation',
        'purchase',
    ],
    'data': [
        # Se quita porque Khalil ha simplificado o lo hará en su desarrollo
        #'data/ir_actions_server_data.xml',
        'views/stock_picking_view.xml',
    ],
    'installable': True,
    'application': False,
    'description': """
# Advanced Warehouse Automation for Bebeplanet

This module introduces two key automation features to streamline warehouse and purchasing workflows.

## 1. Automated Picking Split for Salespersons

- **Real-time Splitting:** When an outgoing picking is created from a Sale Order or PoS Order, an automated rule triggers.
- **Internal Transfers:** If the salesperson has a dedicated stock location (identified by their partner reference `ref`), the system creates an internal transfer to move the required stock from the main warehouse (`WH/Stock`) to the salesperson's location.
- **Chained Pickings:** The original outgoing picking is then chained to this new internal transfer, ensuring products are moved to the salesperson before final delivery.
- **MTO Handling:** The logic correctly handles both stockable and Make-To-Order (MTO) products.

## 2. Purchase Order Reference Consolidation

- **`partner_ref` Field:** Adds a new "Partner Reference" field to all stock pickings (receipts).
- **Automatic Consolidation:** When a receipt associated with a Purchase Order is validated or its `partner_ref` is edited, this module automatically updates a new `partner_ref` field on the Purchase Order itself.
- **Enhanced Search:** The PO's `partner_ref` field consolidates all unique references from its related receipts, plus any manually entered terms. This makes it possible to find a Purchase Order from a Vendor Bill by searching for any of its receipt references.
    """,
}
