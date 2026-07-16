from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    mercas_margin = fields.Float(
        string="Mercas margin (%)",
        digits=(10, 2),
        help="Partner mercas margin used when not null.",
    )
    mercas_box_qty = fields.Float(
        string="Cajas",
        compute="_compute_mercas_box_qty",
        help=(
            "Cantidad de cajas (productos de las categorías configuradas en la "
            "empresa) presentes en las ubicaciones propias de cliente y proveedor "
            "de este contacto."
        ),
    )

    def _mercas_box_locations(self, company):
        """Dedicated customer/supplier locations of this partner, excluding the
        company's generic parent locations."""
        self.ensure_one()
        partner = self.commercial_partner_id.with_company(company)
        locations = self.env["stock.location"]
        customer_loc = partner.property_stock_customer
        if customer_loc and customer_loc != company.mercas_customer_location_id:
            locations |= customer_loc
        supplier_loc = partner.property_stock_supplier
        if supplier_loc and supplier_loc != company.mercas_supplier_location_id:
            locations |= supplier_loc
        return locations

    def _mercas_box_quants_domain(self, company):
        locations = self._mercas_box_locations(company)
        box_categs = company.box_categ_ids
        if not locations or not box_categs:
            return None
        return [
            ("location_id", "in", locations.ids),
            ("product_id.categ_id", "in", box_categs.ids),
            ("quantity", "!=", 0),
        ]

    def _compute_mercas_box_qty(self):
        company = self.env.company
        for partner in self:
            domain = partner._mercas_box_quants_domain(company)
            if domain is None:
                partner.mercas_box_qty = 0.0
                continue
            quants = self.env["stock.quant"].search(domain)
            partner.mercas_box_qty = sum(quants.mapped("quantity"))

    def action_view_mercas_box_quants(self):
        self.ensure_one()
        domain = self._mercas_box_quants_domain(self.env.company) or [("id", "=", 0)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Resumen de cajas"),
            "res_model": "stock.quant",
            "view_mode": "list",
            "domain": domain,
            "context": {"group_by": ["product_id", "location_id"]},
        }

    def mercas_ensure_customer_location(self, company):
        """Ensure the commercial partner has a sub-location under the mercas parent.

        Creates one if missing and sets property_stock_customer on the partner.
        Safe to call repeatedly; no-op when the location already exists.
        """
        self.ensure_one()
        parent_loc = company.mercas_customer_location_id
        if not parent_loc:
            return
        partner = self.commercial_partner_id
        current = partner.with_company(company).property_stock_customer
        if current and current.location_id == parent_loc:
            return
        new_loc = self.env["stock.location"].create({
            "name": partner.name,
            "location_id": parent_loc.id,
            "usage": "customer",
        })
        partner.with_company(company).property_stock_customer = new_loc

    def mercas_ensure_supplier_location(self, company):
        """Ensure the commercial partner has a sub-location under the mercas supplier parent.

        Creates one if missing and sets property_stock_supplier on the partner.
        Safe to call repeatedly; no-op when the location already exists.
        """
        self.ensure_one()
        parent_loc = company.mercas_supplier_location_id
        if not parent_loc:
            return
        partner = self.commercial_partner_id
        current = partner.with_company(company).property_stock_supplier
        if current and current.location_id == parent_loc:
            return
        new_loc = self.env["stock.location"].create({
            "name": partner.name,
            "location_id": parent_loc.id,
            "usage": "supplier",
        })
        partner.with_company(company).property_stock_supplier = new_loc
