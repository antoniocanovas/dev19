from odoo import _, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    product_template_id = fields.Many2one("product.template", string="Producto")

    def action_open_crm_business_product_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nuevo producto"),
            "res_model": "crm.business.product.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_lead_id": self.id},
        }
