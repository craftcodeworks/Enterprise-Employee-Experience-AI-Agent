"""
Welcome Adaptive Card for new users.
"""


def create_welcome_card(user_name: str) -> dict:
    """
    Create a welcome Adaptive Card for new users.
    
    Args:
        user_name: Name of the user to welcome
        
    Returns:
        Adaptive Card JSON structure
    """
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
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
                                        "size": "Medium",
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
                                        "text": f"Welcome, {user_name}! 👋",
                                        "weight": "Bolder",
                                        "size": "Large",
                                        "wrap": True
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": "I'm your HR Helpdesk Assistant",
                                        "spacing": "None",
                                        "isSubtle": True,
                                        "wrap": True
                                    }
                                ]
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
                        "text": "I can help you with:",
                        "weight": "Bolder",
                        "spacing": "Medium"
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {
                                "title": "📋",
                                "value": "Company policies and procedures"
                            },
                            {
                                "title": "📊",
                                "value": "Leave balance and history"
                            },
                            {
                                "title": "📝",
                                "value": "Leave applications"
                            },
                            {
                                "title": "✅",
                                "value": "Approval workflows (for managers)"
                            }
                        ]
                    }
                ]
            },
            {
                "type": "TextBlock",
                "text": "Try asking me something like:",
                "weight": "Bolder",
                "spacing": "Medium"
            },
            {
                "type": "TextBlock",
                "text": "• \"What's my leave balance?\"\n• \"I want to apply for sick leave\"\n• \"What is the work from home policy?\"",
                "wrap": True,
                "spacing": "Small"
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "📊 Check Leave Balance",
                "data": {
                    "action": "check_balance"
                }
            },
            {
                "type": "Action.Submit",
                "title": "📝 Apply for Leave",
                "data": {
                    "action": "apply_leave"
                }
            }
        ]
    }
