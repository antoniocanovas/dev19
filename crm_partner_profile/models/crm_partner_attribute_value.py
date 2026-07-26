from odoo import api, fields, models


class CrmPartnerAttributeValue(models.Model):
    _name = "crm.partner.attribute.value"
    _description = "Client classification value"
    # Keep in sync with _compute_display_name below (same pattern as
    # product.attribute.value: grouped by attribute first, then sequence).
    _order = "attribute_id, sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    attribute_id = fields.Many2one(
        "crm.partner.attribute", required=True, ondelete="cascade", index=True
    )
    active = fields.Boolean(default=True)

    _name_attribute_uniq = models.Constraint(
        "unique(name, attribute_id)",
        "Ya existe un valor con este nombre para este tipo de clasificación.",
    )

    @api.depends("attribute_id", "name")
    @api.depends_context("show_attribute")
    def _compute_display_name(self):
        # Same pattern as product.attribute.value: showing the value alone
        # ("Calzado") is confusing when values from several attribute types
        # are mixed in the same list (e.g. the rule condition assistant).
        # Callers that already show the attribute as its own column (e.g.
        # the classification table on the partner form) can opt out with
        # context={'show_attribute': False} to avoid repeating it.
        if not self.env.context.get("show_attribute", True):
            super()._compute_display_name()
            return
        for value in self:
            value.display_name = f"{value.attribute_id.name}: {value.name}"
