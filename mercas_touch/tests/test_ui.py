import uuid

from odoo import Command
from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestMercasTouchUi(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_kg = cls.env.ref('uom.product_uom_kgm')
        cls.customer = cls.env['res.partner'].create({'name': 'Tour Customer', 'customer_rank': 1})
        cls.supplier = cls.env['res.partner'].create({'name': 'Tour Supplier', 'supplier_rank': 1})
        cls.box = cls.env['product.product'].create({
            'name': 'Tour Box', 'type': 'consu', 'is_storable': True, 'is_box': True, 'list_price': 0.0,
            'taxes_id': [Command.clear()], 'supplier_taxes_id': [Command.clear()],
        })
        cls.crate = cls.env['product.product'].create({
            'name': 'Tour Crate', 'default_code': 'CJ-77', 'type': 'consu', 'is_storable': True, 'is_box': True, 'list_price': 0.0,
            'taxes_id': [Command.clear()], 'supplier_taxes_id': [Command.clear()],
        })
        cls.pear = cls.env['product.product'].create({
            'name': 'Tour Pear', 'type': 'consu', 'is_storable': True, 'tracking': 'lot',
            'uom_id': cls.uom_kg.id, 'list_price': 2.0, 'box_product_id': cls.box.id,
            'taxes_id': [Command.clear()], 'supplier_taxes_id': [Command.clear()],
        })
        cls.user = new_test_user(
            cls.env, login='touch_tour', name='Touch Tour',
            groups='sales_team.group_sale_salesman_all_leads,purchase.group_purchase_user,'
                   'stock.group_stock_user,stock.group_production_lot,account.group_account_invoice',
        )
        # The tours tap the keypad of the screen: the browser of the tests has a mouse
        cls.user.mercas_touch_numpad = 'show'
        cls.env['mercas.touch'].with_user(cls.user).purchase({
            'uuid': str(uuid.uuid4()), 'partner_id': cls.supplier.id,
            'lines': [{'product_id': cls.pear.id, 'qty': 100.0, 'price_unit': 1.0, 'lot_name': 'TOUR-LOT'}],
        })
        cls.lot = cls.env['stock.lot'].search([('name', '=', 'TOUR-LOT')])

    def test_sale(self):
        if not self.env['account.journal'].search([('type', 'in', ('bank', 'cash')), ('company_id', '=', self.env.company.id)]):
            self.env['account.journal'].create({'name': 'Counter Cash', 'type': 'cash', 'code': 'TCSH'})
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_sale_tour', login='touch_tour')
        order = self.env['sale.order'].search([('partner_id', '=', self.customer.id)])
        self.assertEqual(order.state, 'sale')
        line = order.order_line.filtered(lambda l: l.product_id == self.pear)
        self.assertEqual(line.lot_id.name, 'TOUR-LOT')
        self.assertEqual(line.product_uom_qty, 12)
        self.assertEqual(line.price_unit, 1.5)
        self.assertEqual(line.box_qty, 2)
        self.assertEqual(line.box_product_id, self.crate, "The box chosen by typing, not the one of the product")
        self.assertTrue(all(picking.state == 'done' for picking in order.picking_ids))
        invoice = order.invoice_ids
        self.assertEqual(invoice.state, 'posted')
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'), "Invoiced and collected from the sale")

    def test_purchase_and_scrap(self):
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_purchase_tour', login='touch_tour')
        lot = self.env['stock.lot'].search([('name', '=', 'TOUR-NEW'), ('product_id', '=', self.pear.id)])
        self.assertEqual(lot.partner_id, self.supplier)
        self.assertEqual(lot.scrap_kg, 5)
        self.assertEqual(lot.product_qty, 75)

    def test_payment(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_line_ids': [Command.create({'product_id': self.pear.id, 'quantity': 50, 'price_unit': 2.0})],
        })
        invoice.action_post()
        if not self.env['account.journal'].search([('type', 'in', ('bank', 'cash')), ('company_id', '=', self.env.company.id)]):
            self.env['account.journal'].create({'name': 'Counter Cash', 'type': 'cash', 'code': 'TCSH'})
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_payment_tour', login='touch_tour')
        self.assertEqual(invoice.payment_state, 'partial')
        self.assertEqual(invoice.amount_residual, 40.0)

    def test_keyboard_lots(self):
        """ The lots with the keyboard: selected, priced and scrapped with the arrows and Enter. """
        self.env['mercas.touch'].with_user(self.user).purchase({
            'uuid': str(uuid.uuid4()), 'partner_id': self.supplier.id,
            'lines': [{'product_id': self.pear.id, 'qty': 50.0, 'price_unit': 1.0, 'lot_name': 'TOUR-LOT-2'}],
        })
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_keyboard_lots_tour', login='touch_tour')
        lots = self.env['stock.lot'].search([('name', 'in', ('TOUR-LOT', 'TOUR-LOT-2'))])
        priced = lots.filtered(lambda lot: lot.mercas_sale_price == 3)
        self.assertEqual(len(priced), 1)
        scrap = self.env['stock.scrap'].search([('lot_id', 'in', lots.ids), ('state', '=', 'done')])
        self.assertEqual((scrap.lot_id, scrap.scrap_qty), (priced, 1))

    def test_keyboard_pallets(self):
        """ The boxes put on pallets with the keyboard: the chips and the pallets with the arrows
        and Enter, the boxes to move typed. """
        self.env['stock.package.type'].create({'name': 'Tour Euro', 'mercas_is_pallet': True})
        draft = self.env['mercas.touch'].with_user(self.user).save_draft('sale', {
            'uuid': str(uuid.uuid4()), 'partner_id': self.customer.id, 'lines': [
                {'product_id': self.pear.id, 'lot_id': self.lot.id, 'qty': 40.0, 'price_unit': 2.0,
                 'box_qty': 8, 'box_product_id': self.box.id},
            ]})
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_keyboard_pallets_tour', login='touch_tour')
        pallets = self.env['mercas.touch'].get_pallets(draft['id'])['pallets']
        self.assertEqual([sum(line['box_qty'] for line in pallet['lines']) for pallet in pallets], [7])

    def test_keyboard_payment(self):
        """ A payment made with the keyboard: the invoice marked with the arrows and Enter, the
        amount, the journal with the arrows, the memo and the button. """
        invoices = self.env['account.move']
        for amount in (100.0, 30.0):
            invoices |= self.env['account.move'].create({
                'move_type': 'out_invoice', 'partner_id': self.customer.id,
                'invoice_line_ids': [Command.create({'product_id': self.pear.id, 'quantity': 1, 'price_unit': amount})],
            })
        invoices.action_post()
        for kind in ('bank', 'cash'):
            if not self.env['account.journal'].search_count([('type', '=', kind), ('company_id', '=', self.env.company.id)]):
                self.env['account.journal'].create({'name': f'Tour {kind}', 'code': f'T{kind[:2].upper()}', 'type': kind})
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_keyboard_payment_tour', login='touch_tour')
        self.assertEqual(invoices.mapped('amount_residual'), [100.0, 10.0])
        payment = self.env['account.payment'].search([('memo', '=', 'KEYBOARD')])
        self.assertEqual(payment.amount, 20.0)

    def test_quick_prices(self):
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_price_tour', login='touch_tour')
        order = self.env['sale.order'].search([('partner_id', '=', self.customer.id)])
        lines = order.order_line.filtered(lambda l: l.product_id == self.pear).sorted('id')
        self.assertEqual(lines.mapped('product_uom_qty'), [10, 5])
        self.assertEqual(lines.mapped('price_unit'), [2.5, 3.0])

    def test_enter_goes_through_the_line(self):
        """ Enter goes from a field of the line to the next one, and adds it in the last. """
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_enter_tour', login='touch_tour')
        line = self.env['sale.order'].search([('partner_id', '=', self.customer.id)]).order_line.filtered(
            lambda l: l.product_id == self.pear)
        self.assertEqual((line.product_uom_qty, line.price_unit, line.box_qty, line.box_product_id),
                         (12, 2.5, 2, self.box))

    def test_keyboard(self):
        """ The first field of each screen has the focus, and Enter in a search chooses the only
        record found: a sale made with the keyboard. """
        # A second lot, newer: the arrows go from the first one to it
        self.env['mercas.touch'].with_user(self.user).purchase({
            'uuid': str(uuid.uuid4()), 'partner_id': self.supplier.id,
            'lines': [{'product_id': self.pear.id, 'qty': 50.0, 'price_unit': 1.0, 'lot_name': 'TOUR-LOT-2'}],
        })
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_keyboard_tour', login='touch_tour')
        line = self.env['sale.order'].search([('partner_id', '=', self.customer.id)]).order_line
        self.assertEqual((line.product_id, line.lot_id.name, line.product_uom_qty), (self.pear, 'TOUR-LOT-2', 3))

    def test_keyboard_purchase(self):
        """ A purchase made with the keyboard: the supplier and the product chosen with the
        arrows and Enter, the line with Enter; then the boxes and the damaged label. """
        self.env['res.partner'].create({'name': 'Tour Supplier Bis', 'supplier_rank': 0})
        # Two journals to pay the boxes with: the arrows go from one to the other
        for kind in ('bank', 'cash'):
            if not self.env['account.journal'].search_count([('type', '=', kind), ('company_id', '=', self.env.company.id)]):
                self.env['account.journal'].create({'name': f'Tour {kind}', 'code': f'T{kind[:2].upper()}', 'type': kind})
        self.env['product.product'].create({
            'name': 'Tour Plum', 'type': 'consu', 'is_storable': True, 'tracking': 'lot',
            'uom_id': self.uom_kg.id, 'list_price': 3.0, 'categ_id': self.pear.categ_id.id,
        })
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_keyboard_purchase_tour', login='touch_tour')
        line = self.env['purchase.order.line'].search(
            ['|', ('lot_id.name', '=', 'TOUR-KEY'), ('mercas_touch_lot_name', '=', 'TOUR-KEY')])
        self.assertEqual((line.partner_id, line.product_id, line.product_qty, line.price_unit),
                         (self.supplier, self.pear, 20, 1))

    def test_without_numpad(self):
        """ With the keypad hidden in the preferences, everything is typed with the keyboard. """
        self.user.mercas_touch_numpad = 'hide'
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_no_numpad_tour', login='touch_tour')
        line = self.env['sale.order'].search([('partner_id', '=', self.customer.id)]).order_line.filtered(
            lambda l: l.product_id == self.pear)
        self.assertEqual((line.product_uom_qty, line.price_unit), (4, 2.5))

    def test_resume_quotation(self):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.pear.id, 'product_uom_qty': 7, 'lot_id': self.lot.id,
            })],
        })
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_quotation_tour', login='touch_tour')
        self.assertEqual(order.state, 'sale', "The quotation resumed is the one sold")
        self.assertEqual(order.order_line.filtered(lambda l: l.product_id == self.pear).mapped('product_uom_qty'), [7, 4])

    def test_purchase_drafts(self):
        other_supplier = self.env['res.partner'].create({'name': 'Backend Supplier', 'supplier_rank': 1})
        other = self.env['purchase.order'].create({'partner_id': other_supplier.id})
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_purchase_drafts_tour', login='touch_tour')
        first = self.env['purchase.order'].search([('partner_id', '=', self.supplier.id), ('state', '=', 'purchase')],
                                                  order='id desc', limit=1)
        self.assertEqual(first.order_line.filtered(lambda l: l.product_id == self.pear).lot_id.name, 'DRAFT-A')
        self.assertEqual(other.state, 'draft', "The other purchase is kept in draft")
        line = other.order_line.filtered(lambda l: l.product_id == self.pear)
        self.assertEqual((line.product_qty, line.mercas_touch_lot_name), (12, 'DRAFT-B'))
        self.assertFalse(self.env['stock.lot'].search([('name', '=', 'DRAFT-B')]),
                         "No lot is made before the purchase is received")

    def test_to_invoice(self):
        order = self.env['mercas.touch'].with_user(self.user).sell({
            'uuid': str(uuid.uuid4()), 'partner_id': self.customer.id,
            'lines': [{'product_id': self.pear.id, 'lot_id': self.lot.id, 'qty': 3.0, 'price_unit': 2.0}],
        })['order']
        # The advance of the purchase: only the billing administrators invoice the purchases
        self.user.group_ids += self.env.ref('account.group_account_manager')
        self.start_tour('/odoo/mercas-touch', 'mercas_touch_to_invoice_tour', login='touch_tour')
        self.assertEqual(self.env['sale.order'].browse(order['id']).invoice_status, 'invoiced')
        self.assertTrue(self.lot.supplier_invoice_line_ids, "The bill of the lot was made from the purchase")
