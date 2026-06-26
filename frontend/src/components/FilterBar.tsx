import { FC } from 'react';

import { AuditFilters } from '../types';

interface FilterBarProps {
  filters: AuditFilters;
  onFilterChange: (filters: AuditFilters) => void;
}

const FilterBar: FC<FilterBarProps> = ({ filters, onFilterChange }) => {
  const handleDecisionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value as AuditFilters['decision'] | '';
    onFilterChange({
      ...filters,
      decision: value || undefined,
      offset: 0,
    });
  };

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFilterChange({
      ...filters,
      start_date: e.target.value || undefined,
      offset: 0,
    });
  };

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFilterChange({
      ...filters,
      end_date: e.target.value || undefined,
      offset: 0,
    });
  };

  return (
    <div className="flex flex-wrap items-end gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-1">
        <label htmlFor="decision-filter" className="text-xs font-medium text-gray-500">
          Decision
        </label>
        <select
          id="decision-filter"
          value={filters.decision || ''}
          onChange={handleDecisionChange}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="">All</option>
          <option value="approve">Approve</option>
          <option value="verify">Verify</option>
          <option value="block">Block</option>
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="start-date" className="text-xs font-medium text-gray-500">
          Start Date
        </label>
        <input
          id="start-date"
          type="date"
          value={filters.start_date || ''}
          onChange={handleStartDateChange}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="end-date" className="text-xs font-medium text-gray-500">
          End Date
        </label>
        <input
          id="end-date"
          type="date"
          value={filters.end_date || ''}
          onChange={handleEndDateChange}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>
    </div>
  );
};

export default FilterBar;
