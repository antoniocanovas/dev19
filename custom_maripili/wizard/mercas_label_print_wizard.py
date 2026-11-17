from odoo import fields, models


class MercasLabelPrintWizard(models.TransientModel):
    _inherit = "mercas.label.print.wizard"

    print_format = fields.Selection(
        selection_add=[("70x50", "70 x 50 (label printer)")],
        ondelete={"70x50": "set default"},
    )

    def _get_report_xmlid(self):
        if self.print_format == "70x50":
            return "custom_maripili.action_report_box_label_70x50"
        return super()._get_report_xmlid()
