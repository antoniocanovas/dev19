from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBoxLabel70x50(TransactionCase):
    """The 70 x 50 format of the label wizard of mercas_base prints its own
    report: one label per box, one label per page."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({
            "name": "Apple",
            "type": "consu",
            "is_storable": True,
            "tracking": "lot",
        })
        cls.lot = cls.env["stock.lot"].create({
            "name": "MARI-001",
            "product_id": cls.product.id,
            "company_id": cls.env.company.id,
        })

    def test_70x50_prints_one_label_per_page(self):
        action = self.lot.action_print_mercas_labels()
        wizard = self.env["mercas.label.print.wizard"].with_context(action["context"]).create({
            "print_format": "70x50",
        })
        wizard.line_ids.quantity = 3
        report_action = wizard.action_print()
        self.assertEqual(report_action["report_name"], "custom_maripili.report_box_label_70x50")

        report = self.env.ref("custom_maripili.action_report_box_label_70x50")
        paper = report.paperformat_id
        self.assertEqual((paper.page_width, paper.page_height), (70, 50))
        html = self.env["ir.actions.report"]._render_qweb_html(
            report, None, data=report_action["data"]
        )[0]
        self.assertEqual(html.count(b'class="o_label_sheet"'), 3)
        self.assertIn(b"MARI-001", html)

    def test_other_formats_keep_mercas_reports(self):
        action = self.lot.action_print_mercas_labels()
        wizard = self.env["mercas.label.print.wizard"].with_context(action["context"]).create({
            "print_format": "dymo",
        })
        self.assertEqual(wizard.action_print()["report_name"], "mercas_base.report_mercas_box_label_dymo")
