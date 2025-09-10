#!/usr/bin/env python3
"""
Cost parsing and formatting utilities.
Extracted from main.py for consistent cost handling across all contexts.

This module provides standardized cost operations:
- Parsing for mathematical calculations (using Decimal for precision)
- Formatting for user display
- Cleaning for form inputs
- Support for multiple currency symbols and formats
"""

from decimal import Decimal, InvalidOperation
import re


class CostUtils:
    """Utility class for consistent cost parsing across all contexts"""
    
    # Currency symbols to remove during parsing
    CURRENCY_SYMBOLS = ['$', '€', '£', '¥', '₹', '₽', '₩', 'CAD', 'USD', 'EUR', 'GBP', 'JPY']
    
    @staticmethod
    def parse_cost_for_calculation(cost_raw):
        """
        Parse cost for mathematical calculations (returns Decimal for precision)
        Used in dashboard totals and financial calculations
        
        Args:
            cost_raw: Raw cost value (string, number, or None)
            
        Returns:
            Decimal: Clean numeric value for calculations, Decimal('0') if invalid
        """
        if not cost_raw:
            return Decimal('0')
        
        try:
            if isinstance(cost_raw, str):
                # Remove currency symbols, commas, and whitespace
                clean_str = cost_raw.strip()
                
                # Remove currency symbols
                for symbol in CostUtils.CURRENCY_SYMBOLS:
                    clean_str = clean_str.replace(symbol, '')
                
                # Remove thousands separators (commas)
                clean_str = clean_str.replace(',', '')
                
                # Handle empty string after cleaning
                if not clean_str:
                    return Decimal('0')
                
                # Parse as Decimal for precision
                return Decimal(clean_str)
            
            # Convert numeric types to Decimal
            return Decimal(str(cost_raw))
            
        except (ValueError, TypeError, InvalidOperation):
            return Decimal('0')
    
    @staticmethod
    def format_cost_for_display(cost_raw):
        """
        Format cost for user display (returns formatted string)
        Used in subscription cards and UI display elements
        
        Args:
            cost_raw: Raw cost value (string, number, or None)
            
        Returns:
            str: Formatted display string like "$15.99" or "?" for zero/empty
        """
        if not cost_raw:
            return "?"
        
        try:
            # Parse using the calculation method for consistency
            cost_decimal = CostUtils.parse_cost_for_calculation(cost_raw)
            
            # Show negative values properly (don't hide them)
            if cost_decimal == 0:
                return "?"
            elif cost_decimal > 0:
                return f"${cost_decimal:.2f}"
            else:
                return f"-${abs(cost_decimal):.2f}"
                
        except (ValueError, TypeError):
            return "?"
    
    @staticmethod
    def clean_cost_for_input(cost_raw):
        """
        Clean cost for form input fields (returns string without currency symbols)
        Used when populating form inputs for editing
        
        Args:
            cost_raw: Raw cost value (string, number, or None)
            
        Returns:
            str: Clean string value suitable for input fields
        """
        if not cost_raw:
            return ''
        
        try:
            if isinstance(cost_raw, str):
                clean_str = cost_raw.strip()
                
                # Remove currency symbols but keep commas for user-friendly display
                for symbol in CostUtils.CURRENCY_SYMBOLS:
                    clean_str = clean_str.replace(symbol, '')
                
                return clean_str.strip()
            
            # For numeric types, convert to string
            return str(cost_raw)
            
        except (ValueError, TypeError):
            return ''


if __name__ == "__main__":
    # Allow standalone testing with comprehensive examples
    test_values = [
        # Basic cases
        None, "", "0", "0.00", "$15.99", "15.99", 15.99,
        # International currencies 
        "€25.50", "£12.99", "¥1000", "₹150.75",
        # Thousands separators
        "1,000.00", "$1,500.99", "€2,500.50",
        # Negative values
        "-15.99", "$-25.00", "-1,000.50",
        # Precision cases
        "99.999", "0.001", "0.005", "0.009",
        # Edge cases
        "invalid", "Price: $15.99", "15.99 monthly",
        # Scientific notation
        "1e6", "5.5e2"
    ]
    
    print("Testing Enhanced CostUtils with Decimal precision:")
    print("Value\t\t\t→ Calculation\t\t→ Display\t→ Input")
    print("-" * 80)
    
    for val in test_values:
        calc = CostUtils.parse_cost_for_calculation(val)
        display = CostUtils.format_cost_for_display(val)
        clean = CostUtils.clean_cost_for_input(val)
        print(f"{repr(val):<20}\t→ {str(calc):<12}\t→ {display:<12}\t→ {repr(clean)}")
    
    print("\nFinancial accuracy demonstration:")
    print("Sum of [0.1, 0.1, 0.1] using Decimal:", 
          sum([CostUtils.parse_cost_for_calculation("0.1") for _ in range(3)]))
    print("Format result:", 
          CostUtils.format_cost_for_display(sum([CostUtils.parse_cost_for_calculation("0.1") for _ in range(3)])))