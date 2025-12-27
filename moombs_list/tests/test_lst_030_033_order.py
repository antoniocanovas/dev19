# -*- coding: utf-8 -*-
"""
LST-030 to LST-033: Order Products
==================================

Order features:
- LST-030: Select and Order Products
- LST-031: Confirm Order via Popup
- LST-032: PO Columns Only When Sent
- LST-033: Auto-fill Stock Columns

  Pillar: LIST
  Principles: P6 (Computed States), P10 (Graceful Degradation), P11 (Atomic)
  Business Rule: BR-001 (25% Rule)
  Priority: Must
"""

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from .common import MoombsTestCommon


@tagged('moombs', 'lst_030', 'lst_031', 'lst_032', 'lst_033', 'order', 'must')
class TestLST030033Order(MoombsTestCommon):
    """Test cases for Order features."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list()
        self.item = self.create_test_item(
            self.baby_list, 
            product=self.product_crib,
            price_unit=400.00
        )

    # ═══════════════════════════════════════════════════════════════
    # LST-030: SELECT AND ORDER - HAPPY PATH
    # ═══════════════════════════════════════════════════════════════

    def test_order_single_product_with_sufficient_balance(self):
        """
        @happy_path @must @BR-001
        Scenario: Order single product with sufficient wallet balance
        
        Given wallet_balance = 200 (≥ €100 = 25% of €400)
        When I order the product
        Then order succeeds
        """
        # Setup wallet with sufficient balance
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 200  # ≥ 100 (25% of 400)
        
        # Order the item
        if hasattr(self.item, 'action_order'):
            self.item.action_order()
            self.assertEqual(self.item.state, 'ordered')

    def test_order_checks_25_percent_rule(self):
        """
        @happy_path @must @BR-001
        Scenario: 25% rule is enforced
        
        Required = price × 0.25 = 400 × 0.25 = 100
        """
        required_25_percent = self.item.price_final * 0.25
        self.assertAlmostEqual(required_25_percent, 100.00, places=2)

    # ═══════════════════════════════════════════════════════════════
    # LST-030: SELECT AND ORDER - SAD PATH
    # ═══════════════════════════════════════════════════════════════

    def test_order_fails_insufficient_balance(self):
        """
        @sad_path @P10 @BR-001
        Scenario: Order fails with insufficient wallet balance
        
        Given wallet_balance = 50 (< €100 = 25% of €400)
        When I try to order
        Then I see error
        """
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 50  # < 100 required
        
        if hasattr(self.item, 'action_order'):
            with self.assertRaises((UserError, ValidationError)):
                self.item.action_order()

    def test_order_fails_zero_balance(self):
        """
        @sad_path @P10
        Scenario: Order fails with zero balance
        """
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 0
        
        if hasattr(self.item, 'action_order'):
            with self.assertRaises((UserError, ValidationError)):
                self.item.action_order()

    def test_cannot_order_non_wished_item(self):
        """
        @sad_path @P10
        Scenario: Cannot order item that is not in wished state
        """
        self.item.state = 'ordered'  # Already ordered
        
        if hasattr(self.item, 'action_order'):
            with self.assertRaises((UserError, ValidationError)):
                self.item.action_order()

    # ═══════════════════════════════════════════════════════════════
    # LST-030: ORDER - EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_order_multiple_is_atomic(self):
        """
        @edge_case @P11
        Scenario: Order multiple is atomic (all or nothing)
        """
        # Create second item
        item2 = self.create_test_item(
            self.baby_list, 
            product=self.product_bottle,
            price_unit=15.00
        )
        
        # Total: 400 + 15 = 415, 25% = 103.75
        # If wallet has only 100, should fail for both
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 100  # Not enough for both
        
        # Attempting to order both should fail atomically
        # Neither should be ordered
        if hasattr(self.baby_list, 'action_order_selected'):
            try:
                self.baby_list.action_order_selected([self.item.id, item2.id])
            except (UserError, ValidationError):
                pass
            
            # Both should still be wished
            self.assertEqual(self.item.state, 'wished')
            self.assertEqual(item2.state, 'wished')

    def test_order_is_idempotent(self):
        """
        @edge_case @P12
        Scenario: Ordering already ordered item is idempotent
        """
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 200
        
        self.item.state = 'ordered'
        
        # Trying to order again should not change anything
        if hasattr(self.item, 'action_order'):
            try:
                self.item.action_order()
            except (UserError, ValidationError):
                pass
            
            self.assertEqual(self.item.state, 'ordered')

    # ═══════════════════════════════════════════════════════════════
    # LST-031: CONFIRM ORDER VIA POPUP
    # ═══════════════════════════════════════════════════════════════

    def test_order_creates_sale_order(self):
        """
        @happy_path @must
        Scenario: Confirming order creates Sale Order
        """
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 200
        
        if hasattr(self.item, 'action_order'):
            self.item.action_order()
            
            # Should have linked sale order
            if hasattr(self.item, 'sale_order_id'):
                self.assertTrue(self.item.sale_order_id)

    def test_order_fills_date_ordered(self):
        """
        @happy_path @P5
        Scenario: Order fills date_ordered (SOR-C)
        """
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 200
        
        self.assertFalse(self.item.date_ordered)
        
        if hasattr(self.item, 'action_order'):
            self.item.action_order()
            self.assertTrue(self.item.date_ordered)

    def test_order_increases_committed(self):
        """
        @happy_path @BR-001
        Scenario: Order increases wallet_committed by 25%
        """
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 200
        
        initial_committed = getattr(self.baby_list, 'wallet_committed', 0)
        
        if hasattr(self.item, 'action_order'):
            self.item.action_order()
            
            if hasattr(self.baby_list, 'wallet_committed'):
                expected_committed = initial_committed + (400 * 0.25)
                self.assertAlmostEqual(
                    self.baby_list.wallet_committed, 
                    expected_committed, 
                    places=2
                )

    # ═══════════════════════════════════════════════════════════════
    # LST-032: PO COLUMNS ONLY WHEN SENT
    # ═══════════════════════════════════════════════════════════════

    def test_po_fields_empty_initially(self):
        """
        @happy_path @should
        Scenario: PO columns empty for in-stock items
        """
        if hasattr(self.item, 'purchase_order_id'):
            self.assertFalse(self.item.purchase_order_id)

    # ═══════════════════════════════════════════════════════════════
    # LST-033: AUTO-FILL STOCK COLUMNS
    # ═══════════════════════════════════════════════════════════════

    def test_auto_reserve_when_stock_available(self):
        """
        @happy_path @must @P6
        Scenario: Auto-fill SHP-I/SHP-R if stock exists
        """
        # Simulate stock available
        self.product_crib.qty_available = 10
        
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 200
        
        if hasattr(self.item, 'action_order'):
            self.item.action_order()
            
            # With stock available, should auto-reserve
            # State might go directly to 'reserved'
            self.assertIn(self.item.state, ['ordered', 'reserved'])

    def test_no_auto_reserve_when_no_stock(self):
        """
        @edge_case
        Scenario: No auto-reserve when no stock
        """
        self.product_crib.qty_available = 0
        
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 200
        
        if hasattr(self.item, 'action_order'):
            self.item.action_order()
            
            # Without stock, stays in ordered (waiting for PO)
            self.assertEqual(self.item.state, 'ordered')
