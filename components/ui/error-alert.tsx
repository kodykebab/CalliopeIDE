import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, AlertCircle, CheckCircle, Info, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ApiError } from '@/lib/error-handler';

export type ToastType = 'error' | 'success' | 'info' | 'warning';

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ErrorAlertProps {
  error: ApiError | null;
  onDismiss?: () => void;
  className?: string;
  showIcon?: boolean;
}

// Global toast state management
let toastId = 0;
const toastSubscribers: ((toasts: Toast[]) => void)[] = [];
let toasts: Toast[] = [];

function notifySubscribers() {
  toastSubscribers.forEach(callback => callback([...toasts]));
}

export function addToast(toast: Omit<Toast, 'id'>) {
  const newToast: Toast = {
    ...toast,
    id: `toast-${++toastId}`,
    duration: toast.duration ?? 5000,
  };
  
  toasts.push(newToast);
  notifySubscribers();

  // Auto-remove toast after duration
  if (newToast.duration > 0) {
    setTimeout(() => {
      removeToast(newToast.id);
    }, newToast.duration);
  }

  return newToast.id;
}

export function removeToast(id: string) {
  toasts = toasts.filter(toast => toast.id !== id);
  notifySubscribers();
}

export function showErrorToast(error: ApiError, title = 'Error') {
  return addToast({
    type: 'error',
    title,
    description: error.message,
    duration: 7000, // Longer duration for errors
  });
}

export function showSuccessToast(message: string, title = 'Success') {
  return addToast({
    type: 'success',
    title,
    description: message,
    duration: 3000,
  });
}

export function showInfoToast(message: string, title = 'Info') {
  return addToast({
    type: 'info',
    title,
    description: message,
    duration: 4000,
  });
}

export function showWarningToast(message: string, title = 'Warning') {
  return addToast({
    type: 'warning',
    title,
    description: message,
    duration: 5000,
  });
}

// Error Alert Component
export function ErrorAlert({ 
  error, 
  onDismiss, 
  className, 
  showIcon = true 
}: ErrorAlertProps) {
  if (!error) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg border',
        'bg-red-950/30 border-red-500/30 text-red-200',
        className
      )}
    >
      {showIcon && (
        <AlertCircle className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" />
      )}
      
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-red-200">
          {error.message}
        </p>
        {error.code && (
          <p className="text-xs text-red-300/70 mt-1">
            Error code: {error.code}
          </p>
        )}
      </div>

      {onDismiss && (
        <button
          onClick={onDismiss}
          className="flex-shrink-0 text-red-300 hover:text-red-200 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </motion.div>
  );
}

// Toast Component
function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: string) => void }) {
  const icons = {
    error: AlertCircle,
    success: CheckCircle,
    info: Info,
    warning: AlertTriangle,
  };

  const styles = {
    error: 'bg-red-950/90 border-red-500/50 text-red-100',
    success: 'bg-green-950/90 border-green-500/50 text-green-100',
    info: 'bg-blue-950/90 border-blue-500/50 text-blue-100',
    warning: 'bg-yellow-950/90 border-yellow-500/50 text-yellow-100',
  };

  const iconStyles = {
    error: 'text-red-400',
    success: 'text-green-400',
    info: 'text-blue-400',
    warning: 'text-yellow-400',
  };

  const Icon = icons[toast.type];

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 300, scale: 0.3 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 300, scale: 0.5 }}
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg border backdrop-blur-sm',
        'min-w-[320px] max-w-[420px] shadow-lg',
        styles[toast.type]
      )}
    >
      <Icon className={cn('h-5 w-5 flex-shrink-0 mt-0.5', iconStyles[toast.type])} />
      
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">
          {toast.title}
        </p>
        {toast.description && (
          <p className="text-xs opacity-90 mt-1">
            {toast.description}
          </p>
        )}
        {toast.action && (
          <button
            onClick={toast.action.onClick}
            className="text-xs underline mt-2 hover:no-underline transition-all"
          >
            {toast.action.label}
          </button>
        )}
      </div>

      <button
        onClick={() => onRemove(toast.id)}
        className="flex-shrink-0 opacity-70 hover:opacity-100 transition-opacity"
      >
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
}

// Toast Container Component
export function ToastContainer() {
  const [currentToasts, setCurrentToasts] = useState<Toast[]>([]);

  useEffect(() => {
    toastSubscribers.push(setCurrentToasts);
    return () => {
      const index = toastSubscribers.indexOf(setCurrentToasts);
      if (index > -1) {
        toastSubscribers.splice(index, 1);
      }
    };
  }, []);

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      <AnimatePresence mode="popLayout">
        {currentToasts.map((toast) => (
          <ToastItem
            key={toast.id}
            toast={toast}
            onRemove={removeToast}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}