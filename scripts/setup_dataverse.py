"""
Script to set up Dataverse entities and seed initial data.

This script creates the required entities in Dataverse and
seeds them with default leave types.

Prerequisites:
- Dataverse environment must exist
- App registration must have Dataverse permissions

Usage:
    python scripts/setup_dataverse.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.dataverse import DataverseClient
from src.dataverse.schema import STANDARD_LEAVE_TYPES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


ENTITY_DEFINITIONS = {
    "hr_employee": {
        "display_name": "HR Employee",
        "description": "Stores employee information",
        "primary_field": "hr_displayname",
    },
    "hr_leavetype": {
        "display_name": "HR Leave Type",
        "description": "Leave type definitions",
        "primary_field": "hr_name",
    },
    "hr_leavebalance": {
        "display_name": "HR Leave Balance",
        "description": "Employee leave balances by type and year",
        "primary_field": "hr_leavebalanceid",
    },
    "hr_leaverequest": {
        "display_name": "HR Leave Request",
        "description": "Employee leave requests",
        "primary_field": "hr_leaverequestid",
    },
}


async def seed_leave_types(client: DataverseClient) -> None:
    """Seed standard leave types."""
    logger.info("Seeding leave types...")
    
    for leave_type in STANDARD_LEAVE_TYPES:
        try:
            # Check if already exists
            result = await client.get(
                entity_set="hr_leavetypes",
                filter_query=f"hr_code eq '{leave_type.code}'",
                top=1,
            )
            
            if result.get("value"):
                logger.info(f"Leave type {leave_type.code} already exists, skipping")
                continue
            
            # Create leave type
            await client.create(
                entity_set="hr_leavetypes",
                data=leave_type.to_dataverse_dict(),
            )
            logger.info(f"Created leave type: {leave_type.name} ({leave_type.code})")
            
        except Exception as e:
            logger.error(f"Failed to create leave type {leave_type.code}: {e}")


async def main():
    """Main setup function."""
    logger.info("Starting Dataverse setup...")
    
    try:
        settings = get_settings()
        logger.info(f"Dataverse URL: {settings.dataverse_url}")
        
        client = DataverseClient()
        
        # Note: Entity creation requires Dataverse SDK or Power Platform API
        # This script focuses on seeding initial data
        logger.info("""
╔══════════════════════════════════════════════════════════════════╗
║                    DATAVERSE SETUP GUIDE                         ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  The following entities need to be created in Dataverse:         ║
║                                                                  ║
║  1. hr_employee                                                  ║
║     - hr_email (Text, Required)                                  ║
║     - hr_displayname (Text, Required)                            ║
║     - hr_employeecode (Text, Required)                           ║
║     - hr_department (Text)                                       ║
║     - hr_designation (Text)                                      ║
║     - hr_managerid (Lookup to hr_employee)                       ║
║     - hr_joiningdate (DateTime)                                  ║
║     - hr_status (OptionSet: Active=1, Inactive=2)                ║
║                                                                  ║
║  2. hr_leavetype                                                 ║
║     - hr_name (Text, Required)                                   ║
║     - hr_code (Text, Required)                                   ║
║     - hr_annualentitlement (Integer)                             ║
║     - hr_carryforward (Boolean)                                  ║
║     - hr_requiresapproval (Boolean)                              ║
║                                                                  ║
║  3. hr_leavebalance                                              ║
║     - hr_employeeid (Lookup to hr_employee)                      ║
║     - hr_leavetypeid (Lookup to hr_leavetype)                    ║
║     - hr_year (Integer)                                          ║
║     - hr_entitled (Decimal)                                      ║
║     - hr_used (Decimal)                                          ║
║     - hr_pending (Decimal)                                       ║
║     - hr_available (Decimal)                                     ║
║                                                                  ║
║  4. hr_leaverequest                                              ║
║     - hr_employeeid (Lookup to hr_employee)                      ║
║     - hr_leavetypeid (Lookup to hr_leavetype)                    ║
║     - hr_startdate (DateTime)                                    ║
║     - hr_enddate (DateTime)                                      ║
║     - hr_days (Decimal)                                          ║
║     - hr_reason (Text)                                           ║
║     - hr_status (OptionSet: Pending=1, Approved=2, Rejected=3)   ║
║     - hr_approverid (Lookup to hr_employee)                      ║
║     - hr_approvaldate (DateTime)                                 ║
║     - hr_comments (Text)                                         ║
║                                                                  ║
║  Create these entities using:                                    ║
║  - Power Apps Maker Portal (make.powerapps.com)                  ║
║  - Power Platform CLI                                            ║
║  - Dataverse SDK                                                 ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
        """)
        
        # Seed leave types
        await seed_leave_types(client)
        
        logger.info("\nSetup complete!")
        
    except Exception as e:
        logger.error(f"Setup failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
