"""
Leave Balance Adaptive Card.
"""

from typing import Optional


def create_leave_balance_card(
    employee_name: str,
    year: int,
    balances: list[dict],
) -> dict:
    """
    Create an Adaptive Card displaying leave balances.
    
    Args:
        employee_name: Name of the employee
        year: Calendar year for the balances
        balances: List of balance dictionaries with keys:
            - leave_type: Name of leave type
            - code: Leave type code
            - entitled: Total entitled days
            - used: Days used
            - pending: Days in pending requests
            - available: Available days
            
    Returns:
        Adaptive Card JSON structure
    """
    # Build balance rows
    balance_rows = []
    for balance in balances:
        row = {
            "type": "TableRow",
            "cells": [
                {
                    "type": "TableCell",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"{balance['code']}",
                            "weight": "Bolder"
                        }
                    ]
                },
                {
                    "type": "TableCell",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": str(balance['entitled'])
                        }
                    ]
                },
                {
                    "type": "TableCell",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": str(balance['used'])
                        }
                    ]
                },
                {
                    "type": "TableCell",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": str(balance['pending']),
                            "color": "Warning" if balance['pending'] > 0 else "Default"
                        }
                    ]
                },
                {
                    "type": "TableCell",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": str(balance['available']),
                            "weight": "Bolder",
                            "color": "Good" if balance['available'] > 0 else "Attention"
                        }
                    ]
                }
            ]
        }
        balance_rows.append(row)
    
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": f"📊 Leave Balance - {year}",
                "weight": "Bolder",
                "size": "Large"
            },
            {
                "type": "TextBlock",
                "text": employee_name,
                "isSubtle": True,
                "spacing": "None"
            },
            {
                "type": "Table",
                "columns": [
                    {"width": 1},
                    {"width": 1},
                    {"width": 1},
                    {"width": 1},
                    {"width": 1}
                ],
                "rows": [
                    {
                        "type": "TableRow",
                        "style": "accent",
                        "cells": [
                            {
                                "type": "TableCell",
                                "items": [{"type": "TextBlock", "text": "Type", "weight": "Bolder"}]
                            },
                            {
                                "type": "TableCell",
                                "items": [{"type": "TextBlock", "text": "Entitled", "weight": "Bolder"}]
                            },
                            {
                                "type": "TableCell",
                                "items": [{"type": "TextBlock", "text": "Used", "weight": "Bolder"}]
                            },
                            {
                                "type": "TableCell",
                                "items": [{"type": "TextBlock", "text": "Pending", "weight": "Bolder"}]
                            },
                            {
                                "type": "TableCell",
                                "items": [{"type": "TextBlock", "text": "Available", "weight": "Bolder"}]
                            }
                        ]
                    },
                    *balance_rows
                ]
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "📝 Apply for Leave",
                "data": {
                    "action": "apply_leave"
                }
            }
        ]
    }
