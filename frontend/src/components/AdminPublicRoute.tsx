import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

/**
 * Wrapper for admin pages that should be publicly accessible only when the
 * admin is *not* authenticated (e.g., the login page).
 *
 * If a JWT token exists, we assume the admin is already logged in and redirect
 * them to the dashboard (or the page they originally tried to access).
 */
export const AdminPublicRoute: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const token = localStorage.getItem('admin_token');
  const location = useLocation();

  if (token) {
    // Already logged in – go to the protected dashboard
    return <Navigate to="/admin/dashboard" state={{ from: location }} replace />;
  }

  // Not logged in – render the public component (login form)
  return <>{children}</>;
};
