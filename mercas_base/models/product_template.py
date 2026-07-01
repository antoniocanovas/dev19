from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    box_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Caja",
        help="Producto de envase utilizado al vender este producto.",
    )
    mercas_box_categ_ids = fields.Many2many(
        comodel_name="product.category",
        compute="_compute_mercas_box_categ_ids",
    )

    @api.depends_context("allowed_company_ids")
    def _compute_mercas_box_categ_ids(self):
        for rec in self:
            rec.mercas_box_categ_ids = rec.env.company.box_categ_ids
