"""
Audit Logger - Centralized action logging service
"""
from sqlalchemy.orm import Session
from typing import Optional, Any
from fastapi import Request

from app.models import AuditLog


class AuditLogger:
    """Simple audit logging service"""
    
    @staticmethod
    def log(
        db: Session,
        action: str,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Log an action to the audit_logs table.
        
        Args:
            db: Database session
            action: Action type (login, apply, status_change, resume_upload)
            user_id: ID of user performing the action
            resource_type: Type of resource affected (application, job, user)
            resource_id: ID of the affected resource
            details: Additional context as JSON
            ip_address: Client IP address
        """
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
        print(f"[AUDIT] {action} | user={user_id} | {resource_type}={resource_id}")
        return log_entry
    
    @staticmethod
    def get_client_ip(request: Request) -> Optional[str]:
        """Extract client IP from request, handling proxies"""
        # Check for forwarded header (behind proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        # Direct connection
        if request.client:
            return request.client.host
        return None


# Convenience function for dependency injection
def get_audit_logger() -> AuditLogger:
    return AuditLogger()
