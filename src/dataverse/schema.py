"""
Pydantic models for Dataverse HR entities.

These models map to the Dataverse entity schema and provide
type-safe data handling throughout the application.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import IntEnum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class EmployeeStatus(IntEnum):
    """Employee status option set values in Dataverse."""
    ACTIVE = 1
    INACTIVE = 2
    ON_LEAVE = 3
    TERMINATED = 4


class LeaveStatus(IntEnum):
    """Leave request status option set values in Dataverse."""
    PENDING = 1
    APPROVED = 2
    REJECTED = 3
    CANCELLED = 4


class Employee(BaseModel):
    """
    Employee entity model.
    
    Maps to: hr_employee in Dataverse
    """
    id: Optional[UUID] = Field(None, alias="hr_employeeid")
    email: str = Field(..., alias="hr_email")
    display_name: str = Field(..., alias="hr_displayname")
    employee_code: str = Field(..., alias="hr_employeecode")
    department: str = Field(..., alias="hr_department")
    designation: str = Field(..., alias="hr_designation")
    manager_id: Optional[UUID] = Field(None, alias="_hr_managerid_value")
    joining_date: Optional[date] = Field(None, alias="hr_joiningdate")
    status: EmployeeStatus = Field(default=EmployeeStatus.ACTIVE, alias="hr_status")
    
    # Navigation properties (populated separately)
    manager: Optional["Employee"] = Field(None, exclude=True)
    
    class Config:
        populate_by_name = True
        use_enum_values = True

    def to_dataverse_dict(self) -> dict:
        """Convert to Dataverse-compatible dictionary for create/update."""
        data = {
            "hr_email": self.email,
            "hr_displayname": self.display_name,
            "hr_employeecode": self.employee_code,
            "hr_department": self.department,
            "hr_designation": self.designation,
            "hr_status": self.status,
        }
        if self.manager_id:
            data["hr_ManagerId@odata.bind"] = f"/hr_employees({self.manager_id})"
        if self.joining_date:
            data["hr_joiningdate"] = self.joining_date.isoformat()
        return data


class LeaveType(BaseModel):
    """
    Leave type entity model.
    
    Maps to: hr_leavetype in Dataverse
    """
    id: Optional[UUID] = Field(None, alias="hr_leavetypeid")
    name: str = Field(..., alias="hr_name")
    code: str = Field(..., alias="hr_code")  # CL, SL, EL, PL, ML
    annual_entitlement: int = Field(..., alias="hr_annualentitlement")
    carry_forward: bool = Field(default=False, alias="hr_carryforward")
    requires_approval: bool = Field(default=True, alias="hr_requiresapproval")
    
    class Config:
        populate_by_name = True

    def to_dataverse_dict(self) -> dict:
        """Convert to Dataverse-compatible dictionary for create/update."""
        return {
            "hr_name": self.name,
            "hr_code": self.code,
            "hr_annualentitlement": self.annual_entitlement,
            "hr_carryforward": self.carry_forward,
            "hr_requiresapproval": self.requires_approval,
        }


class LeaveBalance(BaseModel):
    """
    Leave balance entity model.
    
    Maps to: hr_leavebalance in Dataverse
    Tracks available leave days per employee per leave type per year.
    """
    id: Optional[UUID] = Field(None, alias="hr_leavebalanceid")
    employee_id: UUID = Field(..., alias="_hr_employeeid_value")
    leave_type_id: UUID = Field(..., alias="_hr_leavetypeid_value")
    year: int = Field(..., alias="hr_year")
    entitled: Decimal = Field(..., alias="hr_entitled")
    used: Decimal = Field(default=Decimal("0"), alias="hr_used")
    pending: Decimal = Field(default=Decimal("0"), alias="hr_pending")
    available: Decimal = Field(..., alias="hr_available")
    
    # Navigation properties (populated separately)
    leave_type: Optional[LeaveType] = Field(None, exclude=True)
    
    class Config:
        populate_by_name = True

    @computed_field
    @property
    def calculated_available(self) -> Decimal:
        """Calculate available balance (entitled - used - pending)."""
        return self.entitled - self.used - self.pending

    def to_dataverse_dict(self) -> dict:
        """Convert to Dataverse-compatible dictionary for create/update."""
        return {
            "hr_EmployeeId@odata.bind": f"/hr_employees({self.employee_id})",
            "hr_LeaveTypeId@odata.bind": f"/hr_leavetypes({self.leave_type_id})",
            "hr_year": self.year,
            "hr_entitled": float(self.entitled),
            "hr_used": float(self.used),
            "hr_pending": float(self.pending),
            "hr_available": float(self.available),
        }


class LeaveRequest(BaseModel):
    """
    Leave request entity model.
    
    Maps to: hr_leaverequest in Dataverse
    Represents a leave application from an employee.
    """
    id: Optional[UUID] = Field(None, alias="hr_leaverequestid")
    employee_id: UUID = Field(..., alias="_hr_employeeid_value")
    leave_type_id: UUID = Field(..., alias="_hr_leavetypeid_value")
    start_date: date = Field(..., alias="hr_startdate")
    end_date: date = Field(..., alias="hr_enddate")
    days: Decimal = Field(..., alias="hr_days")
    reason: str = Field(..., alias="hr_reason")
    status: LeaveStatus = Field(default=LeaveStatus.PENDING, alias="hr_status")
    approver_id: Optional[UUID] = Field(None, alias="_hr_approverid_value")
    approval_date: Optional[datetime] = Field(None, alias="hr_approvaldate")
    comments: Optional[str] = Field(None, alias="hr_comments")
    created_on: Optional[datetime] = Field(None, alias="createdon")
    
    # Navigation properties (populated separately)
    employee: Optional[Employee] = Field(None, exclude=True)
    leave_type: Optional[LeaveType] = Field(None, exclude=True)
    approver: Optional[Employee] = Field(None, exclude=True)
    
    class Config:
        populate_by_name = True
        use_enum_values = True

    @computed_field
    @property
    def status_display(self) -> str:
        """Get human-readable status."""
        status_map = {
            LeaveStatus.PENDING: "⏳ Pending",
            LeaveStatus.APPROVED: "✅ Approved",
            LeaveStatus.REJECTED: "❌ Rejected",
            LeaveStatus.CANCELLED: "🚫 Cancelled",
        }
        return status_map.get(LeaveStatus(self.status), "Unknown")

    @computed_field
    @property
    def date_range_display(self) -> str:
        """Get formatted date range string."""
        if self.start_date == self.end_date:
            return self.start_date.strftime("%d %b %Y")
        return f"{self.start_date.strftime('%d %b')} - {self.end_date.strftime('%d %b %Y')}"

    def to_dataverse_dict(self) -> dict:
        """Convert to Dataverse-compatible dictionary for create/update."""
        data = {
            "hr_EmployeeId@odata.bind": f"/hr_employees({self.employee_id})",
            "hr_LeaveTypeId@odata.bind": f"/hr_leavetypes({self.leave_type_id})",
            "hr_startdate": self.start_date.isoformat(),
            "hr_enddate": self.end_date.isoformat(),
            "hr_days": float(self.days),
            "hr_reason": self.reason,
            "hr_status": self.status,
        }
        if self.approver_id:
            data["hr_ApproverId@odata.bind"] = f"/hr_employees({self.approver_id})"
        if self.approval_date:
            data["hr_approvaldate"] = self.approval_date.isoformat()
        if self.comments:
            data["hr_comments"] = self.comments
        return data


# Standard leave types that will be seeded in Dataverse
STANDARD_LEAVE_TYPES = [
    LeaveType(
        name="Casual Leave",
        code="CL",
        annual_entitlement=12,
        carry_forward=False,
        requires_approval=True,
    ),
    LeaveType(
        name="Sick Leave",
        code="SL",
        annual_entitlement=10,
        carry_forward=False,
        requires_approval=True,
    ),
    LeaveType(
        name="Earned Leave",
        code="EL",
        annual_entitlement=15,
        carry_forward=True,
        requires_approval=True,
    ),
    LeaveType(
        name="Paternity Leave",
        code="PL",
        annual_entitlement=5,
        carry_forward=False,
        requires_approval=True,
    ),
    LeaveType(
        name="Maternity Leave",
        code="ML",
        annual_entitlement=180,
        carry_forward=False,
        requires_approval=True,
    ),
]
