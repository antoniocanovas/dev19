from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_box = fields.Boolean(
        string="Es caja/envase",
        help="Marca este producto como caja o envase: se usa para detectar "
             "pedidos de devolución/entrega de cajas y para excluirlo de la "
             "impresión de etiquetas y del cálculo de cajas en ubicaciones.",
    )
    box_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Caja",
        help="Producto de envase utilizado al vender este producto.",
        domain=[("is_box", "=", True)],
    )

    def _mercas_any_box_product_exists(self):
        return bool(self.env["product.template"].search_count(
            [("is_box", "=", True)], limit=1
        ))
