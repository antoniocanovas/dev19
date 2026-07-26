from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockLotChangeWizard(TransactionCase):
    """Un usuario asigna por error el lote A a una línea de venta; se
    corrige a mano al lote B correcto con el asistente, tanto si ya se ha
    servido como si el albarán sigue pendiente de validar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.supplier = cls.env["res.partner"].create({"name": "Proveedor Corrección Lote"})
        cls.customer = cls.env["res.partner"].create({"name": "Cliente Corrección Lote"})
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.product = cls.env["product.product"].create({
            "name": "Producto Corrección Lote",
            "type": "consu",
            "is_storable": True,
            "tracking": "lot",
            "uom_id": cls.uom_kg.id,
            "taxes_id": [Command.clear()],
            "supplier_taxes_id": [Command.clear()],
        })

        cls.lot_a = cls.env["stock.lot"].create({
            "name": "LOTE-A",
            "product_id": cls.product.id,
            "company_id": cls.company.id,
            "partner_id": cls.supplier.id,
            "mercas_margin": 10.0,
        })
        cls.lot_b = cls.env["stock.lot"].create({
            "name": "LOTE-B",
            "product_id": cls.product.id,
            "company_id": cls.company.id,
            "partner_id": cls.supplier.id,
            "mercas_margin": 10.0,
        })
        for lot in (cls.lot_a, cls.lot_b):
            purchase = cls.env["purchase.order"].create({
                "partner_id": cls.supplier.id,
                "order_line": [Command.create({
                    "product_id": cls.product.id,
                    "product_qty": 1000.0,
                    "product_uom_id": cls.uom_kg.id,
                    "price_unit": 1.0,
                    "lot_id": lot.id,
                })],
            })
            purchase.button_purchase_and_receive()

        cls.manager_user = cls.env["res.users"].create({
            "name": "Corrector de lotes",
            "login": "mercas_test_lot_corrector",
            "email": "mercas_test_lot_corrector@example.com",
            "group_ids": [
                Command.link(cls.env.ref("mercas_base.group_correct_lots").id),
                Command.link(cls.env.ref("stock.group_stock_user").id),
                Command.link(cls.env.ref("sales_team.group_sale_salesman").id),
                Command.link(cls.env.ref("account.group_account_manager").id),
            ],
        })

    def _create_wizard(self, sale_line, user=None):
        Wizard = self.env["stock.lot.change.wizard"].with_user(user or self.manager_user)
        return Wizard.with_context(default_sale_line_id=sale_line.id).create({})

    def _sell(self, lot, qty, price_unit):
        sale = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": qty,
                "product_uom_id": self.uom_kg.id,
                "price_unit": price_unit,
                "lot_id": lot.id,
            })],
        })
        sale.button_sold_and_sent()
        return sale

    def test_wizard_moves_delivered_qty_between_lots(self):
        sale = self._sell(self.lot_a, 500.0, 2.0)
        line = sale.order_line
        self.assertTrue(line.mercas_has_assigned_lot)
        self.assertAlmostEqual(self.lot_a.sale_kg, 500.0, places=2)
        self.assertAlmostEqual(self.lot_b.sale_kg, 0.0, places=2)

        action = line.with_user(self.manager_user).action_open_lot_change_wizard()
        self.assertEqual(action["res_model"], "stock.lot.change.wizard")
        self.assertEqual(action["context"]["default_sale_line_id"], line.id)
        wizard = self._create_wizard(line)
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.current_lot_id, self.lot_a)
        wizard.line_ids.new_lot_id = self.lot_b.id

        wizard.action_apply()

        self.assertEqual(line.lot_id, self.lot_b)
        self.assertAlmostEqual(self.lot_a.sale_kg, 0.0, places=2)
        self.assertAlmostEqual(self.lot_b.sale_kg, 500.0, places=2)
        self.assertAlmostEqual(self.lot_a.sale_amount, 0.0, places=2)
        self.assertAlmostEqual(self.lot_b.sale_amount, 1000.0, places=2)

    def test_wizard_corrects_physical_quants_after_delivery(self):
        sale = self._sell(self.lot_a, 500.0, 2.0)
        line = sale.order_line
        move_line = line.move_ids.move_line_ids
        self.assertEqual(move_line.state, "done")

        dest_location = move_line.location_dest_id
        src_location = move_line.location_id
        Quant = self.env["stock.quant"]

        def qty_at(location, lot):
            return sum(Quant.search([
                ("product_id", "=", self.product.id),
                ("location_id", "=", location.id),
                ("lot_id", "=", lot.id),
            ]).mapped("quantity"))

        dest_a_before = qty_at(dest_location, self.lot_a)
        dest_b_before = qty_at(dest_location, self.lot_b)
        src_a_before = qty_at(src_location, self.lot_a)
        src_b_before = qty_at(src_location, self.lot_b)

        wizard = self._create_wizard(line)
        wizard.line_ids.new_lot_id = self.lot_b.id
        wizard.action_apply()

        # En destino (ubicación del cliente): sale el lote A, entra el B.
        self.assertAlmostEqual(qty_at(dest_location, self.lot_a), dest_a_before - 500.0, places=2)
        self.assertAlmostEqual(qty_at(dest_location, self.lot_b), dest_b_before + 500.0, places=2)
        # En origen (almacén): se devuelve la cantidad al lote A, se descuenta del B.
        self.assertAlmostEqual(qty_at(src_location, self.lot_a), src_a_before + 500.0, places=2)
        self.assertAlmostEqual(qty_at(src_location, self.lot_b), src_b_before - 500.0, places=2)

    def test_wizard_corrects_reserved_lot_before_delivery(self):
        # A diferencia de _sell (que confirma y entrega en el mismo paso),
        # aquí solo se confirma: la reserva ya asigna un lote concreto a la
        # línea de albarán (gracias a sale_order_lot_selection), pero el
        # albarán sigue sin validar. El icono/asistente debe funcionar igual.
        sale = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 500.0,
                "product_uom_id": self.uom_kg.id,
                "price_unit": 2.0,
                "lot_id": self.lot_a.id,
            })],
        })
        sale.action_confirm()
        line = sale.order_line
        move_line = line.move_ids.move_line_ids
        self.assertNotEqual(move_line.state, "done")
        self.assertEqual(move_line.lot_id, self.lot_a)
        self.assertTrue(line.mercas_has_assigned_lot)

        wizard = self._create_wizard(line)
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.current_lot_id, self.lot_a)
        wizard.line_ids.new_lot_id = self.lot_b.id
        wizard.action_apply()

        self.assertEqual(move_line.lot_id, self.lot_b)
        self.assertEqual(line.lot_id, self.lot_b)

        # Validar el albarán después de corregir debe entregar del lote
        # correcto, sin dejar cantidades huérfanas reservadas del lote A.
        move_line.quantity = 500.0
        sale.picking_ids.with_context(skip_immediate=True, skip_backorder=True).button_validate()
        self.assertEqual(move_line.state, "done")
        self.assertEqual(move_line.lot_id, self.lot_b)
        self.assertAlmostEqual(self.lot_a.sale_kg, 0.0, places=2)
        self.assertAlmostEqual(self.lot_b.sale_kg, 500.0, places=2)

    def test_wizard_updates_draft_invoice_line(self):
        sale = self._sell(self.lot_a, 500.0, 2.0)
        line = sale.order_line
        invoice = sale._create_invoices()
        invoice_line = invoice.invoice_line_ids.filtered(lambda l: l.product_id == self.product)
        self.assertEqual(invoice_line.lot_id, self.lot_a)

        wizard = self._create_wizard(line)
        wizard.line_ids.new_lot_id = self.lot_b.id
        wizard.action_apply()

        self.assertEqual(invoice_line.lot_id, self.lot_b)

    def test_wizard_updates_restrict_lot_id_if_installed(self):
        if "restrict_lot_id" not in self.env["stock.move"]._fields:
            self.skipTest("stock_restrict_lot no está instalado")

        sale = self._sell(self.lot_a, 500.0, 2.0)
        line = sale.order_line
        move = line.move_ids.filtered(lambda m: m.state == "done")
        self.assertEqual(move.restrict_lot_id, self.lot_a)

        wizard = self._create_wizard(line)
        wizard.line_ids.new_lot_id = self.lot_b.id
        wizard.action_apply()

        self.assertEqual(move.restrict_lot_id, self.lot_b)

    def test_wizard_blocks_when_lot_already_invoiced_to_supplier(self):
        sale = self._sell(self.lot_a, 500.0, 2.0)
        line = sale.order_line

        self.lot_a.with_context(mercas_auto_invoiced=True).write({"invoiced": True})

        wizard = self._create_wizard(line)
        wizard.line_ids.new_lot_id = self.lot_b.id
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_wizard_allows_when_lot_has_only_advance_invoiced(self):
        sale = self._sell(self.lot_a, 500.0, 2.0)
        line = sale.order_line

        action = self.lot_a.action_create_supplier_invoices()
        advance_invoice = self.env["account.move"].browse(action["res_id"])
        advance_invoice.action_post()
        self.assertGreater(self.lot_a.net_invoiced_amount, 0.0)
        self.assertFalse(self.lot_a.invoiced)

        wizard = self._create_wizard(line)
        wizard.line_ids.new_lot_id = self.lot_b.id
        wizard.action_apply()

        self.assertEqual(line.lot_id, self.lot_b)

    def test_wizard_allows_when_lot_fully_invoiced_but_firm_negotiation(self):
        sale = self._sell(self.lot_a, 500.0, 2.0)
        line = sale.order_line

        self.lot_a.with_user(self.manager_user).write({"mercas_firm_negotiation": True})
        self.lot_a.with_context(mercas_auto_invoiced=True).write({"invoiced": True})

        wizard = self._create_wizard(line)
        wizard.line_ids.new_lot_id = self.lot_b.id
        wizard.action_apply()

        self.assertEqual(line.lot_id, self.lot_b)

    def test_wizard_access_denied_without_group(self):
        sale = self._sell(self.lot_a, 500.0, 2.0)
        line = sale.order_line
        other_user = self.env["res.users"].create({
            "name": "Sin permiso corrección",
            "login": "mercas_test_no_correct_lots",
            "email": "mercas_test_no_correct_lots@example.com",
            "group_ids": [
                Command.link(self.env.ref("stock.group_stock_user").id),
                Command.link(self.env.ref("sales_team.group_sale_salesman").id),
            ],
        })
        with self.assertRaises(UserError):
            self.env["stock.lot.change.wizard"].with_user(other_user).create({
                "sale_line_id": line.id,
            })
