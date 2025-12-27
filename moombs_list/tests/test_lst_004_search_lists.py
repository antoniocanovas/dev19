# -*- coding: utf-8 -*-
"""
LST-004: Search Lists
=====================

Feature: LST-004 Search Lists
  As an Advisor
  I want to search lists by name/phone/reference
  So that I can quickly find a customer's list

  Pillar: LIST
  Principles: P2 (Sovereignty)
  Priority: Must
"""

from odoo.tests import tagged
from .common import MoombsTestCommon


@tagged('moombs', 'lst_004', 'search', 'must')
class TestLST004SearchLists(MoombsTestCommon):
    """Test cases for LST-004: Search Lists."""

    def setUp(self):
        super().setUp()
        # Create multiple lists for search testing
        self.list_ana = self.create_test_list(partner=self.partner_ana)
        self.list_maria = self.create_test_list(partner=self.partner_maria)

    # ═══════════════════════════════════════════════════════════════
    # HAPPY PATH
    # ═══════════════════════════════════════════════════════════════

    def test_search_by_phone_number(self):
        """
        @happy_path @must
        Scenario: Search by phone number
        """
        # Search by Ana's phone
        results = self.env['baby.list'].search([
            ('partner_id.mobile', 'ilike', '612345678')
        ])
        
        self.assertIn(self.list_ana, results)
        self.assertNotIn(self.list_maria, results)

    def test_search_by_beneficiary_name(self):
        """
        @happy_path
        Scenario: Search by beneficiary name
        """
        results = self.env['baby.list'].search([
            ('partner_id.name', 'ilike', 'Ana García')
        ])
        
        self.assertIn(self.list_ana, results)

    def test_search_by_reference(self):
        """
        @happy_path
        Scenario: Search by reference
        """
        results = self.env['baby.list'].search([
            ('name', '=', self.list_ana.name)
        ])
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results, self.list_ana)

    def test_search_by_partial_phone(self):
        """
        @happy_path
        Scenario: Search by partial phone
        """
        # Search with partial phone number
        results = self.env['baby.list'].search([
            ('partner_id.mobile', 'ilike', '6123')
        ])
        
        self.assertIn(self.list_ana, results)

    def test_search_by_partial_name(self):
        """
        @happy_path
        Scenario: Search by partial name
        """
        results = self.env['baby.list'].search([
            ('partner_id.name', 'ilike', 'Ana')
        ])
        
        self.assertIn(self.list_ana, results)

    # ═══════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════

    def test_search_no_results(self):
        """
        @edge_case
        Scenario: Search with no results
        """
        results = self.env['baby.list'].search([
            ('partner_id.mobile', 'ilike', '999888777')
        ])
        
        self.assertEqual(len(results), 0)

    def test_search_multiple_results(self):
        """
        @edge_case
        Scenario: Search returns multiple results
        """
        # Create another list for Ana
        list_ana_2 = self.create_test_list(partner=self.partner_ana)
        
        results = self.env['baby.list'].search([
            ('partner_id', '=', self.partner_ana.id)
        ])
        
        self.assertEqual(len(results), 2)
        self.assertIn(self.list_ana, results)
        self.assertIn(list_ana_2, results)

    def test_search_case_insensitive(self):
        """
        @edge_case
        Scenario: Search is case insensitive
        """
        results = self.env['baby.list'].search([
            ('partner_id.name', 'ilike', 'ANA GARCÍA')
        ])
        
        self.assertIn(self.list_ana, results)

    def test_name_search_method(self):
        """
        @edge_case
        Scenario: name_search works for autocomplete
        """
        # Test the name_search method used in Many2one fields
        results = self.env['baby.list'].name_search('Ana')
        
        # Should return tuples of (id, name)
        result_ids = [r[0] for r in results]
        self.assertIn(self.list_ana.id, result_ids)
