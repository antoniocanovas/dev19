from odoo import fields, models


class CrmBusiness(models.Model):
    _name = "crm.business"
    _description = "Business type"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    hr_department_id = fields.Many2one("hr.department", string="Departamento")
    manager_user_id = fields.Many2one(
        "res.users",
        string="Jefe departamento",
        related="hr_department_id.manager_id.user_id",
        store=True,
        readonly=True,
    )
    presale_user_id = fields.Many2one("res.users", string="Preventa")
    controller_user_id = fields.Many2one(
        "res.users",
        string="Validador",
        domain=lambda self: [("group_ids", "in", self.env.ref("purchase.group_purchase_manager").id)],
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    annual_target = fields.Monetary(string="Objetivo anual", currency_field="currency_id")
    crm_business_stage_ids = fields.Many2many("crm.stage", string="Etapas")
    business_procedure = fields.Char(string="Procedimiento")
    note = fields.Html(
        string="Nota",
        help="Lo que escribas aquí se añadirá automáticamente a los comentarios "
             "de las oportunidades de esta línea de negocio.",
    )
