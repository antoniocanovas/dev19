from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    mercas_margin = fields.Float(
        string="Mercas margin percent",
        digits=(10, 2),
        help="Partner mercas margin used when not null.",
    )

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
