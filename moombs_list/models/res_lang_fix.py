# -*- coding: utf-8 -*-
"""
Odoo 19EE Language Import Fix
==============================

Fixes the ValueError when importing languages where grouping field
receives a list instead of a string.

Issue: ValueError: Wrong value for res.lang.grouping: '[3, 3, 0]'
Fix: Convert list to string format before creating language record.
"""

from odoo import models, api


class ResLang(models.Model):
    _inherit = 'res.lang'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to fix grouping field format.
        
        Fixes Odoo 19EE bug where grouping field receives '[3, 3, 0]' (with spaces)
        or list [3, 3, 0] which causes ValueError.
        
        The grouping field is a Selection field. If the value is not valid,
        we remove it to let Odoo use the default value.
        """
        # Get valid selection values for grouping field
        grouping_field = self._fields.get('grouping')
        valid_selections = []
        if grouping_field and hasattr(grouping_field, 'selection'):
            selection = grouping_field.selection
            if callable(selection):
                # If it's a callable, we can't evaluate it here, so we'll handle differently
                valid_selections = None
            else:
                valid_selections = [val[0] for val in selection] if selection else []
        
        # Fix grouping field format
        for vals in vals_list:
            if 'grouping' in vals:
                grouping = vals['grouping']
                normalized_value = None
                
                if isinstance(grouping, list):
                    # Convert list [3, 3, 0] to string "[3,3,0]" (no spaces)
                    normalized_value = '[' + ','.join(str(x) for x in grouping) + ']'
                elif isinstance(grouping, str):
                    # Remove all spaces from string representation
                    if grouping.startswith('[') and grouping.endswith(']'):
                        import re
                        numbers = re.findall(r'\d+', grouping)
                        if numbers:
                            normalized_value = '[' + ','.join(numbers) + ']'
                        else:
                            normalized_value = grouping.replace(' ', '')
                    else:
                        normalized_value = grouping.replace(' ', '')
                
                # Check if normalized value is valid
                if normalized_value:
                    if valid_selections is None:
                        # Can't check validity, try to use it (might fail, but we tried)
                        vals['grouping'] = normalized_value
                    elif normalized_value in valid_selections:
                        # Valid value, use it
                        vals['grouping'] = normalized_value
                    else:
                        # Not a valid selection value - remove it to use default
                        # Odoo will use the default grouping for the language
                        vals.pop('grouping', None)
                else:
                    # Couldn't normalize, remove it
                    vals.pop('grouping', None)
        
        return super().create(vals_list)

