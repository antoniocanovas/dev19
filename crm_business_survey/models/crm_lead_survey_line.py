import werkzeug.urls

from odoo import Command, _, fields, models


class CrmLeadSurveyLine(models.Model):
    _name = "crm.lead.survey.line"
    _description = "Opportunity survey tracking line"

    lead_id = fields.Many2one("crm.lead", required=True, ondelete="cascade")
    survey_id = fields.Many2one("survey.survey", required=True, readonly=True)
    user_input_id = fields.Many2one("survey.user_input", readonly=True)

    _sql_constraints = [
        (
            "lead_survey_uniq",
            "unique(lead_id, survey_id)",
            "Ya existe una línea de encuesta para esta oportunidad y este tipo de encuesta.",
        ),
    ]

    def _get_survey_url(self, user_input):
        return "%s?%s" % (
            self.survey_id.sudo().get_start_url(),
            werkzeug.urls.url_encode({"answer_token": user_input.access_token}),
        )

    def action_start_survey(self):
        self.ensure_one()
        user_input = self.survey_id.sudo()._create_answer(
            user=self.env.user, partner=self.lead_id.partner_id
        )
        self.user_input_id = user_input
        return {
            "type": "ir.actions.act_url",
            "name": _("Cumplimentar encuesta"),
            "target": "new",
            "url": self._get_survey_url(user_input),
        }

    def action_open_user_input(self):
        self.ensure_one()
        user_input = self.user_input_id.sudo()
        if user_input.state == "done":
            # Reopen it for edition: reset the state and last_displayed_page_id
            # so the survey flow resumes from the first page instead of crashing
            # (there would be no "next" page left to compute) or showing the
            # "already answered" page.
            vals = {
                "state": "in_progress",
                "end_datetime": False,
                "last_displayed_page_id": False,
            }
            if not user_input.survey_id.users_can_go_back:
                # Unless the survey allows going back, answering an already
                # answered question raises "This answer cannot be overwritten.".
                # Clear the previous answers so the survey can be filled in again.
                vals["user_input_line_ids"] = [Command.clear()]
            user_input.write(vals)
        return {
            "type": "ir.actions.act_url",
            "name": _("Ver / editar encuesta"),
            "target": "new",
            "url": self._get_survey_url(user_input),
        }
