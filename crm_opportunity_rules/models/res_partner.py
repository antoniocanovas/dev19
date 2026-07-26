from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    crm_solution_ids = fields.Many2many(
        "product.template",
        string="Soluciones vendidas",
        compute="_compute_crm_solution_ids",
        store=True,
        help="Productos de líneas de pedidos de venta confirmados de este "
             "cliente. Sirve para no repetir una propuesta ya vendida y para "
             "encadenar reglas ('si ya tiene X, proponer Y').",
    )
    crm_suggestion_ids = fields.One2many(
        "crm.opportunity.suggestion", "partner_id", string="Recomendaciones de venta"
    )
    crm_new_suggestion_count = fields.Integer(compute="_compute_crm_new_suggestion_count")

    @api.depends("sale_order_ids.state", "sale_order_ids.order_line.product_id.product_tmpl_id")
    def _compute_crm_solution_ids(self):
        for partner in self:
            confirmed_lines = partner.sale_order_ids.filtered(lambda o: o.state == "sale").order_line
            partner.crm_solution_ids = confirmed_lines.product_id.product_tmpl_id

    @api.depends("crm_suggestion_ids.state")
    def _compute_crm_new_suggestion_count(self):
        for partner in self:
            partner.crm_new_suggestion_count = len(
                partner.crm_suggestion_ids.filtered(lambda s: s.state == "new")
            )

    # Fields that, when saved on the client card, may open up a new rule
    # match: re-evaluate immediately instead of waiting for the nightly cron.
    # crm_solution_ids is deliberately not covered here: it changes through
    # the sale order confirmation, not through res.partner.write(vals), so
    # its chaining effect (e.g. "Vertical Mercas" sold => "NIS2" applies) is
    # picked up by the nightly cron instead.
    _CRM_PROFILE_TRIGGER_FIELDS = {
        "crm_profile_line_ids", "crm_current_product_ids",
    }

    def write(self, vals):
        res = super().write(vals)
        if self._CRM_PROFILE_TRIGGER_FIELDS & set(vals):
            self.env["crm.opportunity.rule"].sudo().search([])._generate_suggestions(self)
            # The same profile change that may open up a new match can also
            # close one: e.g. a client had "ERP Odoo" and got suggested
            # "RRHH Odoo", but now also has "Factorial" for HR — the rule's
            # exclusion no longer holds, so that suggestion is stale.
            self.env["crm.opportunity.suggestion"].sudo().search([
                ("partner_id", "in", self.ids), ("state", "=", "new"),
            ])._prune_stale()
        return res

    def action_view_crm_suggestions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Recomendaciones de venta"),
            "res_model": "crm.opportunity.suggestion",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }
