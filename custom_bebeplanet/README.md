# Custom Bebeplanet - Advanced Warehouse Automation

This Odoo module introduces significant automation and usability improvements for warehouse and purchasing workflows, tailored for Bebeplanet's operational needs.

## Features

### 1. Automated Picking Split for Salespersons

This feature automates the process of supplying stock to salespersons who have their own dedicated stock locations.

#### Workflow:
1.  **Trigger:** An automated rule runs whenever an outgoing picking is created from a Sale Order or a Point of Sale order.
2.  **Salesperson Location:** The system checks if the salesperson associated with the order has a specific stock location. This is identified by a reference code (`ref`) on the salesperson's contact (`res.partner`). The location must have a matching name.
3.  **Internal Transfer:** If a location is found, a new internal transfer is automatically created to move the required products from the main warehouse (`WH/Stock`) to the salesperson's location.
4.  **Chaining:** The original outgoing picking is put on hold and "chained" to the new internal transfer. This ensures that the final delivery to the customer can only proceed after the salesperson has received the stock.
5.  **MTO Support:** The logic correctly handles both standard stockable products and Make-To-Order (MTO) products, ensuring the correct warehouse operations are performed for each.

#### Configuration:
-   Ensure your main stock location is named `WH/Stock`.
-   For each salesperson, create a dedicated stock location (e.g., under `WH/Commercials/`).
-   On the salesperson's contact form (the `res.partner` linked to their `res.users`), set the `ref` field to match the name of their stock location.
-   The automated rule is configured via **Settings > Technical > Automation > Automated Actions** and is named "Auto-Split: Trigger for Outgoing Pickings".

### 2. Purchase Order Reference Consolidation

This feature dramatically improves the process of matching vendor bills to purchase orders by making POs searchable by their delivery references.

#### Workflow:
1.  **New Field:** A new text field, **"Partner Reference"** (`partner_ref`), is added to all stock pickings (receipts). This field is intended for entering supplier delivery note numbers or other external references.
2.  **Automatic Consolidation:** When a receipt linked to a Purchase Order is validated, or when its `partner_ref` field is edited later, an automation triggers.
3.  **PO Update:** The automation collects all unique `partner_ref` values from all receipts associated with that Purchase Order. It also preserves any text that was manually entered into the PO's own `partner_ref` field.
4.  **Consolidated String:** It then writes a space-separated string containing all these references into the `partner_ref` field of the Purchase Order.

#### How It Solves a Problem:
-   When creating a vendor bill, you can now find the corresponding Purchase Order by typing **any of its delivery references** into the "Purchase Order" field. Odoo's standard search will find the PO because the reference is now part of its `partner_ref` field.

## Technical Details

-   **Models Extended:**
    -   `stock.picking`: Adds the `partner_ref` field and the core logic in `button_validate` and `write` methods.
-   **Views:**
    -   The `partner_ref` field is added to the stock picking form for easy access.
-   **Automation:**
    -   An `ir.actions.server` contains the Python code for the salesperson picking split.
    -   An `ir.ui.view` adds the field to the form.

---
Developed for Bebeplanet.
