"""
Leave Request Form Adaptive Card.
"""

from datetime import date, timedelta


def create_leave_request_card(
    prefill_type: str = None,
    prefill_start: str = None,
    prefill_end: str = None,
    prefill_reason: str = None,
) -> dict:
    """
    Create an Adaptive Card with a leave request form.
    
    Args:
        prefill_type: Optional pre-selected leave type
        prefill_start: Optional pre-filled start date
        prefill_end: Optional pre-filled end date
        prefill_reason: Optional pre-filled reason
        
    Returns:
        Adaptive Card JSON structure
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "📝 Apply for Leave",
                "weight": "Bolder",
                "size": "Large"
            },
            {
                "type": "TextBlock",
                "text": "Fill in the details below to submit your leave request.",
                "isSubtle": True,
                "wrap": True
            },
            {
                "type": "Container",
                "separator": True,
                "spacing": "Medium",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Leave Type *",
                        "weight": "Bolder"
                    },
                    {
                        "type": "Input.ChoiceSet",
                        "id": "leave_type",
                        "style": "compact",
                        "isRequired": True,
                        "errorMessage": "Please select a leave type",
                        "value": prefill_type or "",
                        "choices": [
                            {"title": "🏖️ Casual Leave (CL)", "value": "CL"},
                            {"title": "🏥 Sick Leave (SL)", "value": "SL"},
                            {"title": "📅 Earned Leave (EL)", "value": "EL"},
                            {"title": "👶 Paternity Leave (PL)", "value": "PL"},
                            {"title": "🤱 Maternity Leave (ML)", "value": "ML"}
                        ]
                    }
                ]
            },
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "1",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "Start Date *",
                                "weight": "Bolder"
                            },
                            {
                                "type": "Input.Date",
                                "id": "start_date",
                                "isRequired": True,
                                "errorMessage": "Please select a start date",
                                "value": prefill_start or tomorrow.isoformat(),
                                "min": today.isoformat()
                            }
                        ]
                    },
                    {
                        "type": "Column",
                        "width": "1",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "End Date *",
                                "weight": "Bolder"
                            },
                            {
                                "type": "Input.Date",
                                "id": "end_date",
                                "isRequired": True,
                                "errorMessage": "Please select an end date",
                                "value": prefill_end or tomorrow.isoformat(),
                                "min": today.isoformat()
                            }
                        ]
                    }
                ]
            },
            {
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Reason *",
                        "weight": "Bolder"
                    },
                    {
                        "type": "Input.Text",
                        "id": "reason",
                        "isRequired": True,
                        "isMultiline": True,
                        "placeholder": "Please provide a reason for your leave request...",
                        "errorMessage": "Please provide a reason",
                        "value": prefill_reason or "",
                        "maxLength": 500
                    }
                ]
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "✅ Submit Request",
                "style": "positive",
                "data": {
                    "action": "submit_leave_request"
                }
            },
            {
                "type": "Action.Submit",
                "title": "❌ Cancel",
                "data": {
                    "action": "cancel"
                }
            }
        ]
    }
