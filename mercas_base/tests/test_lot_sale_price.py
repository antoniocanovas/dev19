from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLotSalePrice(TransactionCase):
    """The sale price of a lot is the base of the price lists in its sales,
    instead of the sale price of the product."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({
            "name": "Lot Price Pear",
            "is_storable": True,
            "tracking": "lot",
            "list_price": 2.0,
            "taxes_id": [Command.clear()],
        })
        Lot = cls.env["stock.lot"]
        cls.priced_lot = Lot.create({"name": "PRICED", "product_id": cls.product.id, "mercas_sale_price": 3.0})
        cls.other_lot = Lot.create({"name": "OTHER", "product_id": cls.product.id, "mercas_sale_price": 4.0})
        cls.plain_lot = Lot.create({"name": "PLAIN", "product_id": cls.product.id})
        stock = cls.env.ref("stock.stock_location_stock")
        for lot in cls.priced_lot | cls.other_lot | cls.plain_lot:
            cls.env["stock.quant"]._update_available_quantity(cls.product, stock, 100.0, lot_id=lot)
        cls.customer = cls.env["res.partner"].create({"name": "Lot Price Customer"})
        cls.pricelist = cls.env["product.pricelist"].create({"name": "Lot Price List"})

    def _line(self, lot, pricelist=None):
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "pricelist_id": (pricelist or self.pricelist).id,
            "order_line": [Command.create({
                "product_id": self.product.id, "product_uom_qty": 10, "lot_id": lot.id,
            })],
        })
        return order.order_line

    def _rule(self, **vals):
        self.pricelist.item_ids = [Command.create({
            "applied_on": "1_product", "product_tmpl_id": self.product.product_tmpl_id.id, **vals,
        })]

    def test_lot_price_without_rule(self):
        self.assertEqual(self._line(self.priced_lot).price_unit, 3.0)
        self.assertEqual(self._line(self.plain_lot).price_unit, 2.0, "Without price, the one of the product")

    def test_discount_on_the_lot_price(self):
        self._rule(compute_price="percentage", percent_price=10)
        self.assertAlmostEqual(self._line(self.priced_lot).price_unit, 2.7)
        self.assertAlmostEqual(self._line(self.plain_lot).price_unit, 1.8)

    def test_formula_on_the_lot_price(self):
        self._rule(compute_price="formula", base="list_price", price_discount=0, price_surcharge=0.5)
        self.assertAlmostEqual(self._line(self.priced_lot).price_unit, 3.5)

    def test_fixed_price_wins(self):
        self._rule(compute_price="fixed", fixed_price=1.5)
        self.assertEqual(self._line(self.priced_lot).price_unit, 1.5)

    def test_change_of_lot(self):
        """In a quotation the price follows the lot; in a confirmed sale what
        was sold keeps its price when its lot is corrected."""
        line = self._line(self.priced_lot)
        line.lot_id = self.other_lot
        self.assertEqual(line.price_unit, 4.0)
        line.order_id.action_confirm()
        line.lot_id = self.priced_lot
        self.assertEqual(line.price_unit, 4.0)

    def test_purchase_carries_the_price_to_the_lot(self):
        supplier = self.env["res.partner"].create({"name": "Lot Price Supplier"})
        order = self.env["purchase.order"].create({
            "partner_id": supplier.id,
            "order_line": [Command.create({
                "product_id": self.product.id, "product_qty": 10, "price_unit": 1.0,
                "mercas_lot_sale_price": 2.5,
            })],
        })
        order.button_confirm()
        lot = order.order_line.lot_id
        self.assertTrue(lot)
        self.assertEqual(lot.mercas_sale_price, 2.5)
        # Changed on the line, changed on the lot; without one, the lot keeps its own
        order.order_line.mercas_lot_sale_price = 2.8
        self.assertEqual(lot.mercas_sale_price, 2.8)
        order.order_line.mercas_lot_sale_price = 0
        self.assertEqual(lot.mercas_sale_price, 2.8)
