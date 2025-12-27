# -*- coding: utf-8 -*-
"""
LST-008: Multiple Lists per Beneficiary
=======================================

Feature: LST-008 Multiple Lists per Beneficiary
  As a Beneficiary
  I want to have multiple lists
  So that I can manage different events (baby 1, baby 2, wedding)

  Pillar: LIST
  Principles: P2 (Sovereignty), P3 (Separation)
  Priority: Should
"""

from odoo.tests import tagged
from datetime import date, timedelta
from .common import MoombsTestCommon


@tagged('moombs', 'lst_008', 'multiple', 'should')
class TestLST008MultipleLists(MoombsTestCommon):
    """Test cases for LST-008: Multiple Lists."""

    # ═══════════════════════════════════════════════════════════════
    # HAPPY PATH
    # ═══════════════════════════════════════════════════════════════

    def test_create_second_list_same_beneficiary(self):
        """
        @happy_path @should @P3
        Scenario: Create second list for same beneficiary
        """
        list1 = self.create_test_list(
            partner=self.partner_ana,
            list_type='birth',
            expected_date=date.today() + timedelta(days=90)
        )
        
        list2 = self.create_test_list(
            partner=self.partner_ana,
            list_type='birth',
            expected_date=date.today() + timedelta(days=365)
        )
        
        # Both lists should exist
        self.assertTrue(list1.id)
        self.assertTrue(list2.id)
        self.assertNotEqual(list1.id, list2.id)
        
        # Both linked to same partner
        self.assertEqual(list1.partner_id, list2.partner_id)

    def test_multiple_lists_share_wallet(self):
        """
        @happy_path @should
        Scenario: Multiple lists share same wallet
        """
        list1 = self.create_test_list(partner=self.partner_ana)
        list2 = self.create_test_list(partner=self.partner_ana)
        
        # Both should reference the same wallet
        if list1.wallet_id and list2.wallet_id:
            self.assertEqual(
                list1.wallet_id, list2.wallet_id,
                "Both lists should share the same wallet"
            )

    def test_different_list_types_same_beneficiary(self):
        """
        @happy_path
        Scenario: Different list types for same beneficiary
        """
        birth_list = self.create_test_list(
            partner=self.partner_ana,
            list_type='birth'
        )
        
        wedding_list = self.create_test_list(
            partner=self.partner_ana,
            list_type='wedding'
        )
        
        self.assertEqual(birth_list.list_type, 'birth')
        self.assertEqual(wedding_list.list_type, 'wedding')

    # ═══════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_committed_wallet_includes_all_lists(self):
        """
        @edge_case
        Scenario: Committed wallet includes all active lists
        """
        list1 = self.create_test_list(partner=self.partner_ana)
        list2 = self.create_test_list(partner=self.partner_ana)

        # Both should share the same wallet
        self.assertEqual(list1.wallet_id, list2.wallet_id)

        # Add items to both lists
        item1 = self.create_test_item(list1, product=self.product_crib)
        item2 = self.create_test_item(list2, product=self.product_chair)

        # Simulate ordering (which commits 25%)
        item1.state = 'ordered'
        item2.state = 'ordered'

        # Total committed should include both lists
        # Crib: 450 * 0.25 = 112.50
        # Chair: 120 * 0.25 = 30.00
        # Total: 142.50
        expected = (450 * 0.25) + (120 * 0.25)

        # Both lists should see the same combined committed amount
        list1.invalidate_recordset(['wallet_committed'])
        list2.invalidate_recordset(['wallet_committed'])
        self.assertAlmostEqual(list1.wallet_committed, expected, places=2)
        self.assertAlmostEqual(list2.wallet_committed, expected, places=2)

    def test_available_balance_across_lists(self):
        """
        @edge_case
        Scenario: Available balance calculated across lists
        """
        list1 = self.create_test_list(partner=self.partner_ana)
        list2 = self.create_test_list(partner=self.partner_ana)

        # Topup wallet with €500
        self.assertTrue(list1.wallet_id, "Wallet should be created")
        list1.wallet_id.points = 500

        # Order item in list1 (commits €112.50)
        item1 = self.create_test_item(list1, product=self.product_crib)
        item1.state = 'ordered'

        # List2 should see reduced available balance
        # Available = 500 - 112.50 = 387.50
        list2.invalidate_recordset(['wallet_available'])
        self.assertAlmostEqual(list2.wallet_available, 387.50, places=2)

    def test_count_lists_per_partner(self):
        """
        @edge_case
        Scenario: Can count lists per partner
        """
        # Create 3 lists for Ana
        for _ in range(3):
            self.create_test_list(partner=self.partner_ana)
        
        # Count lists
        lists = self.env['baby.list'].search([
            ('partner_id', '=', self.partner_ana.id)
        ])
        
        self.assertEqual(len(lists), 3)

    def test_lists_are_independent(self):
        """
        @edge_case
        Scenario: Lists operate independently
        """
        list1 = self.create_test_list(partner=self.partner_ana)
        list2 = self.create_test_list(partner=self.partner_ana)
        
        # Complete one list
        list1.action_complete()
        
        # Other list should still be active
        self.assertEqual(list1.state, 'completed')
        self.assertEqual(list2.state, 'active')

    def test_deactivate_one_list_not_others(self):
        """
        @edge_case
        Scenario: Deactivating one list doesn't affect others
        """
        list1 = self.create_test_list(partner=self.partner_ana)
        list2 = self.create_test_list(partner=self.partner_ana)
        
        list1.action_deactivate()
        
        self.assertEqual(list1.state, 'inactive')
        self.assertEqual(list2.state, 'active')
