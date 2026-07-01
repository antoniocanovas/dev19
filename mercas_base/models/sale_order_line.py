from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    box_qty = fields.Integer(
        string="Cajas",
        default=0,
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
