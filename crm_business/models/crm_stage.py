from odoo import fields, models


class CrmStage(models.Model):
    _inherit = "crm.stage"

    crm_business_ids = fields.Many2many(
        "crm.business",
        relation="crm_business_crm_stage_rel",
        column1="crm_stage_id",
        column2="crm_business_id",
        string="Business Areas",
    )
