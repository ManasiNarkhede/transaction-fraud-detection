import { Info } from 'lucide-react';
import { FC, useId } from 'react';

interface InfoTooltipProps {
  text: string;
}

/** Small "i" icon that reveals field help on hover or keyboard focus. */
export const InfoTooltip: FC<InfoTooltipProps> = ({ text }) => {
  const tooltipId = useId();

  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        tabIndex={0}
        aria-describedby={tooltipId}
        aria-label="Field help"
        className="rounded-full p-0.5 text-gray-400 hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
      >
        <Info className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
      <span
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-0 z-50 mb-2 w-80 max-w-[calc(100vw-2rem)] rounded-md bg-gray-900 px-3 py-2 text-left text-xs font-normal leading-snug text-white opacity-0 shadow-lg transition-opacity break-words group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
      >
        {text}
        <span className="absolute left-3 top-full border-4 border-transparent border-t-gray-900" />
      </span>
    </span>
  );
};

interface LabelWithTooltipProps {
  htmlFor?: string;
  label: string;
  tooltip: string;
  required?: boolean;
  className?: string;
}

export const LabelWithTooltip: FC<LabelWithTooltipProps> = ({
  htmlFor,
  label,
  tooltip,
  required,
  className = 'block text-xs font-medium text-gray-700 mb-1',
}) => (
  <label htmlFor={htmlFor} className={`${className} flex items-center gap-0.5`}>
    <span>
      {label}
      {required && <span className="text-red-500"> *</span>}
    </span>
    <InfoTooltip text={tooltip} />
  </label>
);
