
// import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing';
import StudentLogin from './pages/StudentLogin';
import StudentChat from './pages/StudentChat';
import ForgotPassword from './pages/ForgotPassword';
import AdminLogin from './pages/AdminLogin';
import AdminDashboard from './pages/AdminDashboard';
import StudentLogsPage from './pages/StudentLogsPage';
import AdminProtectedRoute from './components/AdminProtectedRoute';
import StudentSessionsPage from './pages/StudentSessionsPage';
import StudentConversationPage from './pages/StudentConversationPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<StudentLogin />} />
        <Route path="/chat" element={<StudentChat />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/admin" element={<AdminLogin />} />
        <Route path="/admin/forgot-password" element={<ForgotPassword audience="admin" />} />
        <Route
          path="/admin/dashboard"
          element={
            <AdminProtectedRoute>
              <AdminDashboard />
            </AdminProtectedRoute>
          }
        />
        <Route
          path="/admin/logs"
          element={
            <AdminProtectedRoute>
              <StudentLogsPage />
            </AdminProtectedRoute>
          }
        />
        <Route
          path="/admin/logs/:studentId"
          element={
            <AdminProtectedRoute>
              <StudentSessionsPage />
            </AdminProtectedRoute>
          }
        />
        <Route
          path="/admin/logs/:studentId/:sessionId"
          element={
            <AdminProtectedRoute>
              <StudentConversationPage />
            </AdminProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
