import React from 'react';
import { Spinner } from '@heroui/react';
import { cn } from '@/lib/utils';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  label?: string;
  fullScreen?: boolean;
}

export function LoadingSpinner({ 
  size = 'md', 
  className, 
  label = 'Loading...',
  fullScreen = false 
}: LoadingSpinnerProps) {
  const spinnerContent = (
    <div className={cn(
      'flex flex-col items-center justify-center gap-2',
      fullScreen && 'fixed inset-0 bg-black/60 backdrop-blur-sm z-50',
      className
    )}>
      <Spinner 
        size={size} 
        color="primary"
        classNames={{
          circle1: "border-b-[#9FEF00]",
          circle2: "border-b-[#9FEF00]",
        }}
      />
      {label && (
        <p className="text-sm text-white/70 animate-pulse">
          {label}
        </p>
      )}
    </div>
  );

  return spinnerContent;
}

interface ButtonLoadingProps {
  isLoading: boolean;
  children: React.ReactNode;
  loadingText?: string;
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
}

export function ButtonWithLoading({ 
  isLoading, 
  children, 
  loadingText = 'Loading...',
  disabled,
  onClick,
  className 
}: ButtonLoadingProps) {
  return (
    <button
      onClick={onClick}
      disabled={isLoading || disabled}
      className={cn(
        'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md',
        'bg-[#9FEF00] text-black font-medium transition-all duration-200',
        'hover:bg-[#9FEF00]/80 focus:outline-none focus:ring-2 focus:ring-[#9FEF00]/50',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        isLoading && 'cursor-wait',
        className
      )}
    >
      {isLoading && (
        <Spinner 
          size="sm"
          classNames={{
            circle1: "border-b-black",
            circle2: "border-b-black",
          }}
        />
      )}
      <span>{isLoading ? loadingText : children}</span>
    </button>
  );
}