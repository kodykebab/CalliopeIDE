import React from 'react';
import { cn } from '@/lib/utils';

export interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'default' | 'primary' | 'secondary';
  className?: string;
  text?: string;
  show?: boolean;
}

/**
 * Loading spinner component with consistent HeroUI styling
 */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  variant = 'default',
  className,
  text,
  show = true
}) => {
  if (!show) return null;

  const sizeClasses: Record<NonNullable<LoadingSpinnerProps['size']>, string> = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6', 
    lg: 'h-8 w-8',
    xl: 'h-12 w-12'
  };

  const variantClasses: Record<NonNullable<LoadingSpinnerProps['variant']>, string> = {
    default: 'text-gray-400',
    primary: 'text-primary',
    secondary: 'text-secondary'
  };

  const textSizeClasses: Record<NonNullable<LoadingSpinnerProps['size']>, string> = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
    xl: 'text-xl'
  };

  return (
    <div className={cn(
      'flex items-center justify-center gap-3',
      className
    )}>
      <div
        className={cn(
          'animate-spin rounded-full border-2 border-transparent border-t-current',
          sizeClasses[size],
          variantClasses[variant]
        )}
        role="status"
        aria-label={text || 'Loading'}
      />
      {text && (
        <span className={cn(
          'animate-pulse',
          textSizeClasses[size],
          variantClasses[variant]
        )}>
          {text}
        </span>
      )}
    </div>
  );
};

/**
 * Inline loading spinner for buttons and small spaces
 */
export const InlineSpinner: React.FC<{
  size?: 'sm' | 'md';
  className?: string;
}> = ({ size = 'sm', className }) => {
  const sizeClasses: Record<'sm' | 'md', string> = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4'
  };

  return (
    <div
      className={cn(
        'animate-spin rounded-full border border-transparent border-t-current inline-block',
        sizeClasses[size],
        className
      )}
      role="status"
      aria-label="Loading"
    />
  );
};

/**
 * Full page loading overlay
 */
export const LoadingOverlay: React.FC<{
  show: boolean;
  text?: string;
  className?: string;
}> = ({ show, text, className }) => {
  if (!show) return null;

  return (
    <div className={cn(
      'fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm',
      className
    )}>
      <div className="bg-background/80 backdrop-blur-md border border-white/10 rounded-lg p-6 shadow-lg">
        <LoadingSpinner 
          size="lg" 
          text={text || 'Loading...'}
          className="text-white"
        />
      </div>
    </div>
  );
};

/**
 * Loading skeleton for cards and content
 */
export const LoadingSkeleton: React.FC<{
  lines?: number;
  className?: string;
}> = ({ lines = 3, className }) => {
  return (
    <div className={cn('animate-pulse', className)}>
      {Array.from({ length: lines }, (_, i) => (
        <div 
          key={i}
          className={cn(
            'bg-gray-300 dark:bg-gray-600 rounded',
            i === 0 ? 'h-4 mb-4' : 'h-3 mb-3',
            i === lines - 1 ? 'w-3/4' : 'w-full'
          )}
        />
      ))}
    </div>
  );
};

/**
 * Loading state for lists
 */
export const LoadingList: React.FC<{
  items?: number;
  className?: string;
}> = ({ items = 3, className }) => {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: items }, (_, i) => (
        <div key={i} className="animate-pulse flex items-center space-x-4">
          <div className="rounded-full bg-gray-300 dark:bg-gray-600 h-10 w-10" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-gray-300 dark:bg-gray-600 rounded w-3/4" />
            <div className="h-3 bg-gray-300 dark:bg-gray-600 rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
};

export default LoadingSpinner;