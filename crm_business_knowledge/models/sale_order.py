from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    business_document_page_id = fields.Many2one(
        "document.page",
        string="Procedimiento",
        help="Document Page",
        related="opportunity_id.business_document_page_id",
        store=True,
    )
