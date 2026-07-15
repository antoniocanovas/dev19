from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    box_qty = fields.Integer(
        string="Cajas",
        compute="_compute_box_qty",
        store=True,
        readonly=False,
    )
    box_sale_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Línea de producto",
        ondelete="cascade",
        copy=False,
        index=True,
    )
    box_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Caja",
        compute="_compute_box_product_id",
        store=True,
        readonly=False,
    )

    @api.depends("product_id", "product_uom_id", "product_uom_qty")
    def _compute_box_qty(self):
        for line in self:
            if line.product_uom_id and line.product_uom_id in line.product_id.uom_ids:
                line.box_qty = line.product_uom_qty
            else:
                line.box_qty = line.box_qty

    @api.depends("product_id")
    def _compute_box_product_id(self):
        for line in self:
            if line.display_type or line.box_sale_line_id:
                line.box_product_id = False
            else:
                line.box_product_id = line.product_id.product_tmpl_id.box_product_id

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        if self.lot_id:
            vals["lot_id"] = self.lot_id.id
        return vals

    def get_available_lots_for_line(self):
        result = super().get_available_lots_for_line()
        if not result or not result.get("available"):
            return result

        invoiced_lot_ids = set(
            self.env["stock.lot"]
            .search(
                [
                    ("id", "in", [item["id"] for item in result["available"]]),
                    ("supplier_invoice_id", "!=", False),
                ]
            )
            .ids
        )
        if invoiced_lot_ids:
            result["available"] = [
                item
                for item in result["available"]
                if item["id"] not in invoiced_lot_ids
            ]
        return result

    def write(self, vals):
        result = super().write(vals)
        if "box_qty" in vals or "box_product_id" in vals or "product_id" in vals:
            for line in self.filtered(lambda l: not l.display_type and not l.box_sale_line_id):
                box_lines = self.env["sale.order.line"].search(
                    [("box_sale_line_id", "=", line.id)]
                )
                if not box_lines:
                    continue
                if "box_qty" in vals and line.box_qty == 0:
                    box_lines.unlink()
                    continue
                update = {}
                if "box_qty" in vals:
                    update["product_uom_qty"] = line.box_qty
                if ("box_product_id" in vals or "product_id" in vals) and line.box_product_id:
                    update["product_id"] = line.box_product_id.id
                if update:
                    box_lines.write(update)
        return result
