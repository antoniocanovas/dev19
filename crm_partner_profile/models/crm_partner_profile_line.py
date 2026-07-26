from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmPartnerProfileLine(models.Model):
    _name = "crm.partner.profile.line"
    _description = "Client classification line (one row per attribute type)"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    attribute_id = fields.Many2one(
        "crm.partner.attribute",
        required=True,
        domain="[('id', 'not in', partner_used_attribute_ids)]",
    )
    value_ids = fields.Many2many(
        "crm.partner.attribute.value",
        string="Valores",
        domain="[('attribute_id', '=', attribute_id)]",
    )
    partner_used_attribute_ids = fields.Many2many(
        "crm.partner.attribute",
        compute="_compute_partner_used_attribute_ids",
        help="Tipos de clasificación que este cliente ya tiene en otra línea, "
             "para no ofrecerlos otra vez al añadir una línea nueva.",
    )

    _partner_attribute_uniq = models.Constraint(
        "unique(partner_id, attribute_id)",
        "Ya existe una línea de este tipo de clasificación para este cliente.",
    )

    @api.depends("partner_id.crm_profile_line_ids.attribute_id")
    def _compute_partner_used_attribute_ids(self):
        for line in self:
            line.partner_used_attribute_ids = (
                line.partner_id.crm_profile_line_ids.attribute_id - line.attribute_id
            )

    @api.depends("attribute_id", "value_ids")
    def _compute_display_name(self):
        # Without this, the default display_name (e.g. in tracking/chatter
        # messages) falls back to the unreadable "crm.partner.profile.line,45".
        for line in self:
            values = ", ".join(line.value_ids.with_context(show_attribute=False).mapped("name"))
            line.display_name = f"{line.attribute_id.name}: {values}" if line.attribute_id else values

    @api.constrains("value_ids", "attribute_id")
    def _check_single_value(self):
        for line in self:
            if line.attribute_id.value_type == "single" and len(line.value_ids) > 1:
                raise ValidationError(
                    _(
                        "«%(attribute)s» solo admite un valor por cliente.",
                        attribute=line.attribute_id.name,
                    )
                )
