import { Shield } from 'lucide-react';
import { FC } from 'react';

const Header: FC = () => {
  return (
    <header className="flex h-16 items-center border-b border-gray-200 bg-white px-6 shadow-sm">
      <div className="flex items-center gap-3">
        <Shield className="h-7 w-7 text-indigo-600" />
        <h1 className="text-lg font-semibold text-gray-900">Fraud Detection Guard</h1>
      </div>
    </header>
  );
};

export default Header;
