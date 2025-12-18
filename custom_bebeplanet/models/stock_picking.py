# -*- coding: utf-8 -*-

from odoo import models, fields

class StockPicking(models.Model):
    """
    Extends stock.picking to add custom automation features:
    1. A 'partner_ref' field for external references.
    2. Logic to automatically update a related Purchase Order with consolidated references
       upon validation or modification of a picking.
    """
    _inherit = 'stock.picking'

    # == Fields ==
    partner_ref = fields.Char(
        string="Partner Reference",
        copy=False,
        help="External reference, typically from a supplier or for a specific delivery. "
             "This field is used to consolidate references on the Purchase Order."
    )

    # == Private Methods ==
    def _update_purchase_order_partner_ref(self):
        """
        Private helper method to recalculate and update the partner_ref on related purchase orders.
        
        This method is triggered by `button_validate` and `write`. It ensures that the
        `partner_ref` field on a Purchase Order becomes a searchable, consolidated string
        of all relevant references from its associated pickings.

        The final string is ordered as follows:
        1. Manually entered terms (preserved from previous values).
        2. All unique `partner_ref` values from all related pickings.
        """
        # Use mapped() to get a clean recordset of unique purchase orders to process.
        purchase_orders_to_update = self.mapped('purchase_id')

        for po in purchase_orders_to_update:
            # 1. Get all pickings related to this PO and their unique, non-empty partner_ref values.
            all_pickings = po.picking_ids
            picking_partner_refs = set(p.partner_ref for p in all_pickings if p.partner_ref)

            # 2. Get the current terms from the PO's partner_ref to identify manual entries.
            current_po_ref_terms = set()
            if po.partner_ref:
                current_po_ref_terms = set(po.partner_ref.split(' '))

            # 3. Identify manual terms by finding what's in the PO's ref but not in the picking refs.
            # This preserves any text entered directly on the Purchase Order.
            manual_terms = current_po_ref_terms - picking_partner_refs
            
            # 4. Build the final list in the correct order: manual terms first, then picking refs.
            sorted_manual_terms = sorted(list(manual_terms))
            sorted_picking_refs = sorted(list(picking_partner_refs))

            all_terms_ordered = sorted_manual_terms + sorted_picking_refs

            # 5. Write the consolidated, space-separated string back to the PO's partner_ref field.
            # This makes the PO searchable by any of these terms from a vendor bill.
            po.partner_ref = ' '.join(all_terms_ordered)

    # == Action Methods ==
    def button_validate(self):
        """
        Overrides the standard validation button.
        After standard validation, it triggers the consolidation of partner references
        onto the related purchase order.
        """
        res = super(StockPicking, self).button_validate()
        self._update_purchase_order_partner_ref()
        return res

    # == ORM Overrides ==
    def write(self, vals):
        """
        Overrides the standard write method.
        If the 'partner_ref' field of a validated picking is changed, it triggers
        the consolidation logic again to ensure the PO is always up-to-date.
        """
        res = super(StockPicking, self).write(vals)
        # Check if 'partner_ref' was modified in the update.
        if 'partner_ref' in vals:
            # To optimize, run the logic only on pickings that are 'done' and linked to a PO.
            validated_pickings_with_po = self.filtered(lambda p: p.state == 'done' and p.purchase_id)
            if validated_pickings_with_po:
                validated_pickings_with_po._update_purchase_order_partner_ref()
        return res
