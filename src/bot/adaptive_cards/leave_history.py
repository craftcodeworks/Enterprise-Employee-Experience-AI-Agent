"""
Leave History Adaptive Card.
"""

from typing import Optional


def create_leave_history_card(
    employee_name: str,
    requests: list[dict],
    filter_status: Optional[str] = None,
) -> dict:
    """
    Create an Adaptive Card displaying leave history.
    
    Args:
        employee_name: Name of the employee
        requests: List of leave request dictionaries with keys:
            - id: Request ID
            - leave_type: Name of leave type
            - start_date: Start date string
            - end_date: End date string
            - days: Number of days
            - status: Status display string
            - reason: Reason for leave
            
    Returns:
        Adaptive Card JSON structure
    """
    if not requests:
        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "📋 Leave History",
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
                    "type": "Container",
                    "style": "emphasis",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "No leave requests found.",
                            "wrap": True
                        }
                    ]
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "📝 Apply for Leave",
                    "data": {"action": "apply_leave"}
                }
            ]
        }
    
    # Build request items
    request_items = []
    for req in requests:
        status_color = "Default"
        if "Approved" in req["status"]:
            status_color = "Good"
        elif "Rejected" in req["status"]:
            status_color = "Attention"
        elif "Pending" in req["status"]:
            status_color = "Warning"
        
        request_items.append({
            "type": "Container",
            "style": "emphasis",
            "spacing": "Small",
            "items": [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": req["leave_type"],
                                    "weight": "Bolder"
                                },
                                {
                                    "type": "TextBlock",
                                    "text": f"{req['start_date']} - {req['end_date']} ({req['days']} days)",
                                    "spacing": "None",
                                    "isSubtle": True
                                }
                            ]
                        },
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": req["status"],
                                    "color": status_color,
                                    "weight": "Bolder"
                                }
                            ]
                        }
                    ]
                },
                {
                    "type": "TextBlock",
                    "text": req.get("reason", ""),
                    "wrap": True,
                    "isSubtle": True,
                    "size": "Small"
                }
            ]
        })
    
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "📋 Leave History",
                "weight": "Bolder",
                "size": "Large"
            },
            {
                "type": "TextBlock",
                "text": f"{employee_name} • {len(requests)} requests",
                "isSubtle": True,
                "spacing": "None"
            },
            *request_items
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "📝 Apply for Leave",
                "data": {"action": "apply_leave"}
            }
        ]
    }
