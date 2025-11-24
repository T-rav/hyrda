# Health UI Testing Guide

The health dashboard includes built-in testing capabilities to simulate different service states without needing to actually configure services.

## Test Mode Usage

Add `?test=true` to the URL to enable test mode:
```
http://localhost:8080/ui?test=true
```

## Test Scenarios

Add `&scenario=<name>` to test specific states:

### All Healthy
```
http://localhost:8080/ui?test=true&scenario=All%20Healthy
```
- All services running perfectly
- Active conversations: 3
- Cache: 45.2MB used
- Langfuse: Connected
- Metrics: Prometheus enabled

### Mixed Status  
```
http://localhost:8080/ui?test=true&scenario=Mixed%20Status
```
- LLM API: Healthy
- Cache: Disabled
- Langfuse: Configuration error
- Metrics: Working
- Missing environment variables

### All Offline
```
http://localhost:8080/ui?test=true&scenario=All%20Offline
```
- All services failing
- Connection errors
- Missing packages
- Configuration issues

### Loading State
```
http://localhost:8080/ui?test=true&scenario=Loading%20State
```
- Shows loading spinner indefinitely
- Tests loading UI components

### Network Error
```
http://localhost:8080/ui?test=true&scenario=Network%20Error
```
- Simulates API fetch failures
- Tests error handling and retry functionality

## Testing Different Components

### Status Cards
- **Healthy**: Green with checkmark
- **Unhealthy**: Red with X mark  
- **Disabled**: Orange with warning
- **Unknown**: Gray with question mark

### Metrics Cards
- Show when services are healthy
- Display actual values (conversations, memory, uptime)
- Include trend indicators when available

### Error States
- Network errors with retry button
- Service-specific error messages
- Configuration problems with helpful hints

### Loading States
- Spinner animation
- Graceful loading without flickering
- Partial data display during refresh

## Real vs Test Data

- **Real mode**: Fetches from `/api/*` endpoints
- **Test mode**: Uses predefined mock data
- **Mixed mode**: Can simulate partial failures
- **Development**: Error boundary shows stack traces

## UI Features Tested

✅ **Component Organization**: Modular, reusable components  
✅ **Error Handling**: Network errors, API failures, React errors  
✅ **Loading States**: Initial load, refresh, partial updates  
✅ **Responsive Design**: Mobile and desktop layouts  
✅ **Real-time Updates**: Auto-refresh every 10 seconds  
✅ **Data Validation**: Handles missing/malformed API responses  
✅ **User Feedback**: Clear status messages and retry options  

## Development Testing

1. **Component Isolation**: Each component can be tested independently
2. **Hook Testing**: `useHealthData` handles all data fetching logic
3. **Utility Testing**: Helper functions for status formatting
4. **Error Boundaries**: Catch and handle React component errors
5. **Mock Data**: Realistic test scenarios without backend setup

## Production Readiness

The refactored UI includes:
- **Error recovery**: Graceful handling of API failures
- **Performance optimization**: Efficient data fetching and caching
- **Accessibility**: Proper ARIA labels and semantic HTML
- **Browser compatibility**: Works across modern browsers
- **Mobile responsiveness**: Clean layout on all screen sizes

Use test mode during development to verify all UI states work correctly before deploying to production.
