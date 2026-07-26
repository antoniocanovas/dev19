from ast import literal_eval

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmOpportunityRule(models.Model):
    _name = "crm.opportunity.rule"
    _inherit = ["mail.thread"]
    _description = "Rule that suggests a business opportunity from a client's profile"
    _order = "sequence, name"

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    domain = fields.Char(
        string="Condición",
        default="[]",
        required=True,
        tracking=True,
        help="Condición sobre la ficha del cliente (res.partner): sector, "
             "actividad, productos y servicios actuales, facturación, "
             "soluciones ya vendidas... "
             "Se construye con el editor de filtros estándar de Odoo. Para "
             "encadenar reglas ('X + Y => Z'), añade como condición que el "
             "cliente ya tenga la solución X vendida (campo Soluciones vendidas).",
    )
    domain_description = fields.Text(
        string="Descripción de la condición",
        help="Resumen en texto de la condición. El Asistente de condición "
             "la rellena (y la sobrescribe) cada vez que se usa; entre "
             "medias puedes editarla a mano para añadir contexto adicional.",
    )
    product_template_id = fields.Many2one(
        "product.template",
        string="Solución propuesta",
        required=True,
        domain=[("crm_business", "=", True)],
        help="Producto que representa la solución/vertical propuesta. En "
             "cuanto se venda (línea de un pedido confirmado) queda "
             "registrado como \"ya vendida\" en el cliente y esta regla deja "
             "de proponerse de nuevo para él.",
    )
    crm_business_id = fields.Many2one("crm.business", string="Línea de negocio")
    suggestion_ids = fields.One2many("crm.opportunity.suggestion", "rule_id", string="Sugerencias")
    suggestion_count = fields.Integer(compute="_compute_suggestion_count")

    @api.depends("suggestion_ids")
    def _compute_suggestion_count(self):
        for rule in self:
            rule.suggestion_count = len(rule.suggestion_ids)

    @api.constrains("domain")
    def _check_domain(self):
        for rule in self:
            try:
                self.env["res.partner"].search(literal_eval(rule.domain or "[]"), limit=1)
            except Exception as exc:
                raise ValidationError(_("Condición inválida: %(error)s", error=exc)) from exc

    def _get_matching_partners(self, partner_domain=None):
        self.ensure_one()
        if not self.active:
            return self.env["res.partner"]
        domain = literal_eval(self.domain or "[]")
        # Never re-propose a solution the client already bought (confirmed
        # sale) or already has marked as a current product/service in their
        # profile, and never generate a second suggestion of the same rule
        # for the same client.
        domain = domain + [
            ("crm_solution_ids", "not in", [self.product_template_id.id]),
            ("crm_current_product_ids", "not any", [("product_tmpl_id", "=", self.product_template_id.id)]),
            ("id", "not in", self.suggestion_ids.partner_id.ids),
        ]
        if partner_domain:
            domain = domain + partner_domain
        return self.env["res.partner"].search(domain)

    def _partner_matches(self, partner):
        """Whether partner currently satisfies self's condition, regardless
        of any existing suggestion (unlike _get_matching_partners, which
        excludes partners that already have one). Used to detect that a
        'new' suggestion has gone stale after a profile change."""
        self.ensure_one()
        if not self.active:
            return False
        domain = literal_eval(self.domain or "[]")
        domain = domain + [
            ("id", "=", partner.id),
            ("crm_solution_ids", "not in", [self.product_template_id.id]),
            ("crm_current_product_ids", "not any", [("product_tmpl_id", "=", self.product_template_id.id)]),
        ]
        return bool(self.env["res.partner"].search_count(domain))

    def _generate_suggestions(self, partners=None):
        """Evaluate self against partners (or the whole database if not given)
        and create the missing crm.opportunity.suggestion records."""
        Suggestion = self.env["crm.opportunity.suggestion"]
        partner_domain = [("id", "in", partners.ids)] if partners is not None else None
        for rule in self:
            for partner in rule._get_matching_partners(partner_domain):
                Suggestion.create({
                    "partner_id": partner.id,
                    "rule_id": rule.id,
                    "product_template_id": rule.product_template_id.id,
                })

    def _reconcile_suggestions(self):
        """Full re-evaluation after a rule's condition/product/active state
        changed, regardless of the state of its existing suggestions:

        - New/Descartada suggestions that no longer match are deleted.
        - Convertida suggestions that no longer match lose their link to
          the rule (the suggestion is deleted) but the opportunity itself
          is kept, with a chatter note explaining why.
        - Existing open opportunities for the rule's product that aren't
          linked to any suggestion yet, but whose partner now matches, are
          retroactively adopted (linked as Convertida) instead of getting a
          duplicate new suggestion.
        - Everyone else who now matches gets a fresh suggestion, as usual.
        """
        Suggestion = self.env["crm.opportunity.suggestion"].sudo()
        Lead = self.env["crm.lead"].sudo()
        for rule in self:
            for suggestion in Suggestion.search([("rule_id", "=", rule.id)]):
                if rule._partner_matches(suggestion.partner_id):
                    continue
                if suggestion.state == "converted" and suggestion.lead_id:
                    suggestion.lead_id.message_post(body=_(
                        "Esta oportunidad se creó en base a la regla "
                        "%(rule)s que ha cambiado su parametrización y "
                        "ahora no la cumple.",
                        rule=rule.name,
                    ))
                suggestion.unlink()

            linked_partner_ids = Suggestion.search([("rule_id", "=", rule.id)]).partner_id.ids
            candidate_leads = Lead.search([
                ("type", "=", "opportunity"),
                ("product_template_id", "=", rule.product_template_id.id),
                ("partner_id", "not in", linked_partner_ids),
            ])
            adopted_partner_ids = set()
            for lead in candidate_leads:
                partner = lead.partner_id
                if not partner or partner.id in adopted_partner_ids:
                    continue
                if not rule._partner_matches(partner):
                    continue
                Suggestion.create({
                    "partner_id": partner.id,
                    "rule_id": rule.id,
                    "product_template_id": rule.product_template_id.id,
                    "state": "converted",
                    "lead_id": lead.id,
                })
                adopted_partner_ids.add(partner.id)

            rule._generate_suggestions()

    def write(self, vals):
        res = super().write(vals)
        if {"domain", "product_template_id", "active"} & set(vals):
            self._reconcile_suggestions()
        return res

    @api.model
    def _cron_generate_suggestions(self):
        self.search([])._generate_suggestions()
        self.env["crm.opportunity.suggestion"].search([("state", "=", "new")])._prune_stale()

    def action_open_domain_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asistente de condición"),
            "res_model": "crm.opportunity.rule.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_rule_id": self.id},
        }

    def action_generate_suggestions_now(self):
        Suggestion = self.env["crm.opportunity.suggestion"]
        before = Suggestion.search_count([("rule_id", "in", self.ids)])
        self._generate_suggestions()
        after = Suggestion.search_count([("rule_id", "in", self.ids)])
        pruned = Suggestion.search([
            ("rule_id", "in", self.ids), ("state", "=", "new"),
        ])._prune_stale()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sugerencias generadas"),
                "message": _(
                    "%(count)s sugerencia(s) nueva(s) generada(s). "
                    "%(pruned)s sugerencia(s) obsoleta(s) eliminada(s).",
                    count=after - before,
                    pruned=len(pruned),
                ),
                "type": "success",
                "sticky": False,
            },
        }
