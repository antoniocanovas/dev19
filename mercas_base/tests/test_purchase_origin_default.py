from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPurchaseOriginDefault(TransactionCase):
    """The origin of the goods bought is, by default, where the supplier is."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.spain = cls.env.ref("base.es")
        cls.murcia = cls.env.ref("base.state_es_mu")
        cls.supplier = cls.env["res.partner"].create({
            "name": "Origin Supplier",
            "is_company": True,
            "country_id": cls.spain.id,
            "state_id": cls.murcia.id,
        })
        cls.contact = cls.env["res.partner"].create({"name": "Origin Contact", "parent_id": cls.supplier.id})
        cls.product = cls.env["product.product"].create({"name": "Origin Product", "type": "consu"})
        cls.box = cls.env["product.product"].create({"name": "Origin Box", "type": "consu", "is_box": True})

    def _order(self, partner, **line):
        return self.env["purchase.order"].create({
            "partner_id": partner.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 1, "price_unit": 1, **line})],
        })

    def test_origin_of_the_supplier(self):
        self.env.company.origin_filter = False
        line = self._order(self.contact).order_line
        self.assertEqual(line.origin_country_id, self.spain, "Of the supplier, also for one of its contacts")
        self.assertEqual(line.origin_state_id, self.murcia)
        # Still editable on each line
        seville = self.env.ref("base.state_es_se")
        line = self._order(self.supplier, origin_country_id=self.spain.id, origin_state_id=seville.id).order_line
        self.assertEqual((line.origin_country_id, line.origin_state_id), (self.spain, seville))
        # Not for the boxes
        order = self._order(self.supplier)
        order.order_line = [(0, 0, {"product_id": self.box.id, "product_qty": 1, "price_unit": 1})]
        box_line = order.order_line.filtered(lambda l: l.product_id == self.box)
        self.assertFalse(box_line.origin_country_id)

    def test_origin_filter(self):
        """With the origin filter, only a country marked as origin is proposed."""
        self.env.company.origin_filter = True
        self.spain.mercas_origin = False
        line = self._order(self.supplier).order_line
        self.assertFalse(line.origin_country_id)
        self.assertFalse(line.origin_state_id)
        self.spain.mercas_origin = True
        line = self._order(self.supplier).order_line
        self.assertEqual((line.origin_country_id, line.origin_state_id), (self.spain, self.murcia))
