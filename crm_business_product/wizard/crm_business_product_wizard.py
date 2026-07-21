from odoo import Command, api, fields, models


class CrmBusinessProductWizard(models.TransientModel):
    _name = "crm.business.product.wizard"
    _description = "Create product from an opportunity"

    lead_id = fields.Many2one("crm.lead", required=True)
    type_id = fields.Many2one(
        "crm.business.product.type", string="Tipo de producto", required=True
    )
    name = fields.Char(string="Nombre", required=True)
    detail_type = fields.Selection(
        [("consu", "Bien"), ("service", "Servicio")],
        string="Tipo",
        required=True,
        default="consu",
    )
    categ_id = fields.Many2one(
        "product.category", string="Categoría", required=True
    )
    attribute_line_ids = fields.One2many(
        "crm.business.product.wizard.line", "wizard_id", string="Atributos"
    )

    @api.onchange("type_id")
    def _onchange_type_id(self):
        self.attribute_line_ids = [Command.clear()] + [
            Command.create({"attribute_id": attribute.id})
            for attribute in self.type_id.attribute_ids
        ]

    def action_create_product(self):
        self.ensure_one()
        product = self.env["product.template"].create({
            "name": self.name,
            "type": self.detail_type,
            "categ_id": self.categ_id.id,
            "crm_business_product_type_id": self.type_id.id,
        })
        for line in self.attribute_line_ids.filtered("value_ids"):
            self.env["product.template.attribute.line"].create({
                "product_tmpl_id": product.id,
                "attribute_id": line.attribute_id.id,
                "value_ids": [Command.set(line.value_ids.ids)],
            })
        self.lead_id.product_template_id = product
        return {"type": "ir.actions.act_window_close"}


class CrmBusinessProductWizardLine(models.TransientModel):
    _name = "crm.business.product.wizard.line"
    _description = "Attribute line for the product creation wizard"

    wizard_id = fields.Many2one(
        "crm.business.product.wizard", required=True, ondelete="cascade"
    )
    attribute_id = fields.Many2one(
        "product.attribute", string="Atributo", required=True
    )
    value_ids = fields.Many2many(
        "product.attribute.value",
        string="Valores",
        domain="[('attribute_id', '=', attribute_id)]",
    )
