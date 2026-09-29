import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

/**
 * Protect admin routes that require authentication.
 * If no JWT is found, redirect to the admin login page.
 */
const AdminProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('admin_token');
  const location = useLocation();

  if (!token) {
    // Redirect unauthenticated users to the login page
    return <Navigate to="/admin" state={{ from: location }} replace />;
  }

  // Token present – render the protected component tree
  return <>{children}</>;
};

export default AdminProtectedRoute;
