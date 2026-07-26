from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class MercasLabelPrintWizard(models.TransientModel):
    _name = "mercas.label.print.wizard"
    _description = "Imprimir etiquetas de producto por caja"

    purchase_id = fields.Many2one(comodel_name="purchase.order", string="Pedido de compra")
    sale_id = fields.Many2one(comodel_name="sale.order", string="Pedido de venta")
    print_format = fields.Selection(
        [
            ("dymo", "Dymo"),
            ("2x7xprice", "2 x 7 con precio"),
            ("4x7xprice", "4 x 7 con precio"),
            ("4x12", "4 x 12"),
            ("4x12xprice", "4 x 12 con precio"),
        ],
        string="Formato",
        default="2x7xprice",
        required=True,
    )
    line_ids = fields.One2many(
        comodel_name="mercas.label.print.wizard.line",
        inverse_name="wizard_id",
        string="Etiquetas",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "line_ids" not in fields_list:
            return res

        order = None
        box_line_field = None
        if res.get("purchase_id"):
            order = self.env["purchase.order"].browse(res["purchase_id"])
            box_line_field = "box_purchase_line_id"
        elif res.get("sale_id"):
            order = self.env["sale.order"].browse(res["sale_id"])
            box_line_field = "box_sale_line_id"
        if not order:
            return res

        lines = order.order_line.filtered(
            lambda l: not l.display_type
            and not l[box_line_field]
            and l.product_id.type == "consu"
            and not l.product_id.is_box
        )
        res["line_ids"] = [
            Command.create({"product_id": line.product_id.id, "quantity": line.box_qty})
            for line in lines
        ]
        return res

    def action_print(self):
        self.ensure_one()
        printable = self.line_ids.filtered(lambda l: l.product_id and l.quantity > 0)
        if not printable:
            raise UserError(
                _("Indica una cantidad de etiquetas mayor que cero en al menos una línea.")
            )

        quantity_by_product = {}
        for line in printable:
            quantity_by_product[line.product_id.id] = (
                quantity_by_product.get(line.product_id.id, 0) + line.quantity
            )

        layout = self.env["product.label.layout"].create({
            "print_format": self.print_format,
            "product_ids": [Command.set(list(quantity_by_product.keys()))],
        })
        xml_id, data = layout._prepare_report_data()
        data["quantity_by_product"] = quantity_by_product
        report_action = self.env.ref(xml_id).report_action(None, data=data, config=False)
        report_action.update({"close_on_report_download": True})
        return report_action


class MercasLabelPrintWizardLine(models.TransientModel):
    _name = "mercas.label.print.wizard.line"
    _description = "Línea de impresión de etiquetas"

    wizard_id = fields.Many2one(
        comodel_name="mercas.label.print.wizard",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(comodel_name="product.product", string="Producto", readonly=True)
    quantity = fields.Integer(string="Etiquetas", default=1)
