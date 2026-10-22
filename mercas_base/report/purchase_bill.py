from odoo import api, fields, models, tools


class PurchaseBillUnion(models.Model):
    _inherit = "purchase.bill.union"
    _rec_names_search = ["name", "reference", "mercas_receipts"]
    # Flushed before reading the view, so that it shows the receipts as they are
    _depends = {
        "stock.picking": ["name", "supplier_ref", "state", "picking_type_id"],
        "stock.picking.type": ["code"],
        "stock.move": ["picking_id", "purchase_line_id"],
        "purchase.order.line": ["order_id"],
    }

    mercas_receipts = fields.Char(
        string="Receipts",
        readonly=True,
        help="Receipts of the purchase order, with the supplier's delivery note.",
    )

    def init(self):
        # The view of purchase (and of any other module) is kept as it is and
        # wrapped to add the receipts (not cancelled) of each purchase order, as
        # "WH/IN/00001 (supplier delivery note), ..."; none for the bills
        super().init()
        cr = self.env.cr
        cr.execute("SELECT pg_get_viewdef('purchase_bill_union'::regclass, true)")
        base_query = cr.fetchone()[0].strip().rstrip(";")
        tools.drop_view_if_exists(cr, "purchase_bill_union")
        cr.execute(f"""
            CREATE OR REPLACE VIEW purchase_bill_union AS (
                SELECT bill_union.*,
                       (SELECT string_agg(
                                   picking.name || COALESCE(' (' || NULLIF(picking.supplier_ref, '') || ')', ''),
                                   ', ' ORDER BY picking.id)
                          FROM stock_picking picking
                          JOIN stock_picking_type picking_type ON picking_type.id = picking.picking_type_id
                         WHERE picking_type.code = 'incoming'
                           AND picking.state != 'cancel'
                           AND picking.id IN (
                               SELECT move.picking_id
                                 FROM stock_move move
                                 JOIN purchase_order_line line ON line.id = move.purchase_line_id
                                WHERE line.order_id = bill_union.purchase_order_id
                           )
                       ) AS mercas_receipts
                  FROM ({base_query}) bill_union
            )""")

    @api.depends("mercas_receipts")
    def _compute_display_name(self):
        super()._compute_display_name()
        for doc in self.filtered("mercas_receipts"):
            # The receipts go with the date, under the reference in the dropdown
            separator = " · " if self.env.context.get("formatted_display_name") else " - "
            doc.display_name = f"{doc.display_name}{separator}{doc.mercas_receipts}"
