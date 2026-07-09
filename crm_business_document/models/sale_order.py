from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    business_document_id = fields.Many2one(
        "documents.document",
        string="Procedimiento (Documents)",
        related="opportunity_id.business_document_id",
        store=True,
    )
