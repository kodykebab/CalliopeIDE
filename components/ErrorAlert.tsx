import React, { useState, useEffect } from 'react';
import { X, AlertCircle, CheckCircle, Info, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface AlertProps {
  variant?: 'error' | 'success' | 'warning' | 'info';
  title?: string;
  message: string;
  closable?: boolean;
  className?: string;
  onClose?: () => void;
}

export interface ToastProps extends AlertProps {
  id: string;
  duration?: number;
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left' | 'top-center';
}

/**
 * Error Alert component for inline error display
 */
export const ErrorAlert: React.FC<AlertProps> = ({
  variant = 'error',
  title,
  message,
  closable = true,
  className,
  onClose
}) => {
  const [isVisible, setIsVisible] = useState(true);

  const variantConfig: Record<NonNullable<AlertProps['variant']>, {
    icon: React.ComponentType<any>;
    bgClass: string;
    iconClass: string;
    textClass: string;
    titleClass: string;
  }> = {
    error: {
      icon: AlertCircle,
      bgClass: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800',
      iconClass: 'text-red-500 dark:text-red-400',
      textClass: 'text-red-800 dark:text-red-200',
      titleClass: 'text-red-900 dark:text-red-100'
    },
    success: {
      icon: CheckCircle,
      bgClass: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
      iconClass: 'text-green-500 dark:text-green-400',
      textClass: 'text-green-800 dark:text-green-200',
      titleClass: 'text-green-900 dark:text-green-100'
    },
    warning: {
      icon: AlertTriangle,
      bgClass: 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800',
      iconClass: 'text-yellow-500 dark:text-yellow-400',
      textClass: 'text-yellow-800 dark:text-yellow-200',
      titleClass: 'text-yellow-900 dark:text-yellow-100'
    },
    info: {
      icon: Info,
      bgClass: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
      iconClass: 'text-blue-500 dark:text-blue-400',
      textClass: 'text-blue-800 dark:text-blue-200',
      titleClass: 'text-blue-900 dark:text-blue-100'
    }
  };

  const config = variantConfig[variant || 'error'];
  const Icon = config.icon;

  const handleClose = () => {
    setIsVisible(false);
    onClose?.();
  };

  if (!isVisible) return null;

  return (
    <div
      className={cn(
        'rounded-lg border p-4 shadow-sm',
        config.bgClass,
        className
      )}
      role="alert"
    >
      <div className="flex items-start">
        <div className="flex-shrink-0">
          <Icon className={cn('h-5 w-5', config.iconClass)} />
        </div>
        <div className="ml-3 flex-1">
          {title && (
            <h3 className={cn('text-sm font-medium mb-1', config.titleClass)}>
              {title}
            </h3>
          )}
          <p className={cn('text-sm', config.textClass)}>
            {message}
          </p>
        </div>
        {closable && (
          <div className="ml-auto pl-3">
            <button
              type="button"
              className={cn(
                'inline-flex rounded-md p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800',
                config.textClass
              )}
              onClick={handleClose}
              aria-label="Close alert"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Toast notification system
 */
class ToastManager {
  private toasts: ToastProps[] = [];
  private listeners: ((toasts: ToastProps[]) => void)[] = [];

  subscribe(listener: (toasts: ToastProps[]) => void) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify() {
    this.listeners.forEach(listener => listener([...this.toasts]));
  }

  show(toast: Omit<ToastProps, 'id'>) {
    const id = Math.random().toString(36).substr(2, 9);
    const newToast: ToastProps = {
      ...toast,
      id,
      duration: toast.duration ?? 5000,
      position: toast.position ?? 'top-right'
    };

    this.toasts.push(newToast);
    this.notify();

    // Auto-remove after duration
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        this.remove(id);
      }, newToast.duration);
    }

    return id;
  }

  remove(id: string) {
    this.toasts = this.toasts.filter(toast => toast.id !== id);
    this.notify();
  }

  clear() {
    this.toasts = [];
    this.notify();
  }

  // Convenience methods
  error(message: string, options?: Partial<ToastProps>) {
    return this.show({ ...options, variant: 'error', message });
  }

  success(message: string, options?: Partial<ToastProps>) {
    return this.show({ ...options, variant: 'success', message });
  }

  warning(message: string, options?: Partial<ToastProps>) {
    return this.show({ ...options, variant: 'warning', message });
  }

  info(message: string, options?: Partial<ToastProps>) {
    return this.show({ ...options, variant: 'info', message });
  }
}

export const toast = new ToastManager();

/**
 * Toast container component
 */
export const ToastContainer: React.FC<{
  position?: ToastProps['position'];
  className?: string;
}> = ({ position = 'top-right', className }) => {
  const [toasts, setToasts] = useState<ToastProps[]>([]);

  useEffect(() => {
    const unsubscribe = toast.subscribe(setToasts);
    return unsubscribe;
  }, []);

  const positionClasses = {
    'top-right': 'top-4 right-4',
    'top-left': 'top-4 left-4',
    'bottom-right': 'bottom-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'top-center': 'top-4 left-1/2 transform -translate-x-1/2'
  };

  const filteredToasts = toasts.filter(t => t.position === position);

  if (filteredToasts.length === 0) return null;

  return (
    <div
      className={cn(
        'fixed z-50 flex flex-col space-y-2 w-full max-w-sm pointer-events-none',
        positionClasses[position],
        className
      )}
    >
      {filteredToasts.map(toastItem => (
        <ToastItem
          key={toastItem.id}
          toast={toastItem}
          onClose={() => {
            if (toastItem.id && typeof window !== 'undefined' && (window as any).toastManager) {
              (window as any).toastManager.remove(toastItem.id);
            }
          }}
        />
      ))}
    </div>
  );
};

/**
 * Individual toast item component
 */
const ToastItem: React.FC<{
  toast: ToastProps;
  onClose: () => void;
}> = ({ toast, onClose }) => {
  const [isVisible, setIsVisible] = useState(true);
  const [isLeaving, setIsLeaving] = useState(false);

  const handleClose = () => {
    setIsLeaving(true);
    setTimeout(() => {
      setIsVisible(false);
      onClose();
    }, 150); // Animation duration
  };

  useEffect(() => {
    if (toast.duration && toast.duration > 0) {
      const timer = setTimeout(handleClose, toast.duration);
      return () => clearTimeout(timer);
    }
  }, [toast.duration]);

  if (!isVisible) return null;

  return (
    <div
      className={cn(
        'pointer-events-auto transform transition-all duration-150',
        isLeaving 
          ? 'translate-x-full opacity-0 scale-95' 
          : 'translate-x-0 opacity-100 scale-100'
      )}
    >
      <ErrorAlert
        {...toast}
        onClose={handleClose}
        className="shadow-lg backdrop-blur-sm"
      />
    </div>
  );
};

// Make toast manager globally available
if (typeof window !== 'undefined') {
  (window as any).toastManager = toast;
}

/**
 * React hook for using toasts
 */
export const useToast = () => {
  return {
    show: toast.show.bind(toast),
    error: toast.error.bind(toast),
    success: toast.success.bind(toast),
    warning: toast.warning.bind(toast),
    info: toast.info.bind(toast),
    remove: toast.remove.bind(toast),
    clear: toast.clear.bind(toast)
  };
};

export default ErrorAlert;