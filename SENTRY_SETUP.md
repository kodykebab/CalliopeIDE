# Sentry Monitoring and Error Tracking Setup

This document provides comprehensive setup instructions for Sentry monitoring and error tracking in the CalliopeIDE project.

## Overview

The CalliopeIDE project now includes integrated monitoring and error tracking using Sentry for both frontend (Next.js) and backend (Flask) components. The integration provides:

- **Uncaught exception capture** for both frontend and backend
- **API failure tracking** with detailed context
- **Frontend runtime error monitoring** 
- **PII and sensitive data filtering** to protect user privacy
- **Toggleable monitoring** via environment variables
- **Zero performance impact** when disabled

## Features

### ✅ Backend (Flask) Monitoring
- Automatic exception capture with Flask integration
- API endpoint error tracking
- Database error monitoring 
- Custom error context and filtering
- Environment-based configuration

### ✅ Frontend (Next.js) Monitoring
- React error boundary integration
- API client failure tracking
- Global unhandled promise rejection capture
- Performance monitoring (configurable)
- Source map support for debugging

### ✅ Security & Privacy
- Sensitive data filtering (passwords, tokens, keys)
- PII protection (email masking, data scrubbing)
- No sensitive information in error reports
- Configurable data sanitization

## Installation

### 1. Install Dependencies

Backend dependencies are already included in `requirements.txt`:
```bash
# Install Python dependencies
pip install -r requirements.txt
```

Frontend dependencies are already included in `package.json`:
```bash
# Install Node.js dependencies
npm install
# or
yarn install
```

### 2. Sentry Project Setup

1. **Create a Sentry account** at [sentry.io](https://sentry.io)
2. **Create two projects** in your Sentry organization:
   - One for your **frontend** (Platform: JavaScript/Next.js)
   - One for your **backend** (Platform: Python/Flask)
3. **Get the DSN** for each project from the project settings

### 3. Environment Configuration

Copy the example environment file and configure Sentry:
```bash
cp .env.example .env
```

Edit your `.env` file and set the following variables:

```env
# Backend Monitoring (DISABLED by default)
ENABLE_MONITORING=false
SENTRY_DSN=https://your-backend-sentry-dsn@sentry.io/project-id
APP_VERSION=1.0.0

# Frontend Monitoring (DISABLED by default)  
NEXT_PUBLIC_ENABLE_MONITORING=false
NEXT_PUBLIC_SENTRY_DSN=https://your-frontend-sentry-dsn@sentry.io/project-id
NEXT_PUBLIC_APP_VERSION=1.0.0

# Optional: Sentry organization settings (for source maps)
SENTRY_ORG=your-sentry-org
SENTRY_PROJECT=your-frontend-project-name
```

## Enabling Monitoring

### Development Environment
To enable monitoring in development:

```env
ENABLE_MONITORING=true
NEXT_PUBLIC_ENABLE_MONITORING=true
```

### Production Environment
For production deployment, set the environment variables:

```bash
# Backend
export ENABLE_MONITORING=true
export SENTRY_DSN="your-backend-dsn"

# Frontend  
export NEXT_PUBLIC_ENABLE_MONITORING=true
export NEXT_PUBLIC_SENTRY_DSN="your-frontend-dsn"
```

## Configuration Options

### Backend Configuration

The backend Sentry configuration is managed in `server/utils/sentry_config.py`:

```python
# Key configuration options
traces_sample_rate=0.1      # Sample 10% of transactions
sample_rate=1.0             # Send all errors
send_default_pii=False      # Don't send PII
before_send=filter_function # Custom data filtering
```

### Frontend Configuration

The frontend Sentry configuration is managed in `config/sentry.ts`:

```typescript
// Key configuration options
tracesSampleRate: 0.1,      // Sample 10% of transactions
sampleRate: 1.0,            // Send all errors  
sendDefaultPii: false,      // Don't send PII
beforeSend: filterFunction  // Custom data filtering
```

## Data Privacy & Security

### Automatic Filtering

Both frontend and backend automatically filter sensitive data:

**Filtered Headers:**
- `authorization`
- `cookie`
- `x-api-key` 
- `x-auth-token`

**Filtered Form Data:**
- `password`
- `token`
- `secret`
- `key`
- `auth`

**User Data:**
- Email addresses are partially masked: `em***@domain.com`
- Only essential user fields are included: `id`, `username`, `email`

### Custom Filtering

You can add custom filtering rules by modifying the `before_send` functions in:
- Backend: `server/utils/sentry_config.py`
- Frontend: `config/sentry.ts`

## Usage Examples

### Backend Error Capture

```python
from server.utils.sentry_config import capture_exception_with_context

try:
    # Your code here
    result = risky_operation()
except Exception as e:
    # Capture with additional context
    event_id = capture_exception_with_context(e, 
        endpoint="api_endpoint_name",
        user_id=current_user.id,
        additional_context="custom data"
    )
    return {"error": "Operation failed", "event_id": event_id}
```

### Frontend Error Capture

```typescript
import { captureExceptionWithContext } from '@/config/sentry';

try {
    // Your code here
    const result = await riskyOperation();
} catch (error) {
    // Capture with additional context
    const eventId = captureExceptionWithContext(error, {
        component: 'ComponentName',
        action: 'user_action',
        additionalData: 'custom context'
    });
    console.log(`Error reported: ${eventId}`);
}
```

## Testing the Integration

### 1. Test Backend Error Capture

Add a test route to trigger an error:
```python
@app.route('/test-sentry', methods=['GET'])
def test_sentry():
    if SentryConfig.is_monitoring_enabled():
        raise Exception("Test exception for Sentry")
    return jsonify({"message": "Sentry monitoring disabled"})
```

### 2. Test Frontend Error Capture

Add a test button to trigger an error:
```typescript
const testSentryError = () => {
    throw new Error("Test frontend error for Sentry");
};
```

### 3. Verify in Sentry Dashboard

1. Visit your Sentry project dashboard
2. Check the **Issues** tab for captured errors
3. Verify that sensitive data is properly filtered
4. Confirm error context and stack traces are captured

## Monitoring Performance

### Metrics to Monitor

- **Error Rate**: Percentage of requests resulting in errors
- **Response Time**: API endpoint response times  
- **User Impact**: Number of users affected by errors
- **Error Volume**: Total number of errors over time

### Sentry Features

- **Performance Monitoring**: Track slow API endpoints and page loads
- **Release Tracking**: Monitor error rates across deployments
- **User Feedback**: Collect user feedback on errors
- **Alerts**: Get notified of error spikes or new issues

## Troubleshooting

### Common Issues

1. **"Sentry not initialized" warnings**
   - Verify `ENABLE_MONITORING` and `NEXT_PUBLIC_ENABLE_MONITORING` are set to `true`
   - Check that DSN values are correctly configured

2. **Source maps not uploading**
   - Ensure `SENTRY_ORG` and `SENTRY_PROJECT` are set
   - Verify Sentry auth token has proper permissions

3. **Too many events / Rate limiting**
   - Adjust `sample_rate` and `traces_sample_rate` values
   - Implement additional filtering in `before_send` functions

4. **Sensitive data appearing in reports**
   - Check and update the filtering rules
   - Test with sample data to verify filtering works

### Debug Mode

Enable debug mode in development:

```env
FLASK_ENV=development  # Backend debug mode
NODE_ENV=development   # Frontend debug mode
```

This will show Sentry initialization logs and debug information.

## Best Practices

### 1. Error Context
Always provide meaningful context when capturing errors:
```python
# Good
capture_exception_with_context(e, 
    endpoint="user_registration",
    email_domain=email.split("@")[1],
    step="email_validation"
)

# Avoid
capture_exception(e)  # No context
```

### 2. Rate Limiting
Configure appropriate sampling rates:
- **Development**: High rates for testing (0.5-1.0)
- **Production**: Lower rates to control volume (0.1-0.3)

### 3. Release Tracking
Set version numbers for better error tracking:
```env
APP_VERSION=1.2.3
NEXT_PUBLIC_APP_VERSION=1.2.3  
```

### 4. Custom Tags
Use tags for better error organization:
```python
sentry_sdk.set_tag("component", "auth_system")
sentry_sdk.set_tag("feature", "password_reset")
```

## Production Deployment

### 1. Environment Variables
Ensure all Sentry environment variables are properly configured in your production environment.

### 2. Source Maps  
For Next.js applications, source maps will be automatically uploaded if properly configured.

### 3. Performance Impact
- Error tracking has minimal performance impact
- Performance monitoring should be sampled (10-30%)
- Disable in case of performance issues

### 4. Monitoring
Set up alerts in Sentry for:
- New error types
- Error rate increases  
- Performance degradation
- User impact thresholds

## Security Considerations

1. **Never commit DSN values** to version control
2. **Use environment variables** for all configuration
3. **Regular review filtering rules** to ensure PII protection
4. **Monitor Sentry project access** and permissions
5. **Rotate DSN values** periodically if compromised

## Support & Maintenance

### Regular Tasks
- Review error patterns monthly
- Update filtering rules as needed
- Monitor quota usage and adjust sampling
- Review and resolve critical issues promptly

### Updates
- Keep Sentry SDK versions updated
- Monitor Sentry changelog for new features
- Test updates in staging before production
- Review changes to default filtering behavior

---

For additional help:
- [Sentry Documentation](https://docs.sentry.io/)
- [Sentry Python SDK](https://docs.sentry.io/platforms/python/)
- [Sentry Next.js Integration](https://docs.sentry.io/platforms/javascript/guides/nextjs/)