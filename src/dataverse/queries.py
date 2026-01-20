"""
Dataverse query builders for common HR operations.

Provides pre-built OData queries and high-level methods
for interacting with HR entities in Dataverse.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from .client import DataverseClient
from .schema import (
    Employee,
    LeaveBalance,
    LeaveRequest,
    LeaveStatus,
    LeaveType,
)

logger = logging.getLogger(__name__)


class DataverseQueries:
    """
    High-level query interface for Dataverse HR entities.
    
    Wraps the raw DataverseClient with domain-specific methods
    that return properly typed Pydantic models.
    """
    
    # Entity set names in Dataverse
    EMPLOYEES = "hr_employees"
    LEAVE_TYPES = "hr_leavetypes"
    LEAVE_BALANCES = "hr_leavebalances"
    LEAVE_REQUESTS = "hr_leaverequests"
    
    def __init__(self, client: Optional[DataverseClient] = None):
        """
        Initialize with a Dataverse client.
        
        Args:
            client: Optional DataverseClient instance. Creates new one if not provided.
        """
        self.client = client or DataverseClient()
    
    # =========================================================================
    # Employee Queries
    # =========================================================================
    
    async def get_employee_by_email(self, email: str) -> Optional[Employee]:
        """
        Get an employee by their email address.
        
        Args:
            email: Employee's email address (matches Azure AD)
            
        Returns:
            Employee if found, None otherwise
        """
        try:
            # Escape single quotes to prevent OData injection
            safe_email = email.replace("'", "''")
            result = await self.client.get(
                entity_set=self.EMPLOYEES,
                filter_query=f"hr_email eq '{safe_email}'",
                top=1,
            )
            
            records = result.get("value", [])
            if records:
                return Employee.model_validate(records[0])
            return None
            
        except Exception as e:
            logger.error(f"Failed to get employee by email {email}: {e}")
            raise
    
    async def get_employee_by_id(self, employee_id: UUID) -> Optional[Employee]:
        """
        Get an employee by their Dataverse ID.
        
        Args:
            employee_id: Employee's Dataverse GUID
            
        Returns:
            Employee if found, None otherwise
        """
        try:
            result = await self.client.get(
                entity_set=self.EMPLOYEES,
                record_id=employee_id,
            )
            return Employee.model_validate(result)
            
        except Exception as e:
            logger.error(f"Failed to get employee by ID {employee_id}: {e}")
            raise
    
    async def get_direct_reports(self, manager_id: UUID) -> list[Employee]:
        """
        Get all employees who report to a manager.
        
        Args:
            manager_id: Manager's Dataverse GUID
            
        Returns:
            List of employees reporting to this manager
        """
        try:
            result = await self.client.get(
                entity_set=self.EMPLOYEES,
                filter_query=f"_hr_managerid_value eq {manager_id}",
            )
            
            records = result.get("value", [])
            return [Employee.model_validate(r) for r in records]
            
        except Exception as e:
            logger.error(f"Failed to get direct reports for {manager_id}: {e}")
            raise
    
    # =========================================================================
    # Leave Type Queries
    # =========================================================================
    
    async def get_all_leave_types(self) -> list[LeaveType]:
        """
        Get all configured leave types.
        
        Returns:
            List of all leave types
        """
        try:
            result = await self.client.get(entity_set=self.LEAVE_TYPES)
            records = result.get("value", [])
            return [LeaveType.model_validate(r) for r in records]
            
        except Exception as e:
            logger.error(f"Failed to get leave types: {e}")
            raise
    
    async def get_leave_type_by_code(self, code: str) -> Optional[LeaveType]:
        """
        Get a leave type by its code.
        
        Args:
            code: Leave type code (e.g., "CL", "SL")
            
        Returns:
            LeaveType if found, None otherwise
        """
        try:
            # Escape single quotes to prevent OData injection
            safe_code = code.upper().replace("'", "''")
            result = await self.client.get(
                entity_set=self.LEAVE_TYPES,
                filter_query=f"hr_code eq '{safe_code}'",
                top=1,
            )
            
            records = result.get("value", [])
            if records:
                return LeaveType.model_validate(records[0])
            return None
            
        except Exception as e:
            logger.error(f"Failed to get leave type by code {code}: {e}")
            raise
    
    # =========================================================================
    # Leave Balance Queries
    # =========================================================================
    
    async def get_leave_balances(
        self,
        employee_id: UUID,
        year: Optional[int] = None,
    ) -> list[LeaveBalance]:
        """
        Get leave balances for an employee.
        
        Args:
            employee_id: Employee's Dataverse GUID
            year: Optional calendar year (defaults to current year)
            
        Returns:
            List of leave balances with leave type info
        """
        if year is None:
            year = date.today().year
        
        try:
            result = await self.client.get(
                entity_set=self.LEAVE_BALANCES,
                filter_query=f"_hr_employeeid_value eq {employee_id} and hr_year eq {year}",
                expand=["hr_LeaveTypeId"],
            )
            
            balances = []
            for record in result.get("value", []):
                balance = LeaveBalance.model_validate(record)
                # Attach leave type from expanded property
                if "hr_LeaveTypeId" in record and record["hr_LeaveTypeId"]:
                    balance.leave_type = LeaveType.model_validate(record["hr_LeaveTypeId"])
                balances.append(balance)
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get leave balances for {employee_id}: {e}")
            raise
    
    async def update_leave_balance(
        self,
        balance_id: UUID,
        used: Optional[Decimal] = None,
        pending: Optional[Decimal] = None,
    ) -> LeaveBalance:
        """
        Update a leave balance record.
        
        Args:
            balance_id: Leave balance GUID
            used: New used days value
            pending: New pending days value
            
        Returns:
            Updated leave balance
        """
        data = {}
        if used is not None:
            data["hr_used"] = float(used)
        if pending is not None:
            data["hr_pending"] = float(pending)
        
        if not data:
            raise ValueError("No fields to update")
        
        # Recalculate available
        current = await self.client.get(self.LEAVE_BALANCES, balance_id)
        entitled = Decimal(str(current.get("hr_entitled", 0)))
        new_used = used if used is not None else Decimal(str(current.get("hr_used", 0)))
        new_pending = pending if pending is not None else Decimal(str(current.get("hr_pending", 0)))
        data["hr_available"] = float(entitled - new_used - new_pending)
        
        result = await self.client.update(self.LEAVE_BALANCES, balance_id, data)
        return LeaveBalance.model_validate(result)
    
    # =========================================================================
    # Leave Request Queries
    # =========================================================================
    
    async def get_leave_requests(
        self,
        employee_id: UUID,
        status: Optional[LeaveStatus] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 20,
    ) -> list[LeaveRequest]:
        """
        Get leave requests for an employee.
        
        Args:
            employee_id: Employee's Dataverse GUID
            status: Optional filter by status
            start_date: Optional filter by start date (on or after)
            end_date: Optional filter by end date (on or before)
            limit: Maximum records to return
            
        Returns:
            List of leave requests
        """
        filters = [f"_hr_employeeid_value eq {employee_id}"]
        
        if status:
            filters.append(f"hr_status eq {status.value}")
        if start_date:
            filters.append(f"hr_startdate ge {start_date.isoformat()}")
        if end_date:
            filters.append(f"hr_enddate le {end_date.isoformat()}")
        
        try:
            result = await self.client.get(
                entity_set=self.LEAVE_REQUESTS,
                filter_query=" and ".join(filters),
                expand=["hr_LeaveTypeId"],
                order_by="hr_startdate desc",
                top=limit,
            )
            
            requests = []
            for record in result.get("value", []):
                request = LeaveRequest.model_validate(record)
                if "hr_LeaveTypeId" in record and record["hr_LeaveTypeId"]:
                    request.leave_type = LeaveType.model_validate(record["hr_LeaveTypeId"])
                requests.append(request)
            
            return requests
            
        except Exception as e:
            logger.error(f"Failed to get leave requests for {employee_id}: {e}")
            raise
    
    async def get_pending_approvals(self, manager_id: UUID) -> list[LeaveRequest]:
        """
        Get pending leave requests for a manager to approve.
        
        Args:
            manager_id: Manager's Dataverse GUID
            
        Returns:
            List of pending leave requests from direct reports
        """
        # First get direct reports
        direct_reports = await self.get_direct_reports(manager_id)
        if not direct_reports:
            return []
        
        # Build filter for all direct report IDs
        employee_filters = " or ".join(
            f"_hr_employeeid_value eq {emp.id}" for emp in direct_reports
        )
        
        try:
            result = await self.client.get(
                entity_set=self.LEAVE_REQUESTS,
                filter_query=f"hr_status eq {LeaveStatus.PENDING.value} and ({employee_filters})",
                expand=["hr_EmployeeId", "hr_LeaveTypeId"],
                order_by="createdon asc",
            )
            
            requests = []
            for record in result.get("value", []):
                request = LeaveRequest.model_validate(record)
                if "hr_EmployeeId" in record and record["hr_EmployeeId"]:
                    request.employee = Employee.model_validate(record["hr_EmployeeId"])
                if "hr_LeaveTypeId" in record and record["hr_LeaveTypeId"]:
                    request.leave_type = LeaveType.model_validate(record["hr_LeaveTypeId"])
                requests.append(request)
            
            return requests
            
        except Exception as e:
            logger.error(f"Failed to get pending approvals for {manager_id}: {e}")
            raise
    
    async def create_leave_request(
        self,
        employee_id: UUID,
        leave_type_id: UUID,
        start_date: date,
        end_date: date,
        days: Decimal,
        reason: str,
    ) -> LeaveRequest:
        """
        Create a new leave request.
        
        Args:
            employee_id: Employee's Dataverse GUID
            leave_type_id: Leave type GUID
            start_date: Leave start date
            end_date: Leave end date
            days: Number of leave days
            reason: Reason for the leave
            
        Returns:
            Created leave request
        """
        request = LeaveRequest(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            days=days,
            reason=reason,
            status=LeaveStatus.PENDING,
        )
        
        try:
            result = await self.client.create(
                entity_set=self.LEAVE_REQUESTS,
                data=request.to_dataverse_dict(),
            )
            
            created = LeaveRequest.model_validate(result)
            logger.info(f"Created leave request {created.id} for employee {employee_id}")
            
            # Update pending balance
            balances = await self.get_leave_balances(employee_id)
            for balance in balances:
                if balance.leave_type_id == leave_type_id:
                    new_pending = balance.pending + days
                    await self.update_leave_balance(balance.id, pending=new_pending)
                    break
            
            return created
            
        except Exception as e:
            logger.error(f"Failed to create leave request: {e}")
            raise
    
    async def approve_leave_request(
        self,
        request_id: UUID,
        approver_id: UUID,
        comments: Optional[str] = None,
    ) -> LeaveRequest:
        """
        Approve a leave request.
        
        Args:
            request_id: Leave request GUID
            approver_id: Approving manager's GUID
            comments: Optional approval comments
            
        Returns:
            Updated leave request
        """
        data = {
            "hr_status": LeaveStatus.APPROVED.value,
            "hr_ApproverId@odata.bind": f"/hr_employees({approver_id})",
            "hr_approvaldate": datetime.utcnow().isoformat(),
        }
        if comments:
            data["hr_comments"] = comments
        
        try:
            result = await self.client.update(self.LEAVE_REQUESTS, request_id, data)
            approved = LeaveRequest.model_validate(result)
            
            # Move from pending to used
            balances = await self.get_leave_balances(approved.employee_id)
            for balance in balances:
                if balance.leave_type_id == approved.leave_type_id:
                    new_pending = max(Decimal("0"), balance.pending - approved.days)
                    new_used = balance.used + approved.days
                    await self.update_leave_balance(
                        balance.id, used=new_used, pending=new_pending
                    )
                    break
            
            logger.info(f"Approved leave request {request_id} by {approver_id}")
            return approved
            
        except Exception as e:
            logger.error(f"Failed to approve leave request {request_id}: {e}")
            raise
    
    async def reject_leave_request(
        self,
        request_id: UUID,
        approver_id: UUID,
        comments: str,
    ) -> LeaveRequest:
        """
        Reject a leave request.
        
        Args:
            request_id: Leave request GUID
            approver_id: Rejecting manager's GUID
            comments: Rejection reason (required)
            
        Returns:
            Updated leave request
        """
        data = {
            "hr_status": LeaveStatus.REJECTED.value,
            "hr_ApproverId@odata.bind": f"/hr_employees({approver_id})",
            "hr_approvaldate": datetime.utcnow().isoformat(),
            "hr_comments": comments,
        }
        
        try:
            result = await self.client.update(self.LEAVE_REQUESTS, request_id, data)
            rejected = LeaveRequest.model_validate(result)
            
            # Release pending balance
            balances = await self.get_leave_balances(rejected.employee_id)
            for balance in balances:
                if balance.leave_type_id == rejected.leave_type_id:
                    new_pending = max(Decimal("0"), balance.pending - rejected.days)
                    await self.update_leave_balance(balance.id, pending=new_pending)
                    break
            
            logger.info(f"Rejected leave request {request_id} by {approver_id}")
            return rejected
            
        except Exception as e:
            logger.error(f"Failed to reject leave request {request_id}: {e}")
            raise
