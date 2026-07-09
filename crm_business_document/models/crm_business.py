from odoo import fields, models


class CrmBusiness(models.Model):
    _inherit = "crm.business"

    business_document_id = fields.Many2one("documents.document", string="Procedimiento (Documents)")
