from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    crm_business_id = fields.Many2one("crm.business", string="Línea de negocio")
    presale_user_id = fields.Many2one(
        "res.users",
        string="Preventa",
        compute="_compute_presale_user_id",
        store=True,
        readonly=False,
        precompute=True,
    )
    manager_user_id = fields.Many2one(
        "res.users",
        string="Jefe departamento",
        related="crm_business_id.manager_user_id",
        store=True,
    )
    controller_user_id = fields.Many2one(
        "res.users",
        string="Validador",
        compute="_compute_controller_user_id",
        store=True,
        readonly=False,
        precompute=True,
        domain=lambda self: [("group_ids", "in", self.env.ref("purchase.group_purchase_manager").id)],
    )
    crm_business_stage_ids = fields.Many2many(
        "crm.stage",
        string="Etapas de la línea de negocio",
        related="crm_business_id.crm_business_stage_ids",
    )
    hr_department_id = fields.Many2one(
        "hr.department",
        string="Departamento",
        related="crm_business_id.hr_department_id",
        store=True,
    )
    business_procedure = fields.Char(
        string="Procedimiento",
        related="crm_business_id.business_procedure",
        store=True,
    )
    crm_business_allowed_stage_ids = fields.Many2many(
        "crm.stage",
        string="Etapas permitidas",
        compute="_compute_crm_business_allowed_stage_ids",
    )

    @api.depends("crm_business_id")
    def _compute_presale_user_id(self):
        for lead in self:
            if lead.crm_business_id:
                lead.presale_user_id = lead.crm_business_id.presale_user_id

    @api.depends("crm_business_id")
    def _compute_controller_user_id(self):
        for lead in self:
            if lead.crm_business_id:
                lead.controller_user_id = lead.crm_business_id.controller_user_id

    @api.depends("crm_business_stage_ids")
    def _compute_crm_business_allowed_stage_ids(self):
        all_stages = self.env["crm.stage"].search([])
        for lead in self:
            lead.crm_business_allowed_stage_ids = lead.crm_business_stage_ids or all_stages

    @api.constrains("stage_id", "crm_business_id")
    def _check_crm_business_stage(self):
        for lead in self:
            if lead.type == "opportunity" and lead.crm_business_stage_ids \
                    and lead.stage_id not in lead.crm_business_stage_ids:
                raise ValidationError(_(
                    "La etapa «%(stage)s» no está permitida para la línea de negocio «%(crm_business)s».",
                    stage=lead.stage_id.name,
                    crm_business=lead.crm_business_id.name,
                ))

    def _get_first_crm_business_stage(self):
        self.ensure_one()
        stages = self.crm_business_stage_ids or self.env["crm.stage"].search([])
        return stages.sorted("sequence")[:1]

    def _append_crm_business_note(self):
        """ Add the business area's note to the opportunity's own comments. """
        for lead in self:
            note = lead.crm_business_id.note
            if note:
                lead.description = (lead.description or "") + note

    _CRM_BUSINESS_RESPONSIBLE_FIELDS = ("presale_user_id", "manager_user_id", "controller_user_id")

    def _subscribe_crm_business_responsibles(self, previous_users=None):
        """ Add presale/manager/controller as followers, either because they were
        just (re)assigned or because the opportunity left its first stage. """
        for lead in self.filtered(lambda l: l.type == "opportunity"):
            partners = self.env["res.partner"]
            for fname in self._CRM_BUSINESS_RESPONSIBLE_FIELDS:
                user = lead[fname]
                if not user:
                    continue
                if previous_users is None or user != previous_users.get((lead.id, fname)):
                    partners |= user.partner_id
            if partners:
                lead.message_subscribe(partner_ids=partners.ids)

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads._subscribe_crm_business_responsibles()
        leads.filtered("crm_business_id")._append_crm_business_note()
        return leads

    def write(self, vals):
        opportunities = self.filtered(lambda l: l.type == "opportunity")
        previous_users = {
            (lead.id, fname): lead[fname]
            for lead in opportunities
            for fname in self._CRM_BUSINESS_RESPONSIBLE_FIELDS
        }

        res = super().write(vals)

        # Newly assigned or reassigned preventa/jefe/validador become followers.
        opportunities._subscribe_crm_business_responsibles(previous_users)

        # Leaving the first stage of the business line re-notifies all three responsibles.
        if "stage_id" in vals:
            for lead in opportunities:
                first_stage = lead._get_first_crm_business_stage()
                if first_stage and lead.stage_id != first_stage:
                    partners = (
                        lead.presale_user_id.partner_id
                        | lead.manager_user_id.partner_id
                        | lead.controller_user_id.partner_id
                    )
                    if partners:
                        lead.message_subscribe(partner_ids=partners.ids)

        # Business area (re)assigned: append its note to the opportunity's comments.
        if "crm_business_id" in vals:
            self.filtered("crm_business_id")._append_crm_business_note()

        return res
