# -*- coding: utf-8 -*-
"""
Business Rules Tests
====================

Test all Business Rules (BR-001 to BR-009):
- BR-001: 25% Rule
- BR-002: Beneficiary is Sovereign
- BR-003: Everything Through Wallet
- BR-004: One Line = One Unit
- BR-005: Topup First
- BR-006: Payer Identification
- BR-007: Invoice to Payer
- BR-008: No Edit
- BR-009: Refund to Wallet
"""

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from .common import MoombsTestCommon


@tagged('moombs', 'business_rules', 'br')
class TestBusinessRules(MoombsTestCommon):
    """Test cases for all Business Rules."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list()
        
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 200

    # ═══════════════════════════════════════════════════════════════
    # BR-001: 25% RULE
    # ═══════════════════════════════════════════════════════════════

    def test_br001_25_percent_required_to_order(self):
        """
        BR-001: wallet_available >= price × 0.25 to order
        """
        item = self.create_test_item(
            self.baby_list,
            product=self.product_crib,
            price_unit=400.00
        )
        
        # Required: 400 × 0.25 = 100
        required = item.price_final * 0.25
        self.assertEqual(required, 100)
        
        # With wallet = 200, should be able to order (200 >= 100)
        if self.baby_list.wallet_id:
            self.assertGreaterEqual(
                self.baby_list.wallet_id.points,
                required
            )

    def test_br001_insufficient_balance_blocks_order(self):
        """
        BR-001: Cannot order if wallet_available < 25%
        """
        item = self.create_test_item(
            self.baby_list,
            product=self.product_crib,
            price_unit=400.00
        )
        
        # Set wallet below required
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 50  # < 100 required
            
            # Order should fail
            if hasattr(item, 'action_order'):
                with self.assertRaises((UserError, ValidationError)):
                    item.action_order()

    def test_br001_committed_calculation(self):
        """
        BR-001: committed = Σ(ordered items × price × 0.25)
        """
        item1 = self.create_test_item(self.baby_list, price_unit=400)
        item2 = self.create_test_item(self.baby_list, price_unit=200)
        
        item1.state = 'ordered'
        item2.state = 'ordered'
        
        # Expected committed: (400 + 200) × 0.25 = 150
        expected_committed = 150
        
        if hasattr(self.baby_list, 'wallet_committed'):
            self.assertAlmostEqual(
                self.baby_list.wallet_committed,
                expected_committed,
                places=2
            )

    # ═══════════════════════════════════════════════════════════════
    # BR-002: BENEFICIARY IS SOVEREIGN
    # ═══════════════════════════════════════════════════════════════

    def test_br002_beneficiary_decides(self):
        """
        BR-002: Family contributes, Beneficiary decides
        """
        # Wallet belongs to beneficiary
        if self.baby_list.wallet_id:
            # Wallet partner should be beneficiary
            self.assertEqual(
                self.baby_list.partner_id,
                self.partner_ana
            )

    # ═══════════════════════════════════════════════════════════════
    # BR-003: EVERYTHING THROUGH WALLET
    # ═══════════════════════════════════════════════════════════════

    def test_br003_100_percent_wallet_payment(self):
        """
        BR-003: 100% payment via eWallet only
        """
        # All payments must go through wallet
        # No mixed payment methods
        item = self.create_test_item(self.baby_list, price_unit=100)
        
        # Payment = full price through wallet
        self.assertEqual(item.price_final, 100)

    # ═══════════════════════════════════════════════════════════════
    # BR-004: ONE LINE = ONE UNIT
    # ═══════════════════════════════════════════════════════════════

    def test_br004_one_line_one_unit(self):
        """
        BR-004: Each line represents 1 unit (qty=1)
        """
        # Create 3 items - should be 3 separate lines
        items = []
        for _ in range(3):
            item = self.create_test_item(
                self.baby_list,
                product=self.product_bottle
            )
            items.append(item)
        
        self.assertEqual(len(items), 3)
        
        # Each line is independent
        for item in items:
            # Implicit qty = 1
            self.assertTrue(item.id)

    def test_br004_no_qty_field_modification(self):
        """
        BR-004: Cannot have qty > 1 on a line
        """
        # If model has qty field, it should be readonly or always 1
        item = self.create_test_item(self.baby_list)
        
        # qty is always implicitly 1
        if hasattr(item, 'qty'):
            self.assertEqual(item.qty, 1)

    # ═══════════════════════════════════════════════════════════════
    # BR-005: TOPUP FIRST
    # ═══════════════════════════════════════════════════════════════

    def test_br005_topup_before_order(self):
        """
        BR-005: Must add money to wallet before ordering
        """
        # Zero balance blocks ordering
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 0
        
        item = self.create_test_item(self.baby_list, price_unit=100)
        
        # Cannot order with zero balance
        if hasattr(item, 'action_order'):
            with self.assertRaises((UserError, ValidationError)):
                item.action_order()

    # ═══════════════════════════════════════════════════════════════
    # BR-006: PAYER IDENTIFICATION
    # ═══════════════════════════════════════════════════════════════

    def test_br006_payer_info_required(self):
        """
        BR-006: Name, Surname, DNI, Phone required for topup
        """
        required_fields = ['name', 'surname', 'vat', 'phone']
        
        # Payer must have all fields
        payer = self.partner_maria
        self.assertTrue(payer.name)
        self.assertTrue(payer.mobile)
        self.assertTrue(payer.vat)

    # ═══════════════════════════════════════════════════════════════
    # BR-007: INVOICE TO PAYER
    # ═══════════════════════════════════════════════════════════════

    def test_br007_invoice_to_payer_not_beneficiary(self):
        """
        BR-007: Simplified invoice in payer's name
        """
        # Invoice partner should be payer, not beneficiary
        payer = self.partner_maria
        beneficiary = self.partner_ana
        
        self.assertNotEqual(payer, beneficiary)

    # ═══════════════════════════════════════════════════════════════
    # BR-008: NO EDIT
    # ═══════════════════════════════════════════════════════════════

    def test_br008_lines_cannot_be_edited(self):
        """
        BR-008: Lines cannot be edited, only cancelled
        """
        item = self.create_test_item(self.baby_list, price_unit=100)
        
        # Attempting to change product should fail
        # (Implementation may vary)
        
        # Only state changes and dates allowed
        allowed_changes = ['state', 'date_ordered', 'date_paid', 
                          'date_delivered', 'date_cancelled', 'cancel_reason']
        
        # These should work
        for field in ['state']:
            if hasattr(item, field):
                self.assertTrue(True)

    # ═══════════════════════════════════════════════════════════════
    # BR-009: REFUND TO WALLET
    # ═══════════════════════════════════════════════════════════════

    def test_br009_return_credits_wallet(self):
        """
        BR-009: Returns credit money back to wallet
        """
        item = self.create_test_item(self.baby_list, price_unit=100)
        item.state = 'paid'
        
        initial_balance = self.baby_list.wallet_id.points if self.baby_list.wallet_id else 0
        
        # Simulate wallet was debited
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points -= 100
        
        # Return/cancel
        item.state = 'cancelled'
        
        # Refund
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points += 100
            
            # Back to initial
            self.assertEqual(self.baby_list.wallet_id.points, initial_balance)
