from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied


def role_required(allowed_roles):
    """
    Decorator to restrict view access to specific user roles.
    Allowed roles: 'Admin', 'Manager', 'Sales Staff', 'Inventory Staff'.
    Admins / superusers always have full access.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Superusers bypass role checks
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_role = getattr(request.user, 'role', None)
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)

            messages.error(
                request,
                f"Access Denied: Your role ({user_role}) does not have permission to view this page."
            )
            return redirect('dashboard')
        return _wrapped_view
    return decorator


def admin_required(view_func):
    return role_required(['Admin'])(view_func)


def manager_required(view_func):
    return role_required(['Admin', 'Manager'])(view_func)


def sales_required(view_func):
    return role_required(['Admin', 'Manager', 'Sales Staff'])(view_func)


def inventory_required(view_func):
    return role_required(['Admin', 'Manager', 'Inventory Staff'])(view_func)
