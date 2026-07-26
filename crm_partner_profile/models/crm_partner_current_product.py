from odoo import api, fields, models


class CrmPartnerCurrentProduct(models.Model):
    _name = "crm.partner.current_product"
    _description = "Product or service currently used by the client"
    _order = "state, product_tmpl_id"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto/servicio",
        required=True,
        domain="[('crm_business', '=', True), ('id', 'not in', partner_used_product_tmpl_ids)]",
    )
    partner_used_product_tmpl_ids = fields.Many2many(
        "product.template",
        compute="_compute_partner_used_product_tmpl_ids",
        help="Productos/servicios que este cliente ya tiene en otra línea, "
             "para no ofrecerlos otra vez al añadir una línea nueva.",
    )
    state = fields.Selection(
        [
            ("1_ok", "Vigente - Ok"),
            ("2_to_evolve", "Vigente - A evolucionar"),
            ("3_to_change", "Vigente - A cambiar"),
            ("4_stopped", "Parado / sin uso"),
            ("5_obsolete", "Obsoleto"),
        ],
        string="Estado",
        default="1_ok",
        required=True,
        help="Vigente - Ok: en uso, sin motivo de cambio. Vigente - A "
             "evolucionar: en uso, con margen de mejora (oportunidad "
             "suave). Vigente - A cambiar: en uso pero el cliente quiere "
             "sustituirlo (oportunidad clara). Parado / sin uso: el "
             "cliente lo tiene pero no lo usa activamente. Obsoleto: "
             "superado técnica o funcionalmente.",
    )
    provider = fields.Selection(
        [
            ("internal", "Interno"),
            ("us", "Nosotros"),
            ("competitor", "Competencia"),
            ("multiple", "Varios"),
        ],
        string="Proveedor",
        help="Quién provee hoy este producto/servicio al cliente: "
             "desarrollado internamente por él, nosotros, la competencia, "
             "o varios proveedores a la vez.",
    )
    note = fields.Char(string="Nota")

    _partner_product_uniq = models.Constraint(
        "unique(partner_id, product_tmpl_id)",
        "Este producto/servicio ya está registrado para este cliente.",
    )

    @api.depends("partner_id.crm_current_product_ids.product_tmpl_id")
    def _compute_partner_used_product_tmpl_ids(self):
        for line in self:
            line.partner_used_product_tmpl_ids = (
                line.partner_id.crm_current_product_ids.product_tmpl_id - line.product_tmpl_id
            )

    @api.depends("product_tmpl_id", "state")
    def _compute_display_name(self):
        # Without this, the default display_name (e.g. in tracking/chatter
        # messages) falls back to the unreadable "crm.partner.current_product,7".
        state_labels = dict(self._fields["state"].selection)
        for line in self:
            product_name = line.product_tmpl_id.name or ""
            line.display_name = (
                f"{product_name} ({state_labels.get(line.state)})" if line.state else product_name
            )
