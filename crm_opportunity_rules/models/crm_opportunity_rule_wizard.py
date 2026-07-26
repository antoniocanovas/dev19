from odoo import _, fields, models

# Duplicated on purpose from crm.partner.current_product (state/provider):
# a wizard line has no partner yet, so it can't relate to that model's own
# selection fields directly. Keep both lists in sync if they ever change.
_STATE_SELECTION = [
    ("1_ok", "Vigente - Ok"),
    ("2_to_evolve", "Vigente - A evolucionar"),
    ("3_to_change", "Vigente - A cambiar"),
    ("4_stopped", "Parado / sin uso"),
    ("5_obsolete", "Obsoleto"),
]
_PROVIDER_SELECTION = [
    ("internal", "Interno"),
    ("us", "Nosotros"),
    ("competitor", "Competencia"),
    ("multiple", "Varios"),
]

class CrmOpportunityRuleWizard(models.TransientModel):
    _name = "crm.opportunity.rule.wizard"
    _description = "Assistant to build a crm.opportunity.rule condition"

    rule_id = fields.Many2one("crm.opportunity.rule", required=True, ondelete="cascade")
    required_value_ids = fields.Many2many(
        "crm.partner.attribute.value",
        "crm_opportunity_rule_wizard_required_value_rel",
        "wizard_id", "value_id",
        string="Propiedades a cumplir del perfil de negocio",
    )
    excluded_value_ids = fields.Many2many(
        "crm.partner.attribute.value",
        "crm_opportunity_rule_wizard_excluded_value_rel",
        "wizard_id", "value_id",
        string="Propiedades excluyentes del perfil de negocio",
    )
    required_product_ids = fields.One2many(
        "crm.opportunity.rule.wizard.product.line", "required_wizard_id",
        string="Productos/servicios que ha de tener el cliente",
    )
    excluded_product_ids = fields.One2many(
        "crm.opportunity.rule.wizard.product.line", "excluded_wizard_id",
        string="Productos/servicios que no ha de tener el cliente",
    )

    def action_apply(self):
        self.ensure_one()
        domain = []
        # The domain widget's value editor for many2many/one2many fields only
        # supports the '=' / '!=' operators (not 'in' / 'not in'), and expects
        # the value as a list of ids even for a single id — otherwise it shows
        # the raw id with a "Value not supported" warning instead of the name.
        for value in self.required_value_ids:
            domain.append(("crm_profile_line_ids.value_ids", "=", [value.id]))
        for value in self.excluded_value_ids:
            # NOT a dotted 'crm_profile_line_ids.value_ids' != [id]: on a
            # client with NO profile lines at all, that incorrectly excludes
            # them too (verified) instead of matching them (they trivially
            # don't have the excluded value). 'not any' handles the
            # no-lines-at-all case correctly.
            domain.append(("crm_profile_line_ids", "not any", [("value_ids", "=", [value.id])]))
        for line in self.required_product_ids:
            domain.append(("crm_current_product_ids", "any", line._build_subdomain()))
        for line in self.excluded_product_ids:
            domain.append(("crm_current_product_ids", "not any", line._build_subdomain()))
        self.rule_id.write({
            "domain": str(domain),
            "domain_description": self._build_description(),
        })
        return {"type": "ir.actions.act_window_close"}

    def _build_description(self):
        self.ensure_one()
        lines = []
        if self.required_value_ids:
            lines.append(_(
                "Cumple: %(values)s.",
                values=", ".join(self.required_value_ids.mapped("name")),
            ))
        if self.excluded_value_ids:
            lines.append(_(
                "Excluye: %(values)s.",
                values=", ".join(self.excluded_value_ids.mapped("name")),
            ))
        if self.required_product_ids:
            lines.append(_(
                "Ha de tener: %(items)s.",
                items="; ".join(self.required_product_ids.mapped(lambda l: l._describe())),
            ))
        if self.excluded_product_ids:
            lines.append(_(
                "No ha de tener: %(items)s.",
                items="; ".join(self.excluded_product_ids.mapped(lambda l: l._describe())),
            ))
        return "\n".join(lines) or _("Sin condiciones (coincide con todos los clientes).")


class CrmOpportunityRuleWizardProductLine(models.TransientModel):
    _name = "crm.opportunity.rule.wizard.product.line"
    _description = "Product/service requirement row of the rule condition assistant"

    required_wizard_id = fields.Many2one(
        "crm.opportunity.rule.wizard", ondelete="cascade"
    )
    excluded_wizard_id = fields.Many2one(
        "crm.opportunity.rule.wizard", ondelete="cascade"
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto/servicio",
        required=True,
        domain=[("crm_business", "=", True)],
    )
    state = fields.Selection(
        _STATE_SELECTION, string="Estado",
        help="Vacío = cualquier estado.",
    )
    provider = fields.Selection(
        _PROVIDER_SELECTION, string="Proveedor",
        help="Vacío = cualquier proveedor.",
    )

    def _build_subdomain(self):
        self.ensure_one()
        subdomain = [("product_tmpl_id", "=", self.product_tmpl_id.id)]
        if self.state:
            subdomain.append(("state", "=", self.state))
        if self.provider:
            subdomain.append(("provider", "=", self.provider))
        return subdomain

    def _describe(self):
        self.ensure_one()
        details = []
        if self.state:
            details.append(dict(_STATE_SELECTION)[self.state])
        if self.provider:
            details.append(dict(_PROVIDER_SELECTION)[self.provider])
        if not details:
            return self.product_tmpl_id.name
        return "%s (%s)" % (self.product_tmpl_id.name, ", ".join(details))
