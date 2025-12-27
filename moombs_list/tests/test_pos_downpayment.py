# -*- coding: utf-8 -*-
"""
Test POS Down Payment Integration (Epic 5)
==========================================

Tests for the computed state machine and POS hooks.

Stories: Epic 5 - POS Down Payment Integration
"""

from odoo.tests import tagged, TransactionCase
from odoo.exceptions import UserError


@tagged('moombs', 'pos_downpayment')
class TestPOSDownPayment(TransactionCase):
    """Test POS Down Payment Integration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test data
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Beneficiary',
        })
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Test Vendor',
            'supplier_rank': 1,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
            'type': 'product',
            'seller_ids': [(0, 0, {
                'partner_id': cls.vendor.id,
                'price': 50.0,
            })],
        })
        cls.baby_list = cls.env['baby.list'].create({
            'partner_id': cls.partner.id,
            'expected_date': '2025-06-01',
        })
        cls.pending_location = cls.env.ref(
            'moombs_list.stock_location_pending_delivery'
        )
        cls.stock_location = cls.env.ref('stock.stock_location_stock')

    def _create_item(self):
        """Helper to create baby list item."""
        return self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product.id,
            'price_unit': self.product.list_price,
        })

    def _add_stock(self, qty=10):
        """Helper to add stock."""
        self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.stock_location.id,
            'quantity': qty,
        })

    # ================================================================
    # STATE COMPUTATION TESTS
    # ================================================================

    def test_state_initial_wished(self):
        """New item should have state 'wished'."""
        item = self._create_item()
        self.assertEqual(item.state, 'wished')

    def test_state_with_downpayment_no_stock_creates_po(self):
        """Item with pos_downpayment_id and PO should be 'po_draft'."""
        item = self._create_item()
        # Create a mock POS order
        pos_order = self.env['pos.order'].create({
            'partner_id': self.partner.id,
            'session_id': self._get_or_create_pos_session().id,
        })
        # Create a mock PO
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
        })
        item.write({
            'pos_downpayment_id': pos_order.id,
            'purchase_order_id': po.id,
        })
        self.assertEqual(item.state, 'po_draft')

    def test_state_priority_paid_over_pending(self):
        """'paid' should take priority over 'pending'."""
        item = self._create_item()
        self._add_stock(10)

        # Set up pending state - create INT picking to pending
        picking_type = self.env.ref('moombs_list.picking_type_internal_pending')
        int_picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.pending_location.id,
            'baby_list_item_id': item.id,
            'move_ids': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom': self.product.uom_id.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.pending_location.id,
            })],
        })
        int_picking.action_confirm()
        int_picking.action_assign()
        int_picking.button_validate()

        item.write({'picking_pending_id': int_picking.id})
        self.assertEqual(item.state, 'pending')

        # Add pos_order_id (100% paid) - should override
        pos_order = self.env['pos.order'].create({
            'partner_id': self.partner.id,
            'session_id': self._get_or_create_pos_session().id,
        })
        item.write({'pos_order_id': pos_order.id})
        self.assertEqual(item.state, 'paid')

    def test_state_cancelled_highest_priority(self):
        """Cancelled state has highest priority."""
        item = self._create_item()
        # Add various documents
        pos_order = self.env['pos.order'].create({
            'partner_id': self.partner.id,
            'session_id': self._get_or_create_pos_session().id,
        })
        item.write({
            'pos_downpayment_id': pos_order.id,
            'pos_order_id': pos_order.id,
        })
        # Cancel
        item.write({'is_cancelled': True})
        self.assertEqual(item.state, 'cancelled')

    # ================================================================
    # STATE TRANSITION TESTS
    # ================================================================

    def test_state_reserved_when_int_assigned(self):
        """State should be 'reserved' when INT is assigned."""
        item = self._create_item()
        self._add_stock(10)

        picking_type = self.env.ref('moombs_list.picking_type_internal_pending')
        int_picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.pending_location.id,
            'baby_list_item_id': item.id,
            'move_ids': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom': self.product.uom_id.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.pending_location.id,
            })],
        })
        int_picking.action_confirm()
        int_picking.action_assign()

        # Link and check state
        item.write({
            'picking_pending_id': int_picking.id,
            'pos_downpayment_id': self._create_mock_pos_order().id,
        })
        self.assertEqual(item.state, 'reserved')

    def test_state_pending_when_int_done(self):
        """State should be 'pending' when INT is done."""
        item = self._create_item()
        self._add_stock(10)

        picking_type = self.env.ref('moombs_list.picking_type_internal_pending')
        int_picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.pending_location.id,
            'baby_list_item_id': item.id,
            'move_ids': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom': self.product.uom_id.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.pending_location.id,
            })],
        })
        int_picking.action_confirm()
        int_picking.action_assign()
        int_picking.button_validate()

        # Link and check state
        item.write({
            'picking_pending_id': int_picking.id,
            'pos_downpayment_id': self._create_mock_pos_order().id,
        })
        self.assertEqual(item.state, 'pending')

    # ================================================================
    # DELIVERY TESTS
    # ================================================================

    def test_state_out_created_when_picking_exists(self):
        """State should be 'out_created' when delivery picking exists."""
        item = self._create_item()

        # Set up as paid first
        item.write({
            'pos_order_id': self._create_mock_pos_order().id,
        })
        self.assertEqual(item.state, 'paid')

        # Create delivery
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
        ], limit=1)
        customer_location = self.env.ref('stock.stock_location_customers')

        out_picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.pending_location.id,
            'location_dest_id': customer_location.id,
            'partner_id': self.partner.id,
            'baby_list_item_id': item.id,
            'move_ids': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom': self.product.uom_id.id,
                'location_id': self.pending_location.id,
                'location_dest_id': customer_location.id,
            })],
        })
        out_picking.action_confirm()

        item.write({'picking_out_id': out_picking.id})
        self.assertEqual(item.state, 'out_created')

    def test_action_create_delivery_from_paid(self):
        """action_create_delivery should work for paid items."""
        item = self._create_item()
        self._add_stock(10)

        # Set up stock in pending location
        self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.pending_location.id,
            'quantity': 1,
        })

        # Set up as paid
        item.write({
            'pos_order_id': self._create_mock_pos_order().id,
        })
        self.assertEqual(item.state, 'paid')

        # Create delivery
        result = item.action_create_delivery()
        self.assertTrue(item.picking_out_id)
        self.assertEqual(item.state, 'out_created')

    def test_action_create_delivery_fails_if_not_paid(self):
        """action_create_delivery should raise error if not paid."""
        item = self._create_item()
        self.assertEqual(item.state, 'wished')

        with self.assertRaises(UserError):
            item.action_create_delivery()

    # ================================================================
    # CANCEL TESTS
    # ================================================================

    def test_cancel_before_payment(self):
        """Can cancel item before payment."""
        item = self._create_item()
        item.write({'is_cancelled': True})
        self.assertEqual(item.state, 'cancelled')

    def test_is_active_false_when_cancelled(self):
        """is_active should be False when cancelled."""
        item = self._create_item()
        self.assertTrue(item.is_active)
        item.write({'is_cancelled': True})
        self.assertFalse(item.is_active)

    def test_is_active_false_when_delivered(self):
        """is_active should be False when delivered."""
        item = self._create_item()
        self.assertTrue(item.is_active)

        # Set up as delivered
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
        ], limit=1)
        customer_location = self.env.ref('stock.stock_location_customers')
        self._add_stock(10)

        out_picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.stock_location.id,
            'location_dest_id': customer_location.id,
            'partner_id': self.partner.id,
            'baby_list_item_id': item.id,
            'move_ids': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom': self.product.uom_id.id,
                'location_id': self.stock_location.id,
                'location_dest_id': customer_location.id,
            })],
        })
        out_picking.action_confirm()
        out_picking.action_assign()
        out_picking.button_validate()

        item.write({'picking_out_id': out_picking.id})
        self.assertEqual(item.state, 'delivered')
        self.assertFalse(item.is_active)

    # ================================================================
    # HELPER METHODS
    # ================================================================

    def _get_or_create_pos_session(self):
        """Get or create a POS session for testing."""
        pos_config = self.env['pos.config'].search([], limit=1)
        if not pos_config:
            pos_config = self.env['pos.config'].create({
                'name': 'Test POS',
            })
        session = self.env['pos.session'].search([
            ('config_id', '=', pos_config.id),
            ('state', '=', 'opened'),
        ], limit=1)
        if not session:
            session = self.env['pos.session'].create({
                'config_id': pos_config.id,
            })
        return session

    def _create_mock_pos_order(self):
        """Create a mock POS order for testing."""
        return self.env['pos.order'].create({
            'partner_id': self.partner.id,
            'session_id': self._get_or_create_pos_session().id,
        })
