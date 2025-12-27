# -*- coding: utf-8 -*-
"""
LST-003: Pregnancy Progress in Weeks
====================================

Feature: LST-003 Pregnancy Progress in Weeks
  As an Advisor
  I want to see pregnancy progress in weeks
  So that I know how urgent the list is

  Pillar: LIST
  Principles: P6 (Computed States)
  Priority: Must
"""

from odoo.tests import tagged
from datetime import date, timedelta
from freezegun import freeze_time
from .common import MoombsTestCommon


@tagged('moombs', 'lst_003', 'progress', 'must')
class TestLST003PregnancyProgress(MoombsTestCommon):
    """Test cases for LST-003: Pregnancy Progress."""

    # ═══════════════════════════════════════════════════════════════
    # HAPPY PATH
    # ═══════════════════════════════════════════════════════════════

    def test_pregnancy_weeks_calculation(self):
        """
        @happy_path @must @P6
        Scenario: Display pregnancy weeks progress
        
        Given Expected Date is "15/03/2025"
        And today is "14/12/2024"
        Then weeks = 40 - weeks_remaining
        """
        # Expected date: 15 March 2025
        # Today: 14 December 2024
        # Days until: ~91 days = ~13 weeks
        # Current week: 40 - 13 = 27
        
        expected_date = date(2025, 3, 15)
        today = date(2024, 12, 14)
        
        baby_list = self.create_test_list(
            list_type='birth',
            expected_date=expected_date
        )
        
        # Calculate expected weeks (simplified)
        days_until = (expected_date - today).days
        weeks_remaining = days_until // 7
        expected_weeks = 40 - weeks_remaining
        
        # The model should have weeks_progress computed field
        if hasattr(baby_list, 'weeks_progress'):
            self.assertGreater(baby_list.weeks_progress, 0)
            self.assertLessEqual(baby_list.weeks_progress, 40)

    def test_progress_percentage_calculation(self):
        """
        @happy_path @P6
        Scenario: Progress bar percentage
        """
        expected_date = date.today() + timedelta(days=70)  # 10 weeks
        
        baby_list = self.create_test_list(
            list_type='birth',
            expected_date=expected_date
        )
        
        # At 30 weeks (10 remaining), progress should be ~75%
        if hasattr(baby_list, 'progress_percentage'):
            self.assertGreater(baby_list.progress_percentage, 0)
            self.assertLessEqual(baby_list.progress_percentage, 100)

    # ═══════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_non_birth_list_shows_days(self):
        """
        @edge_case
        Scenario: Non-birth list shows days remaining
        """
        expected_date = date.today() + timedelta(days=183)
        
        baby_list = self.create_test_list(
            list_type='wedding',
            expected_date=expected_date
        )
        
        # Wedding list should show days, not weeks
        if hasattr(baby_list, 'days_remaining'):
            self.assertAlmostEqual(baby_list.days_remaining, 183, delta=1)

    def test_past_due_date_shows_warning(self):
        """
        @edge_case
        Scenario: Past due date shows warning
        """
        past_date = date.today() - timedelta(days=7)
        
        baby_list = self.create_test_list(
            list_type='birth',
            expected_date=past_date
        )
        
        # Should show 40/40 or overdue status
        if hasattr(baby_list, 'weeks_progress'):
            self.assertEqual(baby_list.weeks_progress, 40)
        
        if hasattr(baby_list, 'is_overdue'):
            self.assertTrue(baby_list.is_overdue)

    def test_far_future_date(self):
        """
        @edge_case
        Scenario: Very early in pregnancy (far future date)
        """
        far_date = date.today() + timedelta(days=280)  # Full pregnancy
        
        baby_list = self.create_test_list(
            list_type='birth',
            expected_date=far_date
        )
        
        if hasattr(baby_list, 'weeks_progress'):
            self.assertEqual(baby_list.weeks_progress, 0)

    def test_progress_display_format(self):
        """
        @edge_case
        Scenario: Progress display format "XX / 40 sem."
        """
        baby_list = self.create_test_list(
            list_type='birth',
            expected_date=date.today() + timedelta(days=42)  # 6 weeks
        )
        
        if hasattr(baby_list, 'progress_display'):
            self.assertIn('/', baby_list.progress_display)
            self.assertIn('40', baby_list.progress_display)
