"""Dataverse integration module for HR entities."""

from .client import DataverseClient
from .schema import (
    Employee,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    LeaveStatus,
    EmployeeStatus,
)
from .queries import DataverseQueries

__all__ = [
    "DataverseClient",
    "DataverseQueries",
    "Employee",
    "LeaveType",
    "LeaveBalance",
    "LeaveRequest",
    "LeaveStatus",
    "EmployeeStatus",
]
