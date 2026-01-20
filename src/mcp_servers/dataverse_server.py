"""
Dataverse MCP Server for HR operations.

Provides tools for interacting with Microsoft Dataverse
HR entities including employees, leave balances, and leave requests.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.dataverse import DataverseClient, DataverseQueries, LeaveStatus

from .base import MCPServer, MCPToolParameter, MCPToolResult

logger = logging.getLogger(__name__)


class DataverseMCPServer(MCPServer):
    """
    MCP Server for Microsoft Dataverse HR operations.
    
    Provides tools for:
    - Employee information lookup
    - Leave balance queries
    - Leave history retrieval
    - Leave request submission
    - Leave approval/rejection (for managers)
    """
    
    def __init__(self):
        """Initialize the Dataverse MCP server."""
        self.client = DataverseClient()
        self.queries = DataverseQueries(self.client)
        super().__init__(
            name="dataverse",
            description="Microsoft Dataverse HR operations server"
        )
    
    def _register_tools(self) -> None:
        """Register all Dataverse tools."""
        
        # Get Employee Info
        self.register_tool(
            name="get_employee_info",
            description=(
                "Get employee information including name, department, designation, "
                "manager, and joining date. Use this when someone asks about their "
                "profile or employee details."
            ),
            parameters=[
                MCPToolParameter(
                    name="email",
                    description="Employee's email address",
                    type="string",
                ),
            ],
            handler=self._get_employee_info,
        )
        
        # Get Leave Balance
        self.register_tool(
            name="get_leave_balance",
            description=(
                "Get leave balances for an employee, showing entitled, used, "
                "pending, and available days for each leave type. Use this when "
                "someone asks about their leave balance or how many days they have."
            ),
            parameters=[
                MCPToolParameter(
                    name="email",
                    description="Employee's email address",
                    type="string",
                ),
                MCPToolParameter(
                    name="year",
                    description="Calendar year (defaults to current year)",
                    type="integer",
                    required=False,
                ),
            ],
            handler=self._get_leave_balance,
        )
        
        # Get Leave History
        self.register_tool(
            name="get_leave_history",
            description=(
                "Get leave request history for an employee, showing past and "
                "pending requests with dates, type, status, and reason."
            ),
            parameters=[
                MCPToolParameter(
                    name="email",
                    description="Employee's email address",
                    type="string",
                ),
                MCPToolParameter(
                    name="status",
                    description="Filter by status: pending, approved, rejected, cancelled",
                    type="string",
                    required=False,
                    enum=["pending", "approved", "rejected", "cancelled"],
                ),
                MCPToolParameter(
                    name="limit",
                    description="Maximum number of records to return (default: 10)",
                    type="integer",
                    required=False,
                    default=10,
                ),
            ],
            handler=self._get_leave_history,
        )
        
        # Submit Leave Request
        self.register_tool(
            name="submit_leave_request",
            description=(
                "Submit a new leave request for an employee. Validates availability "
                "and creates the request in pending status. Use this when someone "
                "wants to apply for leave."
            ),
            parameters=[
                MCPToolParameter(
                    name="email",
                    description="Employee's email address",
                    type="string",
                ),
                MCPToolParameter(
                    name="leave_type",
                    description="Type of leave: CL (Casual), SL (Sick), EL (Earned), PL (Paternity), ML (Maternity)",
                    type="string",
                    enum=["CL", "SL", "EL", "PL", "ML"],
                ),
                MCPToolParameter(
                    name="start_date",
                    description="Leave start date in YYYY-MM-DD format",
                    type="string",
                ),
                MCPToolParameter(
                    name="end_date",
                    description="Leave end date in YYYY-MM-DD format",
                    type="string",
                ),
                MCPToolParameter(
                    name="reason",
                    description="Reason for taking leave",
                    type="string",
                ),
            ],
            handler=self._submit_leave_request,
        )
        
        # Get Pending Approvals (for managers)
        self.register_tool(
            name="get_pending_approvals",
            description=(
                "Get pending leave requests that need approval from a manager. "
                "Only works for employees who have direct reports."
            ),
            parameters=[
                MCPToolParameter(
                    name="manager_email",
                    description="Manager's email address",
                    type="string",
                ),
            ],
            handler=self._get_pending_approvals,
        )
        
        # Approve Leave Request
        self.register_tool(
            name="approve_leave_request",
            description=(
                "Approve a pending leave request. Only the employee's manager "
                "can approve requests."
            ),
            parameters=[
                MCPToolParameter(
                    name="manager_email",
                    description="Manager's email address",
                    type="string",
                ),
                MCPToolParameter(
                    name="request_id",
                    description="Leave request ID to approve",
                    type="string",
                ),
                MCPToolParameter(
                    name="comments",
                    description="Optional approval comments",
                    type="string",
                    required=False,
                ),
            ],
            handler=self._approve_leave_request,
        )
        
        # Reject Leave Request
        self.register_tool(
            name="reject_leave_request",
            description=(
                "Reject a pending leave request. Only the employee's manager "
                "can reject requests. A reason must be provided."
            ),
            parameters=[
                MCPToolParameter(
                    name="manager_email",
                    description="Manager's email address",
                    type="string",
                ),
                MCPToolParameter(
                    name="request_id",
                    description="Leave request ID to reject",
                    type="string",
                ),
                MCPToolParameter(
                    name="reason",
                    description="Reason for rejection",
                    type="string",
                ),
            ],
            handler=self._reject_leave_request,
        )
    
    # =========================================================================
    # Tool Handlers
    # =========================================================================
    
    async def _get_employee_info(self, email: str) -> MCPToolResult:
        """Get employee information by email."""
        try:
            employee = await self.queries.get_employee_by_email(email)
            
            if not employee:
                return MCPToolResult.error(f"Employee not found with email: {email}")
            
            # Get manager info if available
            manager_name = None
            if employee.manager_id:
                manager = await self.queries.get_employee_by_id(employee.manager_id)
                if manager:
                    manager_name = manager.display_name
            
            return MCPToolResult.success({
                "employee_code": employee.employee_code,
                "name": employee.display_name,
                "email": employee.email,
                "department": employee.department,
                "designation": employee.designation,
                "manager": manager_name,
                "joining_date": employee.joining_date.isoformat() if employee.joining_date else None,
                "status": "Active" if employee.status == 1 else "Inactive",
            })
            
        except Exception as e:
            logger.error(f"Failed to get employee info: {e}")
            return MCPToolResult.error(str(e))
    
    async def _get_leave_balance(
        self,
        email: str,
        year: Optional[int] = None,
    ) -> MCPToolResult:
        """Get leave balance for an employee."""
        try:
            employee = await self.queries.get_employee_by_email(email)
            
            if not employee:
                return MCPToolResult.error(f"Employee not found with email: {email}")
            
            balances = await self.queries.get_leave_balances(
                employee.id,
                year=year,
            )
            
            balance_data = []
            for balance in balances:
                leave_type_name = balance.leave_type.name if balance.leave_type else "Unknown"
                leave_type_code = balance.leave_type.code if balance.leave_type else "?"
                
                balance_data.append({
                    "leave_type": leave_type_name,
                    "code": leave_type_code,
                    "entitled": float(balance.entitled),
                    "used": float(balance.used),
                    "pending": float(balance.pending),
                    "available": float(balance.available),
                })
            
            return MCPToolResult.success({
                "employee_name": employee.display_name,
                "year": year or date.today().year,
                "balances": balance_data,
            })
            
        except Exception as e:
            logger.error(f"Failed to get leave balance: {e}")
            return MCPToolResult.error(str(e))
    
    async def _get_leave_history(
        self,
        email: str,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> MCPToolResult:
        """Get leave request history for an employee."""
        try:
            employee = await self.queries.get_employee_by_email(email)
            
            if not employee:
                return MCPToolResult.error(f"Employee not found with email: {email}")
            
            # Convert status string to enum
            status_enum = None
            if status:
                status_map = {
                    "pending": LeaveStatus.PENDING,
                    "approved": LeaveStatus.APPROVED,
                    "rejected": LeaveStatus.REJECTED,
                    "cancelled": LeaveStatus.CANCELLED,
                }
                status_enum = status_map.get(status.lower())
            
            requests = await self.queries.get_leave_requests(
                employee.id,
                status=status_enum,
                limit=limit,
            )
            
            history = []
            for req in requests:
                leave_type_name = req.leave_type.name if req.leave_type else "Unknown"
                
                history.append({
                    "id": str(req.id),
                    "leave_type": leave_type_name,
                    "start_date": req.start_date.isoformat(),
                    "end_date": req.end_date.isoformat(),
                    "days": float(req.days),
                    "reason": req.reason,
                    "status": req.status_display,
                    "applied_on": req.created_on.isoformat() if req.created_on else None,
                    "comments": req.comments,
                })
            
            return MCPToolResult.success({
                "employee_name": employee.display_name,
                "requests": history,
            })
            
        except Exception as e:
            logger.error(f"Failed to get leave history: {e}")
            return MCPToolResult.error(str(e))
    
    async def _submit_leave_request(
        self,
        email: str,
        leave_type: str,
        start_date: str,
        end_date: str,
        reason: str,
    ) -> MCPToolResult:
        """Submit a new leave request."""
        try:
            # Get employee
            employee = await self.queries.get_employee_by_email(email)
            if not employee:
                return MCPToolResult.error(f"Employee not found with email: {email}")
            
            # Get leave type
            leave_type_obj = await self.queries.get_leave_type_by_code(leave_type)
            if not leave_type_obj:
                return MCPToolResult.error(f"Invalid leave type: {leave_type}")
            
            # Parse and validate dates
            try:
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date)
            except ValueError:
                return MCPToolResult.error("Invalid date format. Use YYYY-MM-DD.")
            
            today = date.today()
            if start < today:
                return MCPToolResult.error("Start date cannot be in the past.")
            
            if end < start:
                return MCPToolResult.error("End date cannot be before start date.")
            
            # Calculate days (simple calculation - business days would be more complex)
            days = Decimal(str((end - start).days + 1))
            
            # Check balance
            balances = await self.queries.get_leave_balances(employee.id)
            available = Decimal("0")
            for balance in balances:
                if balance.leave_type_id == leave_type_obj.id:
                    available = balance.available
                    break
            
            if days > available:
                return MCPToolResult.error(
                    f"Insufficient leave balance. Requested: {days} days, "
                    f"Available: {available} days of {leave_type_obj.name}."
                )
            
            # Create the request
            request = await self.queries.create_leave_request(
                employee_id=employee.id,
                leave_type_id=leave_type_obj.id,
                start_date=start,
                end_date=end,
                days=days,
                reason=reason,
            )
            
            return MCPToolResult.success({
                "request_id": str(request.id),
                "employee": employee.display_name,
                "leave_type": leave_type_obj.name,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "days": float(days),
                "status": "Pending Approval",
                "message": (
                    f"Leave request submitted successfully for {days} days of "
                    f"{leave_type_obj.name} from {start.strftime('%d %b %Y')} to "
                    f"{end.strftime('%d %b %Y')}. Awaiting manager approval."
                ),
            })
            
        except Exception as e:
            logger.error(f"Failed to submit leave request: {e}")
            return MCPToolResult.error(str(e))
    
    async def _get_pending_approvals(self, manager_email: str) -> MCPToolResult:
        """Get pending leave requests for a manager."""
        try:
            manager = await self.queries.get_employee_by_email(manager_email)
            if not manager:
                return MCPToolResult.error(f"Manager not found with email: {manager_email}")
            
            pending = await self.queries.get_pending_approvals(manager.id)
            
            if not pending:
                return MCPToolResult.success({
                    "manager": manager.display_name,
                    "pending_count": 0,
                    "requests": [],
                    "message": "No pending leave requests to approve.",
                })
            
            requests = []
            for req in pending:
                emp_name = req.employee.display_name if req.employee else "Unknown"
                leave_type = req.leave_type.name if req.leave_type else "Unknown"
                
                requests.append({
                    "request_id": str(req.id),
                    "employee": emp_name,
                    "leave_type": leave_type,
                    "start_date": req.start_date.isoformat(),
                    "end_date": req.end_date.isoformat(),
                    "days": float(req.days),
                    "reason": req.reason,
                    "applied_on": req.created_on.isoformat() if req.created_on else None,
                })
            
            return MCPToolResult.success({
                "manager": manager.display_name,
                "pending_count": len(requests),
                "requests": requests,
            })
            
        except Exception as e:
            logger.error(f"Failed to get pending approvals: {e}")
            return MCPToolResult.error(str(e))
    
    async def _approve_leave_request(
        self,
        manager_email: str,
        request_id: str,
        comments: Optional[str] = None,
    ) -> MCPToolResult:
        """Approve a leave request."""
        try:
            manager = await self.queries.get_employee_by_email(manager_email)
            if not manager:
                return MCPToolResult.error(f"Manager not found with email: {manager_email}")
            
            try:
                req_uuid = UUID(request_id)
            except ValueError:
                return MCPToolResult.error("Invalid request ID format.")
            
            request = await self.queries.approve_leave_request(
                request_id=req_uuid,
                approver_id=manager.id,
                comments=comments,
            )
            
            return MCPToolResult.success({
                "request_id": str(request.id),
                "status": "Approved",
                "approved_by": manager.display_name,
                "approved_on": datetime.utcnow().isoformat(),
                "message": "Leave request has been approved successfully.",
            })
            
        except Exception as e:
            logger.error(f"Failed to approve leave request: {e}")
            return MCPToolResult.error(str(e))
    
    async def _reject_leave_request(
        self,
        manager_email: str,
        request_id: str,
        reason: str,
    ) -> MCPToolResult:
        """Reject a leave request."""
        try:
            manager = await self.queries.get_employee_by_email(manager_email)
            if not manager:
                return MCPToolResult.error(f"Manager not found with email: {manager_email}")
            
            try:
                req_uuid = UUID(request_id)
            except ValueError:
                return MCPToolResult.error("Invalid request ID format.")
            
            request = await self.queries.reject_leave_request(
                request_id=req_uuid,
                approver_id=manager.id,
                comments=reason,
            )
            
            return MCPToolResult.success({
                "request_id": str(request.id),
                "status": "Rejected",
                "rejected_by": manager.display_name,
                "rejected_on": datetime.utcnow().isoformat(),
                "reason": reason,
                "message": "Leave request has been rejected.",
            })
            
        except Exception as e:
            logger.error(f"Failed to reject leave request: {e}")
            return MCPToolResult.error(str(e))
