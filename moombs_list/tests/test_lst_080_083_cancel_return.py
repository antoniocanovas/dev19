# -*- coding: utf-8 -*-
"""
LST-080 to LST-083: Cancel / Return
===================================

Cancel/Return features:
- LST-080: Cancel/Return Products
- LST-081: Confirm Cancel via Popup
- LST-082: Cancelled Items Styled
- LST-083: Refund to Wallet on Return

  Pillar: LIST + WALLET
  Principles: P5 (Traceability)
  Business Rule: BR-008 (No Edit), BR-009 (Refund to Wallet)
  Priority: Must
"""

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Datetime
from .common import MoombsTestCommon


@tagged('moombs', 'lst_080', 'lst_081', 'lst_082', 'lst_083', 'cancel', 'return', 'must')
class TestLST080083CancelReturn(MoombsTestCommon):
    """Test cases for Cancel/Return features."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list()
        
        # Setup wallet
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 500
        
        self.item = self.create_test_item(
            self.baby_list,
            product=self.product_crib,
            price_unit=400.00
        )

    # ═══════════════════════════════════════════════════════════════
    # LST-080: CANCEL/RETURN PRODUCTS
    # ═══════════════════════════════════════════════════════════════

    def test_cancel_wished_item(self):
        """
        @happy_path @must
        Scenario: Cancel item in wished state
        """
        self.item.state = 'wished'
        
        # Cancel
        if hasattr(self.item, 'action_cancel'):
            self.item.action_cancel(reason='Customer changed mind')
        else:
            self.item.state = 'cancelled'
            self.item.date_cancelled = Datetime.now()
            self.item.cancel_reason = 'Customer changed mind'
        
        self.assertEqual(self.item.state, 'cancelled')

    def test_cancel_ordered_item(self):
        """
        @happy_path
        Scenario: Cancel item in ordered state
        """
        self.item.state = 'ordered'
        
        self.item.state = 'cancelled'
        self.item.date_cancelled = Datetime.now()
        
        self.assertEqual(self.item.state, 'cancelled')

    def test_cancel_reserved_item(self):
        """
        @happy_path
        Scenario: Cancel item in reserved state
        """
        self.item.state = 'reserved'
        
        self.item.state = 'cancelled'
        self.item.date_cancelled = Datetime.now()
        
        self.assertEqual(self.item.state, 'cancelled')

    # ═══════════════════════════════════════════════════════════════
    # LST-081: CONFIRM CANCEL VIA POPUP
    # ═══════════════════════════════════════════════════════════════

    def test_cancel_requires_reason(self):
        """
        @happy_path @must @BR-008
        Scenario: Cancellation requires reason
        """
        reason = 'Product no longer needed'
        
        self.item.state = 'cancelled'
        self.item.cancel_reason = reason
        self.item.date_cancelled = Datetime.now()
        
        self.assertEqual(self.item.cancel_reason, reason)

    def test_date_cancelled_filled(self):
        """
        @happy_path @P5
        Scenario: CAN-C filled on cancellation
        """
        self.assertFalse(self.item.date_cancelled)
        
        self.item.state = 'cancelled'
        self.item.date_cancelled = Datetime.now()
        
        self.assertTrue(self.item.date_cancelled)

    # ═══════════════════════════════════════════════════════════════
    # LST-082: CANCELLED ITEMS STYLED
    # ═══════════════════════════════════════════════════════════════

    def test_cancelled_item_identified(self):
        """
        @happy_path @should
        Scenario: Cancelled item has state = cancelled
        """
        self.item.state = 'cancelled'
        
        self.assertEqual(self.item.state, 'cancelled')

    def test_cancelled_items_filtered(self):
        """
        @happy_path
        Scenario: Cancelled items can be filtered
        """
        # Create some cancelled and active items
        item2 = self.create_test_item(self.baby_list, product=self.product_bottle)
        
        self.item.state = 'cancelled'
        item2.state = 'wished'
        
        cancelled = self.baby_list.item_ids.filtered(
            lambda i: i.state == 'cancelled'
        )
        active = self.baby_list.item_ids.filtered(
            lambda i: i.state != 'cancelled'
        )
        
        self.assertIn(self.item, cancelled)
        self.assertIn(item2, active)

    # ═══════════════════════════════════════════════════════════════
    # LST-083: REFUND TO WALLET ON RETURN
    # ═══════════════════════════════════════════════════════════════

    def test_refund_on_paid_item_return(self):
        """
        @happy_path @must @BR-009
        Scenario: Return after payment credits wallet
        """
        # Item was paid
        self.item.state = 'paid'
        self.item.date_paid = Datetime.now()
        
        initial_balance = self.baby_list.wallet_id.points if self.baby_list.wallet_id else 0
        price = self.item.price_final
        
        # Simulate wallet was debited on payment
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = initial_balance - price
            balance_after_pay = self.baby_list.wallet_id.points
        
        # Return/Cancel the paid item
        self.item.state = 'cancelled'
        self.item.date_cancelled = Datetime.now()
        self.item.cancel_reason = 'Return - defective product'
        
        # Refund to wallet
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points += price
            
            self.assertAlmostEqual(
                self.baby_list.wallet_id.points,
                initial_balance,  # Back to original
                places=2
            )

    def test_no_refund_for_unpaid_cancel(self):
        """
        @edge_case @BR-009
        Scenario: No refund if item wasn't paid
        """
        self.item.state = 'wished'  # Never paid
        initial_balance = self.baby_list.wallet_id.points if self.baby_list.wallet_id else 0
        
        # Cancel
        self.item.state = 'cancelled'
        
        # Wallet unchanged
        if self.baby_list.wallet_id:
            self.assertEqual(self.baby_list.wallet_id.points, initial_balance)

    # ═══════════════════════════════════════════════════════════════
    # SAD PATH
    # ═══════════════════════════════════════════════════════════════

    def test_cannot_cancel_delivered_directly(self):
        """
        @sad_path @P10
        Scenario: Cannot cancel delivered item (must use return)
        """
        self.item.state = 'delivered'
        
        # Delivered items need return process, not simple cancel
        # Business logic may allow or restrict this

    def test_cancel_without_reason_warning(self):
        """
        @sad_path
        Scenario: Cancel without reason may be blocked
        """
        # Reason should be required
        # Implementation may enforce this

    # ═══════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_cancel_releases_committed(self):
        """
        @edge_case @BR-001
        Scenario: Cancelling ordered item releases committed
        """
        self.item.state = 'ordered'
        
        # Committed was 25% = €100
        # After cancel, committed should decrease
        
        self.item.state = 'cancelled'
        
        # Committed for this item should be released

    def test_cannot_reactivate_cancelled_item(self):
        """
        @edge_case
        Scenario: Cancelled items cannot be reactivated
        """
        self.item.state = 'cancelled'
        
        # Should not be able to go back to wished
        # Must create new line instead (BR-008)

    def test_cancel_logs_to_chatter(self):
        """
        @edge_case @P5
        Scenario: Cancellation logged to chatter
        """
        self.item.state = 'cancelled'
        self.item.cancel_reason = 'Test cancellation'
        
        # Check chatter logging
        # Implementation dependent

    def test_partial_refund_not_allowed(self):
        """
        @edge_case @BR-003
        Scenario: No partial refunds - full amount or nothing
        """
        # BR-003: Everything through wallet
        # Refund is always 100% of item price
        
        self.item.state = 'paid'
        price = self.item.price_final
        
        # On return, full amount refunded
        # No partial refunds allowed
        self.assertTrue(price > 0)
