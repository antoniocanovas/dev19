from odoo import models


class ReportBoxLabel70x50(models.AbstractModel):
    """Same values as the box labels of mercas_base (one per box), laid out
    one label per page for the label printer."""

    _name = "report.custom_maripili.report_box_label_70x50"
    _inherit = "report.mercas_base.report_mercas_box_label"
    _description = "Box Label 70 x 50 (Maripili)"
