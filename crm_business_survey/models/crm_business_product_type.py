from odoo import fields, models


class CrmBusinessProductType(models.Model):
    _inherit = "crm.business.product.type"

    survey_ids = fields.Many2many("survey.survey", string="Encuestas")
