from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    crm_business_product_type_id = fields.Many2one(
        "crm.business.product.type", string="Tipo de producto"
    )
