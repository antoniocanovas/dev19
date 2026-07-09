from odoo import fields, models


class CrmBusiness(models.Model):
    _inherit = "crm.business"

    business_document_page_id = fields.Many2one(
        "document.page", string="Procedimiento", help="Document Page",
    )
