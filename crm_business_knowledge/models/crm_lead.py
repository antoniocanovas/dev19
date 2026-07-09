from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    business_document_page_id = fields.Many2one(
        "document.page",
        string="Procedimiento",
        help="Document Page",
        related="crm_business_id.business_document_page_id",
        store=True,
    )
