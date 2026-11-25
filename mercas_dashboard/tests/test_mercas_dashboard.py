import json
from datetime import date, timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMercasDashboards(TransactionCase):
    """ The data of the dashboards of Mercas give the figures of the management summary, and
    the spreadsheets use models and fields that exist. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Summary = cls.env["mercas.management.dashboard"]
        cls.Goods = cls.env["mercas.report.goods"]
        cls.customer = cls.env["res.partner"].create({"name": "Board Customer", "is_company": True})
        cls.contact = cls.env["res.partner"].create({"name": "Board Contact", "parent_id": cls.customer.id})
        cls.supplier = cls.env["res.partner"].create({"name": "Board Supplier"})
        kg = cls.env.ref("uom.product_uom_kgm")
        cls.box = cls.env["product.product"].create({
            "name": "Board Box", "is_storable": True, "is_box": True, "weight": 0.5,
        })
        cls.tomato = cls.env["product.product"].create({
            "name": "Board Tomato", "is_storable": True, "uom_id": kg.id, "taxes_id": [Command.clear()],
            "supplier_taxes_id": [Command.clear()],
        })
        # Sold by units: its weight counts
        cls.melon = cls.env["product.product"].create({
            "name": "Board Melon", "is_storable": True, "weight": 2.0, "taxes_id": [Command.clear()],
            "supplier_taxes_id": [Command.clear()],
        })
        # Sold in grams: converted to kg
        cls.gram = cls.env.ref("uom.product_uom_gram")

    def _figures(self, domain):
        groups = self.Goods._read_group(domain, [], ["amount:sum", "kg:sum"])
        return groups[0]

    def test_goods_as_the_summary(self):
        today = fields.Date.context_today(self.Summary)
        sales_before = self.Summary._mercas_sales_figures(date(2000, 1, 1), today)
        purchases_before = self.Summary._mercas_purchase_figures(date(2000, 1, 1), today)
        order = self.env["sale.order"].create({
            "partner_id": self.contact.id,
            "order_line": [
                Command.create({"product_id": self.tomato.id, "product_uom_qty": 40, "price_unit": 1.5}),
                Command.create({"product_id": self.tomato.id, "product_uom_qty": 500,
                                "product_uom_id": self.gram.id, "price_unit": 2.0}),
                Command.create({"product_id": self.melon.id, "product_uom_qty": 3, "price_unit": 4.0}),
                Command.create({"product_id": self.box.id, "product_uom_qty": 5, "price_unit": 1.0}),
            ],
        })
        order.action_confirm()
        purchase = self.env["purchase.order"].create({
            "partner_id": self.supplier.id,
            "order_line": [Command.create({"product_id": self.tomato.id, "product_qty": 100, "price_unit": 0.8})],
        })
        purchase.button_confirm()
        self.env.flush_all()
        sales = self.Summary._mercas_sales_figures(date(2000, 1, 1), today)
        purchases = self.Summary._mercas_purchase_figures(date(2000, 1, 1), today)

        amount, kg = self._figures([("kind", "=", "sale"), ("sale_order_id", "=", order.id)])
        self.assertAlmostEqual(amount, sales["amount"] - sales_before["amount"], places=2)
        self.assertAlmostEqual(kg, 40 + 0.5 + 6, msg="Without the boxes; grams in kg; units by their weight")
        self.assertAlmostEqual(kg, sales["kg"] - sales_before["kg"])
        lines = self.Goods.search([("sale_order_id", "=", order.id)])
        self.assertEqual(lines.partner_id, self.customer, "The company of the contact")
        self.assertNotIn(self.box, lines.product_id)

        amount, kg = self._figures([("kind", "=", "purchase"), ("purchase_order_id", "=", purchase.id)])
        self.assertAlmostEqual(amount, purchases["amount"] - purchases_before["amount"])
        self.assertAlmostEqual(kg, 100)

    def test_scrap(self):
        self.env["stock.quant"]._update_available_quantity(
            self.melon, self.env.ref("stock.stock_location_stock"), 10)
        scrap = self.env["stock.scrap"].create({"product_id": self.melon.id, "scrap_qty": 2})
        scrap.action_validate()
        # The reports read the tables: what the ORM still holds goes to the database first
        self.env.flush_all()
        line = self.Goods.search([("kind", "=", "scrap"), ("product_id", "=", self.melon.id)])
        self.assertAlmostEqual(line.kg, 4.0, msg="2 melons of 2 kg")
        today = fields.Date.context_today(self.Summary)
        self.assertGreaterEqual(self.Summary._mercas_purchase_figures(today, today)["scrap_kg"], 4.0)

    def test_debt_by_age(self):
        """ The open debt of the customers by days overdue, as the summary on the day. """
        journal = self.env["account.journal"].search([("type", "=", "sale"), ("company_id", "=", self.env.company.id)],
                                                     limit=1)
        today = fields.Date.context_today(self.Summary)
        invoices = self.env["account.move"]
        for days, amount in ((0, 100.0), (45, 30.0), (120, 20.0)):
            invoice = self.env["account.move"].create({
                "move_type": "out_invoice", "partner_id": self.contact.id, "journal_id": journal.id,
                "invoice_date": today - timedelta(days=days), "invoice_date_due": today - timedelta(days=days),
                "invoice_line_ids": [Command.create({"name": "Board", "quantity": 1, "price_unit": amount,
                                                     "tax_ids": [Command.clear()]})],
            })
            invoices |= invoice
        invoices.action_post()
        self.env.flush_all()
        balances = dict(self.env["mercas.report.balance"]._read_group(
            [("kind", "=", "customer"), ("partner_id", "=", self.customer.id)], ["age"], ["residual:sum"]))
        self.assertEqual(balances, {"0_not_due": 100.0, "2_60": 30.0, "4_over_90": 20.0})
        ages = self.Summary._mercas_customer_debt(today)["ages"]
        total = sum(self.env["mercas.report.balance"].search(
            [("kind", "=", "customer"), ("company_id", "=", self.env.company.id)]).mapped("residual"))
        self.assertAlmostEqual(total, sum(ages), places=2)

    def test_payments(self):
        journal = self.env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", self.env.company.id)],
                                                     limit=1)
        payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer", "partner_id": self.contact.id,
            "amount": 75.0, "journal_id": journal.id,
        })
        payment.action_post()
        self.env.flush_all()
        line = self.env["mercas.report.payment"].search([("payment_id", "=", payment.id)])
        self.assertEqual((line.amount, line.partner_id, line.journal_id), (75.0, self.customer, journal))

    def test_spreadsheets(self):
        """ The dashboards are in the group Mercas, only for the management, and their
        spreadsheets use models and fields that exist (checked by Odoo in the tests). """
        group = self.env.ref("mercas_dashboard.spreadsheet_dashboard_group_mercas")
        self.assertEqual(len(group.dashboard_ids), 3)
        for dashboard in group.dashboard_ids:
            self.assertEqual(dashboard.group_ids, self.env.ref("mercas_base.group_mercas_management"))
            dashboard._check_spreadsheet_data()
            data = json.loads(dashboard.spreadsheet_data)
            self.assertEqual([sheet["isVisible"] for sheet in data["sheets"]], [True, False],
                             "The sheet Data is hidden")
        # The management sees the data; a salesman doesn't
        manager = self.env["res.users"].create({
            "name": "Board Manager", "login": "board_manager",
            "group_ids": [Command.link(self.env.ref("sales_team.group_sale_manager").id)],
        })
        self.assertTrue(self.Goods.with_user(manager).search_count([]) >= 0)
        self.assertTrue(self.Goods.with_user(manager).has_access("read"))
        salesman = self.env["res.users"].create({
            "name": "Board Salesman", "login": "board_salesman",
            "group_ids": [Command.link(self.env.ref("sales_team.group_sale_salesman").id)],
        })
        self.assertFalse(self.Goods.with_user(salesman).has_access("read"))
