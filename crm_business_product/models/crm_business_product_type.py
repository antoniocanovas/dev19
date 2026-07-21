from odoo import fields, models


class CrmBusinessProductType(models.Model):
    _name = "crm.business.product.type"
    _description = "Product type"
    _order = "name"

    name = fields.Char(required=True)
    attribute_ids = fields.Many2many("product.attribute", string="Atributos")
