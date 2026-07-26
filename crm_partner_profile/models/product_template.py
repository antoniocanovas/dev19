from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    crm_business = fields.Boolean(
        string="Negocio en CRM",
        help="Marca este producto como una solución o servicio propio de "
             "negocio, para que pueda seleccionarse como \"producto o "
             "servicio actual\" en el perfil comercial de un cliente.",
    )
