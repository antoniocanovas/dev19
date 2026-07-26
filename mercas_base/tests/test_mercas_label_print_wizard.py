from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMercasLabelPrintWizard(TransactionCase):
    """Comprar 100 kg de plátano (10 cajas) y 200 kg de pera (15 cajas):
    el asistente debe proponer 10 etiquetas de plátano y 15 de pera, sin
    incluir la línea de envases ni productos de tipo servicio."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.supplier = cls.env["res.partner"].create({"name": "Proveedor Etiquetas"})
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")

        cls.box_product = cls.env["product.product"].create({
            "name": "Caja test",
            "type": "consu",
            "is_box": True,
        })
        cls.platano = cls.env["product.product"].create({
            "name": "Plátano",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.uom_kg.id,
        })
        cls.pera = cls.env["product.product"].create({
            "name": "Pera",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.uom_kg.id,
        })
        cls.service_product = cls.env["product.product"].create({
            "name": "Transporte",
            "type": "service",
        })

        cls.purchase = cls.env["purchase.order"].create({
            "partner_id": cls.supplier.id,
            "order_line": [
                Command.create({
                    "product_id": cls.platano.id,
                    "product_qty": 100.0,
                    "product_uom_id": cls.uom_kg.id,
                    "price_unit": 1.0,
                    "box_qty": 10,
                    "box_product_id": cls.box_product.id,
                }),
                Command.create({
                    "product_id": cls.pera.id,
                    "product_qty": 200.0,
                    "product_uom_id": cls.uom_kg.id,
                    "price_unit": 1.5,
                    "box_qty": 15,
                    "box_product_id": cls.box_product.id,
                }),
                Command.create({
                    "product_id": cls.service_product.id,
                    "product_qty": 1.0,
                    "price_unit": 20.0,
                }),
            ],
        })
        cls.purchase.button_confirm()

    def _create_wizard(self):
        Wizard = self.env["mercas.label.print.wizard"]
        return Wizard.with_context(default_purchase_id=self.purchase.id).create({})

    def test_proposes_boxes_from_purchase_lines(self):
        # The confirm flow auto-creates a box line for the "Caja test" product;
        # it must not show up as a candidate to label.
        box_line = self.purchase.order_line.filtered(
            lambda l: l.product_id == self.box_product and l.box_purchase_line_id
        )
        self.assertTrue(box_line)

        wizard = self._create_wizard()
        proposed = {line.product_id: line.quantity for line in wizard.line_ids}
        self.assertEqual(proposed, {self.platano: 10, self.pera: 15})
        self.assertNotIn(self.box_product, proposed)
        self.assertNotIn(self.service_product, proposed)

    def test_print_uses_edited_quantities(self):
        wizard = self._create_wizard()
        platano_line = wizard.line_ids.filtered(lambda l: l.product_id == self.platano)
        platano_line.quantity = 3  # solo reponer 3 etiquetas rotas

        action = wizard.action_print()
        self.assertEqual(action["type"], "ir.actions.report")
        quantity_by_product = action["data"]["quantity_by_product"]
        self.assertEqual(quantity_by_product[self.platano.id], 3)
        self.assertEqual(quantity_by_product[self.pera.id], 15)

    def test_print_requires_positive_quantity(self):
        wizard = self._create_wizard()
        wizard.line_ids.quantity = 0
        with self.assertRaises(UserError):
            wizard.action_print()

    def test_proposes_boxes_from_sale_lines(self):
        customer = self.env["res.partner"].create({"name": "Cliente Etiquetas"})
        sale = self.env["sale.order"].create({
            "partner_id": customer.id,
            "order_line": [
                Command.create({
                    "product_id": self.platano.id,
                    "product_uom_qty": 50.0,
                    "product_uom_id": self.uom_kg.id,
                    "price_unit": 2.0,
                    "box_qty": 5,
                    "box_product_id": self.box_product.id,
                }),
            ],
        })
        sale.action_confirm()

        wizard = self.env["mercas.label.print.wizard"].with_context(
            default_sale_id=sale.id
        ).create({})
        proposed = {line.product_id: line.quantity for line in wizard.line_ids}
        self.assertEqual(proposed, {self.platano: 5})
