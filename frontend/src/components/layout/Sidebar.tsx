import { Home, List, Bell, ShieldCheck, Gavel, FileText, LogOut, PlusCircle } from 'lucide-react';
import { FC } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';

import { clearTokens } from '../../api/client';
import { useAuthStore } from '../../stores/authStore';

const navItems = [
  { to: '/', label: 'Overview', icon: Home },
  { to: '/transactions', label: 'Transactions', icon: List },
  { to: '/submit', label: 'Submit Transaction', icon: PlusCircle },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/verifications', label: 'Verifications', icon: ShieldCheck },
  { to: '/rules', label: 'Rules', icon: Gavel },
  { to: '/audit', label: 'Audit Log', icon: FileText },
];

const Sidebar: FC = () => {
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    clearTokens();
    logout();
    navigate('/login');
  };

  return (
    <aside className="flex w-64 flex-col border-r border-gray-200 bg-white">
      <nav className="flex-1 p-4">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                  }`
                }
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="border-t border-gray-200 p-4">
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 hover:text-gray-900"
        >
          <LogOut className="h-5 w-5" />
          Logout
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
