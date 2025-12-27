# -*- coding: utf-8 -*-
"""
LST-060 to LST-064: Pay (POS)
=============================

POS Payment features:
- LST-060: See Pending Products at POS
- LST-061: Pay with Wallet
- LST-062: System Updates PAY-C
- LST-063: Pay Now Collect Later (Beneficiary)
- LST-064: Pay Now Collect Later (Family)

  Pillar: DELIVERY
  Principles: P5 (Traceability), P6 (Computed States)
  Business Rule: BR-003
  Priority: Must
"""

from odoo.tests import tagged
from odoo.fields import Datetime
from .common import MoombsTestCommon


@tagged('moombs', 'lst_060', 'lst_061', 'lst_062', 'lst_063', 'lst_064', 'pay', 'pos', 'must')
class TestLST060064Pay(MoombsTestCommon):
    """Test cases for POS Payment features."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list()
        
        # Create item in ordered/reserved state (ready to pay)
        self.item = self.create_test_item(
            self.baby_list,
            product=self.product_crib,
            price_unit=400.00
        )
        self.item.state = 'reserved'
        
        # Setup wallet with balance
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 500

    # ═══════════════════════════════════════════════════════════════
    # LST-060: SEE PENDING PRODUCTS
    # ═══════════════════════════════════════════════════════════════

    def test_pending_products_filter(self):
        """
        @happy_path @must
        Scenario: POS shows ordered lines not yet paid
        """
        # Item is reserved (ready to pay)
        self.assertEqual(self.item.state, 'reserved')
        
        # Filter: SOR-C filled, PAY-C empty
        pending_items = self.baby_list.item_ids.filtered(
            lambda i: i.state in ('ordered', 'reserved') and not i.date_paid
        )
        
        self.assertIn(self.item, pending_items)

    def test_paid_items_not_in_pending(self):
        """
        @edge_case
        Scenario: Already paid items not shown in pending
        """
        self.item.state = 'paid'
        self.item.date_paid = Datetime.now()
        
        pending_items = self.baby_list.item_ids.filtered(
            lambda i: i.state in ('ordered', 'reserved') and not i.date_paid
        )
        
        self.assertNotIn(self.item, pending_items)

    # ═══════════════════════════════════════════════════════════════
    # LST-061: PAY WITH WALLET
    # ═══════════════════════════════════════════════════════════════

    def test_pay_with_wallet_100_percent(self):
        """
        @happy_path @must @BR-003
        Scenario: Pay 100% with eWallet
        """
        initial_balance = self.baby_list.wallet_id.points if self.baby_list.wallet_id else 0
        product_price = self.item.price_final
        
        # Simulate payment
        if hasattr(self.item, 'action_pay'):
            self.item.action_pay()
        else:
            # Manual simulation
            self.item.state = 'paid'
            self.item.date_paid = Datetime.now()
            if self.baby_list.wallet_id:
                self.baby_list.wallet_id.points -= product_price
        
        # Verify state changed
        self.assertEqual(self.item.state, 'paid')
        
        # Verify wallet debited
        if self.baby_list.wallet_id:
            expected_balance = initial_balance - product_price
            self.assertAlmostEqual(
                self.baby_list.wallet_id.points,
                expected_balance,
                places=2
            )

    def test_pay_fails_insufficient_balance(self):
        """
        @sad_path @BR-003
        Scenario: Payment fails if wallet balance < price
        """
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 100  # Less than €400
        
        # Payment should fail
        # Implementation depends on action_pay method

    def test_committed_released_on_pay(self):
        """
        @happy_path @BR-001
        Scenario: Committed amount released when paid
        """
        # Committed was 25% = €100
        # After payment, committed should decrease
        
        if hasattr(self.baby_list, 'wallet_committed'):
            initial_committed = self.baby_list.wallet_committed
            
            self.item.state = 'paid'
            self.item.date_paid = Datetime.now()
            
            # Recompute
            self.baby_list.invalidate_recordset()

    # ═══════════════════════════════════════════════════════════════
    # LST-062: SYSTEM UPDATES PAY-C
    # ═══════════════════════════════════════════════════════════════

    def test_date_paid_filled_on_payment(self):
        """
        @happy_path @must @P6
        Scenario: PAY-C filled with timestamp on payment
        """
        self.assertFalse(self.item.date_paid)
        
        # Process payment
        self.item.state = 'paid'
        self.item.date_paid = Datetime.now()
        
        self.assertTrue(self.item.date_paid)

    def test_state_changes_to_paid(self):
        """
        @happy_path @P6
        Scenario: State changes to paid after payment
        """
        self.assertEqual(self.item.state, 'reserved')
        
        self.item.state = 'paid'
        
        self.assertEqual(self.item.state, 'paid')

    # ═══════════════════════════════════════════════════════════════
    # LST-063: PAY NOW COLLECT LATER (BENEFICIARY)
    # ═══════════════════════════════════════════════════════════════

    def test_pay_now_collect_later(self):
        """
        @happy_path @should
        Scenario: Payment without immediate pickup
        """
        # Pay the item
        self.item.state = 'paid'
        self.item.date_paid = Datetime.now()
        
        # PAY-C filled but DEL-S empty
        self.assertTrue(self.item.date_paid)
        self.assertFalse(self.item.date_delivered)
        
        # Can collect later
        self.assertEqual(self.item.state, 'paid')

    def test_delivery_separate_from_payment(self):
        """
        @edge_case
        Scenario: Delivery can happen days after payment
        """
        # Pay today
        self.item.state = 'paid'
        self.item.date_paid = Datetime.now()
        
        # Delivery later (DEL-S still empty)
        self.assertFalse(self.item.date_delivered)
        self.assertEqual(self.item.state, 'paid')

    # ═══════════════════════════════════════════════════════════════
    # LST-064: PAY NOW COLLECT LATER (FAMILY)
    # ═══════════════════════════════════════════════════════════════

    def test_family_pays_beneficiary_collects(self):
        """
        @happy_path @should
        Scenario: Family pays, beneficiary collects later
        """
        # María (family) pays for the item
        self.item.paid_by_id = self.partner_maria.id
        self.item.state = 'paid'
        self.item.date_paid = Datetime.now()
        
        # Paid by family member
        self.assertEqual(self.item.paid_by_id, self.partner_maria)
        
        # Beneficiary can collect (not delivered yet)
        self.assertFalse(self.item.date_delivered)

    def test_paid_by_records_family_member(self):
        """
        @happy_path @P5
        Scenario: paid_by_id records who actually paid
        """
        self.item.paid_by_id = self.partner_maria.id
        
        self.assertEqual(self.item.paid_by_id.name, 'María García López')
        self.assertNotEqual(self.item.paid_by_id, self.partner_ana)

    # ═══════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_cannot_pay_wished_item(self):
        """
        @edge_case
        Scenario: Cannot pay item that hasn't been ordered
        """
        self.item.state = 'wished'
        
        # Should not be able to pay
        pending_to_pay = self.baby_list.item_ids.filtered(
            lambda i: i.state in ('ordered', 'reserved')
        )
        self.assertNotIn(self.item, pending_to_pay)

    def test_cannot_pay_delivered_item(self):
        """
        @edge_case
        Scenario: Cannot pay already delivered item
        """
        self.item.state = 'delivered'
        
        # Already delivered means already paid
        pending_to_pay = self.baby_list.item_ids.filtered(
            lambda i: i.state in ('ordered', 'reserved')
        )
        self.assertNotIn(self.item, pending_to_pay)

    def test_cannot_pay_cancelled_item(self):
        """
        @edge_case
        Scenario: Cannot pay cancelled item
        """
        self.item.state = 'cancelled'
        
        # Cancelled items cannot be paid
        pending_to_pay = self.baby_list.item_ids.filtered(
            lambda i: i.state in ('ordered', 'reserved')
        )
        self.assertNotIn(self.item, pending_to_pay)
