"""
Approval Adaptive Card for managers.
"""


def create_approval_card(
    request_id: str,
    employee_name: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    days: float,
    reason: str,
    applied_on: str,
) -> dict:
    """
    Create an Adaptive Card for leave approval.
    
    Args:
        request_id: Leave request ID
        employee_name: Name of the requesting employee
        leave_type: Type of leave
        start_date: Leave start date
        end_date: Leave end date
        days: Number of days
        reason: Reason for leave
        applied_on: Date the request was submitted
        
    Returns:
        Adaptive Card JSON structure
    """
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "⏳ Leave Approval Request",
                "weight": "Bolder",
                "size": "Large"
            },
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "Image",
                                        "url": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
                                        "size": "Small",
                                        "style": "Person"
                                    }
                                ]
                            },
                            {
                                "type": "Column",
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": employee_name,
                                        "weight": "Bolder"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"Applied on {applied_on}",
                                        "spacing": "None",
                                        "isSubtle": True,
                                        "size": "Small"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "type": "FactSet",
                "facts": [
                    {
                        "title": "Leave Type:",
                        "value": leave_type
                    },
                    {
                        "title": "Dates:",
                        "value": f"{start_date} to {end_date}"
                    },
                    {
                        "title": "Duration:",
                        "value": f"{days} day(s)"
                    }
                ]
            },
            {
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Reason:",
                        "weight": "Bolder"
                    },
                    {
                        "type": "TextBlock",
                        "text": reason,
                        "wrap": True
                    }
                ]
            },
            {
                "type": "Container",
                "separator": True,
                "spacing": "Medium",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Comments (optional):"
                    },
                    {
                        "type": "Input.Text",
                        "id": "comments",
                        "isMultiline": True,
                        "placeholder": "Add any comments..."
                    }
                ]
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "✅ Approve",
                "style": "positive",
                "data": {
                    "action": "approve_leave",
                    "request_id": request_id
                }
            },
            {
                "type": "Action.ShowCard",
                "title": "❌ Reject",
                "card": {
                    "type": "AdaptiveCard",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Reason for rejection *",
                            "weight": "Bolder"
                        },
                        {
                            "type": "Input.Text",
                            "id": "reason",
                            "isRequired": True,
                            "isMultiline": True,
                            "placeholder": "Please provide a reason for rejection..."
                        }
                    ],
                    "actions": [
                        {
                            "type": "Action.Submit",
                            "title": "Confirm Rejection",
                            "style": "destructive",
                            "data": {
                                "action": "reject_leave",
                                "request_id": request_id
                            }
                        }
                    ]
                }
            }
        ]
    }


def create_pending_approvals_card(
    manager_name: str,
    pending_requests: list[dict],
) -> dict:
    """
    Create an Adaptive Card listing all pending approvals.
    
    Args:
        manager_name: Name of the manager
        pending_requests: List of pending request summaries
        
    Returns:
        Adaptive Card JSON structure
    """
    if not pending_requests:
        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "✅ Pending Approvals",
                    "weight": "Bolder",
                    "size": "Large"
                },
                {
                    "type": "TextBlock",
                    "text": "You have no pending leave requests to approve.",
                    "wrap": True
                }
            ]
        }
    
    request_items = []
    for req in pending_requests:
        request_items.append({
            "type": "Container",
            "style": "emphasis",
            "selectAction": {
                "type": "Action.Submit",
                "data": {
                    "action": "view_approval",
                    "request_id": req["request_id"]
                }
            },
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
                                    "text": req["employee"],
                                    "weight": "Bolder"
                                },
                                {
                                    "type": "TextBlock",
                                    "text": f"{req['leave_type']} • {req['days']} day(s)",
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
                                    "text": req["start_date"],
                                    "size": "Small"
                                }
                            ]
                        }
                    ]
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
                "text": f"⏳ Pending Approvals ({len(pending_requests)})",
                "weight": "Bolder",
                "size": "Large"
            },
            {
                "type": "TextBlock",
                "text": "Click on a request to view details and take action.",
                "isSubtle": True,
                "spacing": "None"
            },
            *request_items
        ]
    }
