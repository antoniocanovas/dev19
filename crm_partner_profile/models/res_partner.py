from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    crm_profile_line_ids = fields.One2many(
        "crm.partner.profile.line", "partner_id", string="Clasificación"
    )
    crm_current_product_ids = fields.One2many(
        "crm.partner.current_product", "partner_id", string="Productos y servicios actuales"
    )

    # Deliberately NOT using tracking=True here: mail.thread's own tracking
    # re-reads the "before" o2m recordset at precommit time to build the
    # chatter message, and a line removed from the UI is actually deleted
    # (ondelete=cascade, required partner_id), not just unlinked — so that
    # re-read hits a MissingError, which is caught generically and silently
    # cancels ALL tracking for that write, not just this field. Logging the
    # before/after as plain strings up front sidesteps that entirely.
    _CRM_PROFILE_TRACKED_O2M_FIELDS = ("crm_profile_line_ids", "crm_current_product_ids")

    def write(self, vals):
        to_track = [f for f in self._CRM_PROFILE_TRACKED_O2M_FIELDS if f in vals]
        before = {
            partner.id: {fname: ", ".join(partner[fname].mapped("display_name")) for fname in to_track}
            for partner in self
        } if to_track else {}
        res = super().write(vals)
        for partner in self:
            for fname in to_track:
                old = before[partner.id][fname]
                new = ", ".join(partner[fname].mapped("display_name"))
                if old != new:
                    partner.message_post(body=_(
                        "%(label)s: %(old)s → %(new)s",
                        label=partner._fields[fname].string,
                        old=old or _("(vacío)"),
                        new=new or _("(vacío)"),
                    ))
        return res
