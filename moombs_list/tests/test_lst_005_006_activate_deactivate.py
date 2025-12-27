# -*- coding: utf-8 -*-
"""
LST-005: Deactivate List
LST-006: Reactivate List
========================

Feature: LST-005 Deactivate List
  As an Advisor
  I want to deactivate an active list
  So that I can temporarily pause list operations

Feature: LST-006 Reactivate List
  As an Advisor
  I want to reactivate a deactivated list
  So that I can resume list operations

  Pillar: LIST
  Principles: P2 (Sovereignty), P6 (Computed States)
  Priority: Must
"""

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from .common import MoombsTestCommon


@tagged('moombs', 'lst_005', 'lst_006', 'state', 'must')
class TestLST005006ActivateDeactivate(MoombsTestCommon):
    """Test cases for LST-005 and LST-006: Activate/Deactivate."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list(state='active')

    # ═══════════════════════════════════════════════════════════════
    # LST-005: DEACTIVATE - HAPPY PATH
    # ═══════════════════════════════════════════════════════════════

    def test_deactivate_active_list(self):
        """
        @happy_path @must @P6
        Scenario: Deactivate active list
        """
        self.assertEqual(self.baby_list.state, 'active')
        
        self.baby_list.action_deactivate()
        
        self.assertEqual(self.baby_list.state, 'inactive')

    def test_deactivate_logs_to_chatter(self):
        """
        @happy_path @P5
        Scenario: Deactivation logged to chatter
        """
        self.baby_list.action_deactivate()
        
        messages = self.baby_list.message_ids.filtered(
            lambda m: 'deactivat' in (m.body or '').lower()
        )
        self.assertTrue(messages, "Deactivation should be logged")

    # ═══════════════════════════════════════════════════════════════
    # LST-005: DEACTIVATE - SAD PATH
    # ═══════════════════════════════════════════════════════════════

    def test_cannot_deactivate_completed_list(self):
        """
        @sad_path
        Scenario: Cannot deactivate completed list
        """
        self.baby_list.state = 'completed'
        
        with self.assertRaises((UserError, ValidationError)):
            self.baby_list.action_deactivate()

    def test_cannot_deactivate_already_inactive(self):
        """
        @sad_path
        Scenario: Cannot deactivate already inactive list
        """
        self.baby_list.state = 'inactive'
        
        # Should either raise error or be idempotent
        self.baby_list.action_deactivate()
        self.assertEqual(self.baby_list.state, 'inactive')

    # ═══════════════════════════════════════════════════════════════
    # LST-005: DEACTIVATE - EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_deactivated_list_blocks_add_product(self):
        """
        @edge_case
        Scenario: Deactivated list blocks new operations
        """
        self.baby_list.action_deactivate()
        
        with self.assertRaises((UserError, ValidationError)):
            self.create_test_item(self.baby_list)

    # ═══════════════════════════════════════════════════════════════
    # LST-006: REACTIVATE - HAPPY PATH
    # ═══════════════════════════════════════════════════════════════

    def test_reactivate_inactive_list(self):
        """
        @happy_path @must @P6
        Scenario: Reactivate inactive list
        """
        self.baby_list.state = 'inactive'
        
        self.baby_list.action_activate()
        
        self.assertEqual(self.baby_list.state, 'active')

    def test_reactivate_logs_to_chatter(self):
        """
        @happy_path @P5
        Scenario: Reactivation logged to chatter
        """
        self.baby_list.state = 'inactive'
        self.baby_list.action_activate()
        
        messages = self.baby_list.message_ids.filtered(
            lambda m: 'reactivat' in (m.body or '').lower() or 
                      'activat' in (m.body or '').lower()
        )
        self.assertTrue(messages, "Reactivation should be logged")

    def test_reactivate_enables_operations(self):
        """
        @happy_path
        Scenario: Reactivated list allows operations again
        """
        self.baby_list.state = 'inactive'
        self.baby_list.action_activate()
        
        # Should be able to add products now
        item = self.create_test_item(self.baby_list)
        self.assertTrue(item.id)

    # ═══════════════════════════════════════════════════════════════
    # LST-006: REACTIVATE - SAD PATH
    # ═══════════════════════════════════════════════════════════════

    def test_cannot_reactivate_completed_list(self):
        """
        @sad_path
        Scenario: Cannot reactivate completed list
        """
        self.baby_list.state = 'completed'
        
        with self.assertRaises((UserError, ValidationError)):
            self.baby_list.action_activate()

    # ═══════════════════════════════════════════════════════════════
    # STATE TRANSITIONS
    # ═══════════════════════════════════════════════════════════════

    def test_state_transition_active_inactive_active(self):
        """
        @edge_case
        Scenario: Full cycle active -> inactive -> active
        """
        self.assertEqual(self.baby_list.state, 'active')
        
        self.baby_list.action_deactivate()
        self.assertEqual(self.baby_list.state, 'inactive')
        
        self.baby_list.action_activate()
        self.assertEqual(self.baby_list.state, 'active')
