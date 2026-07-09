from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    crm_business_id = fields.Many2one(
        "crm.business",
        string="Línea de negocio",
        compute="_compute_crm_business_id",
        store=True,
        readonly=False,
        precompute=True,
    )
    presale_user_id = fields.Many2one(
        "res.users",
        string="Preventa",
        related="opportunity_id.presale_user_id",
        store=True,
    )
    manager_user_id = fields.Many2one(
        "res.users",
        string="Jefe departamento",
        related="opportunity_id.manager_user_id",
        store=True,
    )
    controller_user_id = fields.Many2one(
        "res.users",
        string="Validador",
        related="opportunity_id.controller_user_id",
        store=True,
    )
    crm_business_stage_ids = fields.Many2many(
        "crm.stage",
        string="Etapas de la línea de negocio",
        related="opportunity_id.crm_business_stage_ids",
    )
    hr_department_id = fields.Many2one(
        "hr.department",
        string="Departamento",
        related="opportunity_id.hr_department_id",
        store=True,
    )

    @api.depends("opportunity_id")
    def _compute_crm_business_id(self):
        for order in self:
            if order.opportunity_id:
                order.crm_business_id = order.opportunity_id.crm_business_id
