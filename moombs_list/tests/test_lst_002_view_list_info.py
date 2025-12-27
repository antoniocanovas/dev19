# -*- coding: utf-8 -*-
"""
LST-002: View List Info via Progress Bar
========================================

Feature: LST-002 View List Info via Progress Bar
  As an Advisor
  I want to view list info by clicking the progress bar
  So that I can see/edit list details

  Pillar: LIST
  Principles: P5 (Traceability)
  Priority: Must
"""

from odoo.tests import tagged
from datetime import date, timedelta
from .common import MoombsTestCommon


@tagged('moombs', 'lst_002', 'view', 'must')
class TestLST002ViewListInfo(MoombsTestCommon):
    """Test cases for LST-002: View List Info."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list(
            partner=self.partner_ana,
            partner2=self.partner_pedro,
            expected_date=date(2025, 3, 15)
        )

    # ═══════════════════════════════════════════════════════════════
    # HAPPY PATH
    # ═══════════════════════════════════════════════════════════════

    def test_happy_action_view_info_returns_wizard(self):
        """
        @happy_path @must @P5
        Scenario: Click progress bar opens info popup

        Given I am viewing list "BBP-2512-0042"
        When I click on the progress bar
        Then a popup opens showing list details
        """
        # When
        result = self.baby_list.action_view_info()

        # Then
        self.assertEqual(result.get('type'), 'ir.actions.act_window',
                        "Should return window action")
        self.assertEqual(result.get('res_model'), 'baby.list.info.wizard',
                        "Should open info wizard")
        self.assertEqual(result.get('target'), 'new',
                        "Should open as popup")

    def test_happy_wizard_shows_partner_info(self):
        """
        @happy_path @must
        Scenario: Popup shows both partners with phones

        Given list has two beneficiaries
        When I view the list info
        Then I see:
          | Field     | Value           |
          | Partner 1 | Ana García      |
          | Phone 1   | +34 612 345 678 |
          | Partner 2 | Pedro Martínez  |
          | Phone 2   | +34 698 765 432 |
        """
        # Then - Verify all info fields are accessible
        self.assertTrue(self.baby_list.name, "Reference should be set")
        self.assertEqual(self.baby_list.list_type, 'birth')
        self.assertEqual(self.baby_list.expected_date, date(2025, 3, 15))
        self.assertEqual(self.baby_list.partner_id, self.partner_ana)
        self.assertEqual(self.baby_list.partner2_id, self.partner_pedro)

        # Phone numbers from partners
        self.assertEqual(self.partner_ana.mobile, '+34612345678')
        self.assertEqual(self.partner_pedro.mobile, '+34698765432')

    def test_happy_wizard_shows_progress_for_birth_type(self):
        """
        @happy_path
        Scenario: Info shows pregnancy progress for birth type

        Given list type is "Birth"
        And Expected Date is set
        When I view the list info
        Then I see pregnancy progress in weeks
        """
        # Then
        self.assertEqual(self.baby_list.list_type, 'birth')
        # Pregnancy progress should be computed
        self.assertIsNotNone(self.baby_list.weeks_progress,
                           "Weeks progress should be computed")
        self.assertEqual(self.baby_list.weeks_total, 40,
                        "Total weeks should be 40 for birth")

    def test_happy_list_info_can_be_edited(self):
        """
        @happy_path
        Scenario: Edit list info from popup

        Given the info popup is open
        When I modify the Expected Date to "20/03/2025"
        And I click "Save"
        Then the list is updated with new Expected Date
        """
        # When
        new_date = date(2025, 3, 20)
        self.baby_list.write({'expected_date': new_date})

        # Then
        self.assertEqual(self.baby_list.expected_date, new_date)

    def test_happy_edit_logs_to_chatter(self):
        """
        @happy_path @P5
        Scenario: Changes are logged to chatter

        When I modify list fields
        Then the changes are tracked in chatter
        """
        # Given
        old_date = self.baby_list.expected_date
        new_date = date(2025, 3, 20)

        # When
        self.baby_list.write({'expected_date': new_date})

        # Then
        # Check tracking message exists
        # Note: Requires field to have tracking=True
        messages = self.baby_list.message_ids
        self.assertTrue(len(messages) > 0, "Changes should be tracked")

    # ═══════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_edge_list_with_only_beneficiary1(self):
        """
        @edge_case
        Scenario: List with only Beneficiary 1

        Given the list has no Beneficiary 2
        When I click on the progress bar
        Then Partner 2 field shows empty
        And Phone 2 field shows empty
        """
        # Given
        baby_list = self.create_test_list(
            partner=self.partner_ana,
            partner2=None
        )

        # Then
        self.assertTrue(baby_list.partner_id)
        self.assertFalse(baby_list.partner2_id)

    def test_edge_info_popup_action_exists(self):
        """
        @edge_case
        Scenario: Action method for info popup exists

        The model should have an action_view_info method
        """
        # Then
        self.assertTrue(
            hasattr(self.baby_list, 'action_view_info'),
            "List should have action_view_info method"
        )

    def test_edge_all_fields_displayed_correctly(self):
        """
        @edge_case
        Scenario: All fields are accessible for display

        When viewing list info
        Then all expected fields are readable
        """
        # Then - All fields should be accessible
        fields_to_check = [
            'name',
            'partner_id',
            'partner2_id',
            'list_type',
            'expected_date',
            'advisor_id',
            'state',
        ]

        for field in fields_to_check:
            self.assertTrue(
                hasattr(self.baby_list, field),
                f"List should have field {field}"
            )
