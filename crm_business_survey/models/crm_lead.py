from markupsafe import Markup, escape

from odoo import _, api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    survey_line_ids = fields.One2many(
        "crm.lead.survey.line", "lead_id", string="Encuestas"
    )
    survey_answers_html = fields.Html(
        string="Respuestas de las encuestas", compute="_compute_survey_answers_html"
    )

    @api.depends(
        "survey_line_ids.user_input_id",
        "survey_line_ids.user_input_id.state",
        "survey_line_ids.user_input_id.user_input_line_ids",
    )
    def _compute_survey_answers_html(self):
        for lead in self:
            sections = []
            for line in lead.survey_line_ids:
                user_input = line.user_input_id.sudo()
                if not user_input or user_input.state != "done":
                    continue
                answers = user_input.user_input_line_ids.filtered(lambda a: not a.skipped)
                if answers:
                    rows = Markup("").join(
                        Markup("<tr><td class=\"text-muted\">%s</td><td>%s</td></tr>")
                        % (escape(answer.question_id.title), escape(answer.display_name or ""))
                        for answer in answers
                    )
                else:
                    # Always show a card for every completed survey, even when it
                    # has no answer lines, so a survey is never silently dropped.
                    rows = Markup(
                        "<tr><td colspan=\"2\" class=\"text-muted fst-italic\">%s</td></tr>"
                    ) % escape(_("Sin respuestas registradas."))
                sections.append(
                    Markup(
                        "<div class=\"card mb-3\">"
                        "<div class=\"card-header\"><strong>%s</strong></div>"
                        "<table class=\"table table-sm mb-0\"><tbody>%s</tbody></table>"
                        "</div>"
                    )
                    % (escape(line.survey_id.title), rows)
                )
            lead.survey_answers_html = Markup("").join(sections) if sections else False

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads.filtered("product_template_id")._sync_survey_lines()
        return leads

    def write(self, vals):
        res = super().write(vals)
        if "product_template_id" in vals:
            self.filtered("product_template_id")._sync_survey_lines()
        return res

    def _sync_survey_lines(self):
        for lead in self:
            wanted_surveys = lead.product_template_id.crm_business_product_type_id.survey_ids
            missing_surveys = wanted_surveys - lead.survey_line_ids.survey_id
            for survey in missing_surveys:
                self.env["crm.lead.survey.line"].create({
                    "lead_id": lead.id,
                    "survey_id": survey.id,
                })
