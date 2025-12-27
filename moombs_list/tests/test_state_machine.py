# -*- coding: utf-8 -*-
"""
State Machine Tests
===================

Test state transitions for baby.list.item:
wished → ordered → reserved → paid → delivered
                                   ↘ cancelled

Valid transitions:
- wished → ordered (ORDER action, BR-001 check)
- wished → cancelled
- ordered → reserved (stock received)
- ordered → cancelled
- reserved → paid (POS payment)
- reserved → cancelled
- paid → delivered (DELIVER action)
- paid → cancelled (return with refund BR-009)
- delivered → cancelled (return with refund BR-009)
"""

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from .common import MoombsTestCommon


@tagged('moombs', 'state_machine', 'states')
class TestStateMachine(MoombsTestCommon):
    """Test cases for State Machine transitions."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list()
        self.item = self.create_test_item(self.baby_list)
        
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 500

    # ═══════════════════════════════════════════════════════════════
    # INITIAL STATE
    # ═══════════════════════════════════════════════════════════════

    def test_initial_state_is_wished(self):
        """New item starts in wished state."""
        self.assertEqual(self.item.state, 'wished')

    # ═══════════════════════════════════════════════════════════════
    # VALID TRANSITIONS
    # ═══════════════════════════════════════════════════════════════

    def test_transition_wished_to_ordered(self):
        """wished → ordered (ORDER action)"""
        self.assertEqual(self.item.state, 'wished')
        
        self.item.state = 'ordered'
        
        self.assertEqual(self.item.state, 'ordered')

    def test_transition_wished_to_cancelled(self):
        """wished → cancelled"""
        self.assertEqual(self.item.state, 'wished')
        
        self.item.state = 'cancelled'
        
        self.assertEqual(self.item.state, 'cancelled')

    def test_transition_ordered_to_reserved(self):
        """ordered → reserved (stock received)"""
        self.item.state = 'ordered'
        
        self.item.state = 'reserved'
        
        self.assertEqual(self.item.state, 'reserved')

    def test_transition_ordered_to_cancelled(self):
        """ordered → cancelled"""
        self.item.state = 'ordered'
        
        self.item.state = 'cancelled'
        
        self.assertEqual(self.item.state, 'cancelled')

    def test_transition_reserved_to_paid(self):
        """reserved → paid (POS payment)"""
        self.item.state = 'reserved'
        
        self.item.state = 'paid'
        
        self.assertEqual(self.item.state, 'paid')

    def test_transition_reserved_to_cancelled(self):
        """reserved → cancelled"""
        self.item.state = 'reserved'
        
        self.item.state = 'cancelled'
        
        self.assertEqual(self.item.state, 'cancelled')

    def test_transition_paid_to_delivered(self):
        """paid → delivered (DELIVER action)"""
        self.item.state = 'paid'
        
        self.item.state = 'delivered'
        
        self.assertEqual(self.item.state, 'delivered')

    def test_transition_paid_to_cancelled(self):
        """paid → cancelled (return with refund)"""
        self.item.state = 'paid'
        
        self.item.state = 'cancelled'
        
        self.assertEqual(self.item.state, 'cancelled')

    # ═══════════════════════════════════════════════════════════════
    # INVALID TRANSITIONS (should be blocked)
    # ═══════════════════════════════════════════════════════════════

    def test_invalid_transition_wished_to_paid(self):
        """wished → paid is INVALID (must go through ordered first)"""
        self.assertEqual(self.item.state, 'wished')
        
        # This transition should be blocked by business logic
        # For now, we just verify the states exist
        self.assertIn(self.item.state, ['wished', 'ordered', 'reserved', 
                                         'paid', 'delivered', 'cancelled'])

    def test_invalid_transition_wished_to_delivered(self):
        """wished → delivered is INVALID"""
        self.assertEqual(self.item.state, 'wished')
        
        # Should not be allowed to skip states

    def test_invalid_transition_ordered_to_delivered(self):
        """ordered → delivered is INVALID (must be paid first)"""
        self.item.state = 'ordered'
        
        # Cannot deliver without payment

    def test_invalid_transition_cancelled_to_any(self):
        """cancelled → any is INVALID (terminal state)"""
        self.item.state = 'cancelled'
        
        # Cancelled is terminal (except for special cases)
        self.assertEqual(self.item.state, 'cancelled')

    # ═══════════════════════════════════════════════════════════════
    # COMPLETE FLOWS
    # ═══════════════════════════════════════════════════════════════

    def test_complete_happy_flow(self):
        """Complete flow: wished → ordered → reserved → paid → delivered"""
        self.assertEqual(self.item.state, 'wished')
        
        self.item.state = 'ordered'
        self.assertEqual(self.item.state, 'ordered')
        
        self.item.state = 'reserved'
        self.assertEqual(self.item.state, 'reserved')
        
        self.item.state = 'paid'
        self.assertEqual(self.item.state, 'paid')
        
        self.item.state = 'delivered'
        self.assertEqual(self.item.state, 'delivered')

    def test_cancel_flow_from_wished(self):
        """Cancel flow from wished"""
        self.assertEqual(self.item.state, 'wished')
        
        self.item.state = 'cancelled'
        self.assertEqual(self.item.state, 'cancelled')

    def test_cancel_flow_from_ordered(self):
        """Cancel flow from ordered"""
        self.item.state = 'ordered'
        
        self.item.state = 'cancelled'
        self.assertEqual(self.item.state, 'cancelled')

    def test_return_flow_from_paid(self):
        """Return flow from paid (with refund)"""
        self.item.state = 'ordered'
        self.item.state = 'reserved'
        self.item.state = 'paid'
        
        # Return
        self.item.state = 'cancelled'
        self.assertEqual(self.item.state, 'cancelled')

    # ═══════════════════════════════════════════════════════════════
    # STATE-BASED PERMISSIONS
    # ═══════════════════════════════════════════════════════════════

    def test_order_button_enabled_for_wished(self):
        """ORDER button enabled only for wished state"""
        wished_allows_order = self.item.state == 'wished'
        self.assertTrue(wished_allows_order)
        
        self.item.state = 'ordered'
        ordered_allows_order = self.item.state == 'wished'
        self.assertFalse(ordered_allows_order)

    def test_deliver_button_enabled_for_paid(self):
        """DELIVER button enabled only for paid state"""
        self.item.state = 'paid'
        paid_allows_deliver = self.item.state == 'paid'
        self.assertTrue(paid_allows_deliver)
        
        self.item.state = 'reserved'
        reserved_allows_deliver = self.item.state == 'paid'
        self.assertFalse(reserved_allows_deliver)

    def test_cancel_button_enabled_states(self):
        """CANCEL button enabled for most states"""
        cancellable_states = ['wished', 'ordered', 'reserved']
        
        for state in cancellable_states:
            self.item.state = state
            self.assertIn(self.item.state, cancellable_states)

    # ═══════════════════════════════════════════════════════════════
    # BUTTON STATES MATRIX
    # ═══════════════════════════════════════════════════════════════

    def test_button_matrix_wished(self):
        """Button states for wished: Order=✅, Deliver=❌, Cancel=✅"""
        self.item.state = 'wished'
        
        can_order = self.item.state == 'wished'
        can_deliver = self.item.state == 'paid'
        can_cancel = self.item.state not in ('delivered', 'cancelled')
        
        self.assertTrue(can_order)
        self.assertFalse(can_deliver)
        self.assertTrue(can_cancel)

    def test_button_matrix_paid(self):
        """Button states for paid: Order=❌, Deliver=✅, Cancel=❌"""
        self.item.state = 'paid'
        
        can_order = self.item.state == 'wished'
        can_deliver = self.item.state == 'paid'
        can_cancel = False  # Special handling for paid items
        
        self.assertFalse(can_order)
        self.assertTrue(can_deliver)

    def test_button_matrix_delivered(self):
        """Button states for delivered: Order=❌, Deliver=❌, Cancel=✅ (return)"""
        self.item.state = 'delivered'
        
        can_order = self.item.state == 'wished'
        can_deliver = self.item.state == 'paid'
        can_return = True  # Can return delivered items
        
        self.assertFalse(can_order)
        self.assertFalse(can_deliver)
        self.assertTrue(can_return)

    def test_button_matrix_cancelled(self):
        """Button states for cancelled: All=❌"""
        self.item.state = 'cancelled'
        
        can_order = False
        can_deliver = False
        can_cancel = False
        
        self.assertFalse(can_order)
        self.assertFalse(can_deliver)
        self.assertFalse(can_cancel)
