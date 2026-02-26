import dynamic from 'next/dynamic';
import { ErrorBoundary } from '../components/error-boundary';
import { ToastContainer } from '../components/ui/error-alert';

// Dynamically import the test runner to avoid SSR issues
const ErrorHandlingTestRunner = dynamic(
  () => import('../components/error-test-runner'),
  { 
    ssr: false,
    loading: () => (
      <div className="min-h-screen bg-[#0D1117] text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#9FEF00] mx-auto mb-4"></div>
          <p>Loading Error Handling Test Suite...</p>
        </div>
      </div>
    )
  }
);

export default function TestPage() {
  return (
    <ErrorBoundary>
      <ErrorHandlingTestRunner />
      <ToastContainer />
    </ErrorBoundary>
  );
}