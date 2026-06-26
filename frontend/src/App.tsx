import { FC, useEffect, useState } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';

import { authApi } from './api/auth';
import { getAccessToken, clearTokens } from './api/client';
import Layout from './components/layout/Layout';
import Alerts from './pages/Alerts';
import Audit from './pages/Audit';
import Investigation from './pages/Investigation';
import Login from './pages/Login';
import Overview from './pages/Overview';
import Register from './pages/Register';
import Rules from './pages/Rules';
import SubmitTransaction from './pages/SubmitTransaction';
import Transactions from './pages/Transactions';
import Verifications from './pages/Verifications';
import { useAuthStore } from './stores/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: FC<ProtectedRouteProps> = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

const App: FC = () => {
  const login = useAuthStore((state) => state.login);
  const logout = useAuthStore((state) => state.logout);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  useEffect(() => {
    const validateToken = async () => {
      const token = getAccessToken();
      if (token) {
        try {
          const user = await authApi.me();
          login(token, user);
        } catch {
          clearTokens();
          logout();
        }
      }
      setIsCheckingAuth(false);
    };

    validateToken();
  }, [login, logout]);

  if (isCheckingAuth) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Overview />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/submit" element={<SubmitTransaction />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/verifications" element={<Verifications />} />
        <Route path="/investigation/:transactionId" element={<Investigation />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="/audit" element={<Audit />} />
      </Route>
    </Routes>
  );
};

export default App;
