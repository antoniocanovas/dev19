from odoo import models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def unlink(self):
        # crm.opportunity.suggestion.lead_id is ondelete='set null', so the
        # database clears it directly via the FK constraint without going
        # through write() — state would otherwise stay stuck on "converted"
        # with an empty lead_id. Capture the affected suggestions before the
        # delete (their lead_id still points here) and revert them after.
        Suggestion = self.env["crm.opportunity.suggestion"]
        suggestions = Suggestion.search([("lead_id", "in", self.ids)])
        res = super().unlink()
        if suggestions:
            suggestions.write({"state": "new", "lead_id": False})
        return res
