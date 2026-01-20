"""Authentication module for Azure AD SSO."""

from .sso import SSOHandler, UserIdentity

__all__ = ["SSOHandler", "UserIdentity"]
