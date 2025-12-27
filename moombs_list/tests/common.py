# -*- coding: utf-8 -*-
"""
MOOMBS Lists - Common Test Utilities
====================================

Base class and helpers for all MOOMBS tests.
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, timedelta


class MoombsTestCommon(TransactionCase):
    """Base class for MOOMBS List tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test company
        cls.company = cls.env.company

        # Create test users with security groups
        cls.user_advisor = cls.env['res.users'].create({
            'name': 'Test Advisor',
            'login': 'test_advisor',
            'email': 'advisor@test.com',
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
            ])],
        })

        cls.user_manager = cls.env['res.users'].create({
            'name': 'Test Manager',
            'login': 'test_manager',
            'email': 'manager@test.com',
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
            ])],
        })

        # Create test partners (beneficiaries)
        cls.partner_ana = cls.env['res.partner'].create({
            'name': 'Ana García',
            'mobile': '+34612345678',
            'email': 'ana@test.com',
        })

        cls.partner_pedro = cls.env['res.partner'].create({
            'name': 'Pedro Martínez',
            'mobile': '+34698765432',
            'email': 'pedro@test.com',
        })

        cls.partner_maria = cls.env['res.partner'].create({
            'name': 'María García López',
            'mobile': '+34611111111',
            'email': 'maria@test.com',
            'vat': '12345678A',
        })

        # Create test products
        cls.product_crib = cls.env['product.product'].create({
            'name': 'Premium Crib',
            'list_price': 450.00,
            'type': 'product',
            'default_code': 'CRIB001',
        })

        cls.product_bottle = cls.env['product.product'].create({
            'name': 'Bottle 250ml',
            'list_price': 15.00,
            'type': 'product',
            'default_code': 'BTL001',
        })

        cls.product_chair = cls.env['product.product'].create({
            'name': 'Baby Chair',
            'list_price': 120.00,
            'type': 'product',
            'default_code': 'CHR001',
        })

        # Create eWallet loyalty program
        cls.wallet_program = cls._create_wallet_program()

    @classmethod
    def _create_wallet_program(cls):
        """Create eWallet loyalty program for testing."""
        LoyaltyProgram = cls.env['loyalty.program']
        existing = LoyaltyProgram.search([('name', '=', 'eWallet MOOMBS')], limit=1)

        if existing:
            return existing

        return LoyaltyProgram.create({
            'name': 'eWallet MOOMBS',
            'program_type': 'ewallet',
            'trigger': 'auto',
            'applies_on': 'both',
        })

    def create_test_list(self, partner=None, partner2=None, list_type='birth',
                         expected_date=None, state='active'):
        """Helper to create a test list with new naming convention."""
        if partner is None:
            partner = self.partner_ana
        if expected_date is None:
            expected_date = date.today() + timedelta(days=90)

        return self.env['baby.list'].create({
            'partner_id': partner.id,
            'partner2_id': partner2.id if partner2 else False,
            'list_type': list_type,
            'expected_date': expected_date,
            'state': state,
        })

    def create_test_item(self, baby_list, product=None, price_unit=None,
                         discount=0, state='wished'):
        """Helper to create a test list item with new naming convention."""
        if product is None:
            product = self.product_crib
        if price_unit is None:
            price_unit = product.list_price

        return self.env['baby.list.item'].create({
            'list_id': baby_list.id,
            'product_id': product.id,
            'price_unit': price_unit,
            'discount': discount,
            'state': state,
        })

    def topup_wallet(self, baby_list, amount, payer=None):
        """Helper to add money to wallet."""
        if payer is None:
            payer = self.partner_maria
        # Add points to loyalty card
        if baby_list.wallet_id:
            baby_list.wallet_id.points += amount
        return amount

    def assertListState(self, baby_list, expected_state):
        """Assert list is in expected state."""
        self.assertEqual(
            baby_list.state, expected_state,
            f"Expected list state '{expected_state}', got '{baby_list.state}'"
        )

    def assertItemState(self, item, expected_state):
        """Assert item is in expected state."""
        self.assertEqual(
            item.state, expected_state,
            f"Expected item state '{expected_state}', got '{item.state}'"
        )

    def assertWalletBalance(self, baby_list, expected_balance):
        """Assert wallet has expected balance."""
        self.assertAlmostEqual(
            baby_list.wallet_balance, expected_balance, places=2,
            msg=f"Expected wallet balance {expected_balance}, got {baby_list.wallet_balance}"
        )
