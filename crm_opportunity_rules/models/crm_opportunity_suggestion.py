from odoo import _, fields, models


class CrmOpportunitySuggestion(models.Model):
    _name = "crm.opportunity.suggestion"
    _inherit = ["mail.thread"]
    _description = "Business opportunity suggested by a rule for a client"
    # id as a tie-breaker: several suggestions generated in the same batch
    # (cron, "Generar sugerencias ahora") can share the exact same
    # create_date, which would otherwise leave their relative order
    # undefined between page loads.
    _order = "create_date desc, id desc"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    rule_id = fields.Many2one("crm.opportunity.rule", required=True, ondelete="cascade", index=True)
    rule_domain_description = fields.Text(
        related="rule_id.domain_description", string="Condiciones de la regla"
    )
    product_template_id = fields.Many2one(
        "product.template",
        string="Solución propuesta",
        required=True,
        help="Copiado de la regla en el momento de generarse, para conservar "
             "el histórico aunque la regla cambie después.",
    )
    crm_business_id = fields.Many2one(related="rule_id.crm_business_id", store=True, readonly=True)
    state = fields.Selection(
        [("new", "Nueva"), ("converted", "Convertida"), ("dismissed", "Descartada")],
        default="new",
        required=True,
        tracking=True,
    )
    lead_id = fields.Many2one(
        "crm.lead", string="Oportunidad", readonly=True, copy=False, tracking=True
    )

    _partner_rule_uniq = models.Constraint(
        "unique(partner_id, rule_id)",
        "Ya existe una sugerencia de esta regla para este cliente.",
    )

    def action_convert(self):
        Lead = self.env["crm.lead"]
        Stage = self.env["crm.stage"]
        for suggestion in self.filtered(lambda s: s.state != "converted"):
            business = suggestion.rule_id.crm_business_id
            vals = {
                "name": _(
                    "%(product)s - %(partner)s",
                    product=suggestion.product_template_id.name,
                    partner=suggestion.partner_id.name,
                ),
                "type": "opportunity",
                "partner_id": suggestion.partner_id.id,
                "user_id": suggestion.partner_id.user_id.id,
                "product_template_id": suggestion.product_template_id.id,
            }
            if business:
                vals["crm_business_id"] = business.id
                # crm_business enforces stage_id in crm_business_stage_ids via a
                # constrain checked at create, so the first allowed stage must
                # be resolved up front instead of fixed up after create().
                stages = business.crm_business_stage_ids or Stage.search([])
                first_stage = stages.sorted("sequence")[:1]
                if first_stage:
                    vals["stage_id"] = first_stage.id
            lead = Lead.create(vals)
            suggestion.write({"state": "converted", "lead_id": lead.id})
        if len(self) == 1 and self.lead_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "crm.lead",
                "res_id": self.lead_id.id,
                "view_mode": "form",
                "target": "current",
            }
        return True

    def action_dismiss(self):
        self.filtered(lambda s: s.state == "new").write({"state": "dismissed"})

    def _prune_stale(self):
        """Delete 'new' suggestions whose rule no longer matches the
        partner (e.g. the client's profile changed and the condition, or
        one of its exclusions, no longer holds). Converted/dismissed
        suggestions are left untouched — those already had a human decide
        on them."""
        stale = self.filtered(
            lambda s: s.state == "new" and not s.rule_id._partner_matches(s.partner_id)
        )
        if stale:
            stale.unlink()
        return stale

    def action_view_lead(self):
        self.ensure_one()
        # act_url + target=new opens a real new browser tab at the record's
        # own URL (the standard opportunity form), instead of the act_window
        # + target=new combination, which opens an in-page modal dialog.
        return {
            "type": "ir.actions.act_url",
            "url": f"/odoo/crm.lead/{self.lead_id.id}",
            "target": "new",
        }
