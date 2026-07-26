from odoo import _, api, fields, models


class CrmPartnerAttribute(models.Model):
    _name = "crm.partner.attribute"
    _description = "Client classification type (sector, interest...)"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    value_type = fields.Selection(
        [("single", "Única"), ("multi", "Múltiple")],
        string="Selección",
        default="multi",
        required=True,
        help="Si es «Única», el perfil del cliente solo admite un valor de este tipo.",
    )
    value_ids = fields.One2many("crm.partner.attribute.value", "attribute_id", string="Valores")
    active = fields.Boolean(default=True)
    partner_count = fields.Integer(compute="_compute_partner_count", string="Clientes")

    @api.depends("value_ids")
    def _compute_partner_count(self):
        # unique(partner_id, attribute_id) on crm.partner.profile.line means
        # at most one line per client for this type, so counting lines here
        # is the same as counting distinct clients.
        counts = dict(
            self.env["crm.partner.profile.line"]._read_group(
                [("attribute_id", "in", self.ids)], ["attribute_id"], ["__count"]
            )
        )
        for attribute in self:
            attribute.partner_count = counts.get(attribute, 0)

    def action_view_partners(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "crm_partner_profile.crm_partner_profile_line_action_report"
        )
        action["domain"] = [("attribute_id", "=", self.id)]
        action["context"] = {"search_default_group_value": 1}
        action["name"] = _("Clientes con «%(attribute)s»", attribute=self.name)
        return action
