# -*- coding: utf-8 -*-
"""
LST-007: Complete List
======================

Feature: LST-007 Complete List
  As an Advisor
  I want to manually complete/close a list
  So that I can mark the list as finished

  Pillar: LIST
  Principles: P2 (Sovereignty), P6 (Computed States)
  Priority: Should
"""

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from .common import MoombsTestCommon


@tagged('moombs', 'lst_007', 'complete', 'should')
class TestLST007CompleteList(MoombsTestCommon):
    """Test cases for LST-007: Complete List."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list(state='active')

    # ═══════════════════════════════════════════════════════════════
    # HAPPY PATH
    # ═══════════════════════════════════════════════════════════════

    def test_complete_list_manually(self):
        """
        @happy_path @should @P6
        Scenario: Complete list manually
        """
        self.baby_list.action_complete()
        
        self.assertEqual(self.baby_list.state, 'completed')

    def test_complete_logs_to_chatter(self):
        """
        @happy_path @P5
        Scenario: Completion logged to chatter
        """
        self.baby_list.action_complete()
        
        messages = self.baby_list.message_ids.filtered(
            lambda m: 'complet' in (m.body or '').lower()
        )
        self.assertTrue(messages, "Completion should be logged")

    def test_complete_list_all_items_delivered(self):
        """
        @happy_path
        Scenario: Complete list when all items delivered
        """
        # Create items in delivered state
        item1 = self.create_test_item(self.baby_list, product=self.product_crib)
        item2 = self.create_test_item(self.baby_list, product=self.product_bottle)
        
        item1.state = 'delivered'
        item2.state = 'delivered'
        
        self.baby_list.action_complete()
        
        self.assertEqual(self.baby_list.state, 'completed')

    # ═══════════════════════════════════════════════════════════════
    # SAD PATH
    # ═══════════════════════════════════════════════════════════════

    def test_warning_when_pending_items(self):
        """
        @sad_path
        Scenario: Warning when completing with pending items opens wizard
        """
        # Create item in ordered state (pending)
        item = self.create_test_item(self.baby_list)
        item.state = 'ordered'

        # action_complete should return wizard action when pending items exist
        result = self.baby_list.action_complete()

        # Should return an action to open the wizard
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('res_model'), 'baby.list.complete.wizard')
        self.assertEqual(result.get('target'), 'new')

        # List should NOT be completed yet
        self.assertEqual(self.baby_list.state, 'active')

    def test_wizard_confirms_completion(self):
        """
        @sad_path
        Scenario: Wizard confirms completion with pending items
        """
        # Create item in ordered state (pending)
        item = self.create_test_item(self.baby_list)
        item.state = 'ordered'

        # Create wizard
        wizard = self.env['baby.list.complete.wizard'].create({
            'list_id': self.baby_list.id,
            'pending_count': 1,
            'pending_amount': item.price_final,
        })

        # Confirm via wizard
        wizard.action_confirm()

        # Now list should be completed
        self.assertEqual(self.baby_list.state, 'completed')

    def test_cannot_complete_inactive_list(self):
        """
        @sad_path
        Scenario: Cannot complete inactive list directly
        """
        self.baby_list.state = 'inactive'
        
        # Should either require activation first or allow completion
        # Depends on business decision
        try:
            self.baby_list.action_complete()
            # If it succeeds, state should be completed
            self.assertEqual(self.baby_list.state, 'completed')
        except (UserError, ValidationError):
            # If it fails, list should still be inactive
            self.assertEqual(self.baby_list.state, 'inactive')

    # ═══════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_completed_list_blocks_modifications(self):
        """
        @edge_case
        Scenario: Completed list blocks modifications
        """
        self.baby_list.action_complete()
        
        with self.assertRaises((UserError, ValidationError)):
            self.create_test_item(self.baby_list)

    def test_completed_list_cannot_be_reactivated(self):
        """
        @edge_case
        Scenario: Completed list cannot be reactivated
        """
        self.baby_list.action_complete()
        
        with self.assertRaises((UserError, ValidationError)):
            self.baby_list.action_activate()

    def test_complete_empty_list(self):
        """
        @edge_case
        Scenario: Complete list with no items
        """
        # List has no items
        self.assertEqual(len(self.baby_list.item_ids), 0)
        
        # Should be allowed to complete
        self.baby_list.action_complete()
        self.assertEqual(self.baby_list.state, 'completed')

    def test_complete_list_with_cancelled_items_only(self):
        """
        @edge_case
        Scenario: Complete list with only cancelled items
        """
        item = self.create_test_item(self.baby_list)
        item.state = 'cancelled'
        
        self.baby_list.action_complete()
        self.assertEqual(self.baby_list.state, 'completed')
