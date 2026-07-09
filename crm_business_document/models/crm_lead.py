from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    business_document_id = fields.Many2one(
        "documents.document",
        string="Procedimiento (Documents)",
        related="crm_business_id.business_document_id",
        store=True,
    )
