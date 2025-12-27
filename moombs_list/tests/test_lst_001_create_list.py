# -*- coding: utf-8 -*-
"""
LST-001: Create Gift List
=========================

Feature: LST-001 Create Gift List
  As an Advisor
  I want to create a new gift list with beneficiary info
  So that I can start registering desired products

  Pillar: LIST
  Principles: P1 (Graceful Uninstall), P2 (Sovereignty), P7 (Referential Integrity)
  Business Rule: BR-003 (Everything Through Wallet)
  Priority: Must
"""

from odoo.tests import tagged
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from .common import MoombsTestCommon


@tagged('moombs', 'lst_001', 'create', 'must')
class TestLST001CreateList(MoombsTestCommon):
    """Test cases for LST-001: Create Gift List."""

    # ═══════════════════════════════════════════════════════════════
    # HAPPY PATH
    # ═══════════════════════════════════════════════════════════════

    def test_happy_create_list_with_required_fields(self):
        """
        @happy_path @must @P2 @BR-003
        Scenario: Create list with all required fields

        Given I am authenticated as "Advisor"
        And contact "Ana García" exists
        When I create a list with valid data
        Then the list is created with state = active
        And a wallet is created for Ana García
        """
        # Given
        expected_date = date.today() + timedelta(days=90)

        # When
        baby_list = self.env['baby.list'].create({
            'partner_id': self.partner_ana.id,
            'partner2_id': self.partner_pedro.id,
            'list_type': 'birth',
            'expected_date': expected_date,
        })

        # Then
        self.assertTrue(baby_list.id, "List should be created")
        self.assertTrue(baby_list.name.startswith('BBP-'),
                       f"Reference should start with BBP-, got {baby_list.name}")
        self.assertEqual(baby_list.state, 'active',
                        "New list should be active by default")
        self.assertEqual(baby_list.partner_id, self.partner_ana)
        self.assertEqual(baby_list.partner2_id, self.partner_pedro)

        # And a wallet is created for Beneficiary 1
        self.assertTrue(baby_list.wallet_id,
                       "Wallet should be created for beneficiary")

    def test_happy_sequence_format_BBP_YYMM_XXXX(self):
        """
        @happy_path
        Scenario: Reference follows format BBP-YYMM-XXXX

        When I create a list in current month
        Then the reference starts with "BBP-YYMM-"
        And the sequence is auto-incremented (0001, 0002, ...)
        """
        # When
        baby_list = self.create_test_list()

        # Then
        # Reference format: BBP-YYMM-XXXX
        self.assertRegex(
            baby_list.name,
            r'^BBP-\d{4}-\d{4}$',
            f"Reference should match BBP-YYMM-XXXX format, got {baby_list.name}"
        )

    def test_happy_state_defaults_to_active(self):
        """
        @happy_path
        Scenario: New list defaults to active state

        When I create a new list
        Then the state is "active"
        """
        # When
        baby_list = self.create_test_list()

        # Then
        self.assertEqual(baby_list.state, 'active',
                        "New list should default to active state")

    def test_happy_wallet_auto_created(self):
        """
        @happy_path @BR-003
        Scenario: Wallet is automatically created

        When I create a list
        Then a wallet (loyalty.card) is created for Beneficiary 1
        And the wallet is linked to the list
        """
        # When
        baby_list = self.create_test_list()

        # Then
        self.assertTrue(baby_list.wallet_id,
                       "Wallet should be auto-created")
        self.assertEqual(baby_list.wallet_id.partner_id,
                        baby_list.partner_id,
                        "Wallet should belong to Beneficiary 1")

    def test_happy_sequence_auto_increments(self):
        """
        @happy_path
        Scenario: Sequence auto-increments

        When I create multiple lists
        Then each list gets next sequence number
        """
        # When
        list1 = self.create_test_list()
        list2 = self.create_test_list()

        # Then
        # Extract sequence numbers (last 4 digits)
        seq1 = int(list1.name.split('-')[-1])
        seq2 = int(list2.name.split('-')[-1])

        self.assertEqual(seq2, seq1 + 1,
                        "Sequence should auto-increment")

    def test_happy_advisor_set_to_current_user(self):
        """
        @happy_path
        Scenario: Current user is set as advisor

        When I create a list
        Then the advisor field is set to current user
        """
        # When
        baby_list = self.env['baby.list'].with_user(self.user_advisor).create({
            'partner_id': self.partner_ana.id,
            'list_type': 'birth',
            'expected_date': date.today() + timedelta(days=90),
        })

        # Then
        self.assertEqual(baby_list.advisor_id, self.user_advisor,
                        "Current user should be set as advisor")

    # ═══════════════════════════════════════════════════════════════
    # SAD PATH
    # ═══════════════════════════════════════════════════════════════

    def test_sad_missing_partner_raises_error(self):
        """
        @sad_path @P10
        Scenario: Beneficiary 1 is required

        When I try to create a list without selecting Beneficiary 1
        Then I see validation error "Beneficiary 1 is required"
        And the list is NOT created
        """
        # When/Then
        with self.assertRaises(ValidationError):
            self.env['baby.list'].create({
                'list_type': 'birth',
                'expected_date': date.today() + timedelta(days=90),
                # partner_id missing
            })

    def test_sad_missing_expected_date_raises_error(self):
        """
        @sad_path @P10
        Scenario: Expected Date is required

        When I try to create a list without Expected Date
        Then I see validation error "Expected Date is required"
        """
        # When/Then
        with self.assertRaises(ValidationError):
            self.env['baby.list'].create({
                'partner_id': self.partner_ana.id,
                'list_type': 'birth',
                # expected_date missing
            })

    # ═══════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_edge_wallet_linked_to_beneficiary1(self):
        """
        @edge_case
        Scenario: Wallet always linked to Beneficiary 1

        When I create list with Beneficiary 1 "Ana" and Beneficiary 2 "Pedro"
        Then the wallet is created/associated to "Ana" (Beneficiary 1)
        And "Pedro" does NOT have their own wallet for this list
        """
        # When
        baby_list = self.create_test_list(
            partner=self.partner_ana,
            partner2=self.partner_pedro
        )

        # Then
        # Wallet should be for Ana (Beneficiary 1), not Pedro
        if baby_list.wallet_id:
            self.assertEqual(
                baby_list.wallet_id.partner_id,
                self.partner_ana,
                "Wallet should be linked to Beneficiary 1"
            )

    def test_edge_chatter_logs_creation(self):
        """
        @edge_case @P5
        Scenario: Chatter logs complete creation

        When I create a list
        Then the chatter logs:
          | field   | value                         |
          | author  | current user                  |
          | content | List created. Wallet created. |
        """
        # When
        baby_list = self.create_test_list()

        # Then
        # Check chatter message exists
        messages = baby_list.message_ids.filtered(
            lambda m: 'created' in (m.body or '').lower()
        )
        self.assertTrue(messages, "Creation should be logged to chatter")

    def test_edge_create_with_only_beneficiary1(self):
        """
        @edge_case
        Scenario: List can be created with only Beneficiary 1

        When I create a list without Beneficiary 2
        Then the list is created successfully
        And partner2_id is empty
        """
        # When
        baby_list = self.env['baby.list'].create({
            'partner_id': self.partner_ana.id,
            'list_type': 'birth',
            'expected_date': date.today() + timedelta(days=90),
            # partner2_id not provided
        })

        # Then
        self.assertTrue(baby_list.id)
        self.assertFalse(baby_list.partner2_id)

    def test_edge_different_list_types(self):
        """
        @edge_case
        Scenario: Lists can be created with different types

        When I create lists of type birth, wedding, other
        Then each list is created with correct type
        """
        # When/Then
        for list_type in ['birth', 'wedding', 'other']:
            baby_list = self.env['baby.list'].create({
                'partner_id': self.partner_ana.id,
                'list_type': list_type,
                'expected_date': date.today() + timedelta(days=90),
            })
            self.assertEqual(baby_list.list_type, list_type)
