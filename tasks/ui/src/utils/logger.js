/**
 * Logger utility for consistent logging across the application.
 *
 * Uses console methods in development, can be replaced with a proper
 * logging service in production (e.g., Sentry, LogRocket).
 */

const isDevelopment = import.meta.env.MODE === 'development';

/**
 * Log an error message.
 * @param {string} message - Error message
 * @param {Error|unknown} error - Error object or additional context
 */
export const logError = (message, error) => {
  if (isDevelopment) {
    // eslint-disable-next-line no-console
    console.error(message, error);
  } else {
    // In production, you might want to send to error tracking service
    // Example: Sentry.captureException(error, { message });
    // eslint-disable-next-line no-console
    console.error(message, error);
  }
};

/**
 * Log a warning message.
 * @param {string} message - Warning message
 * @param {unknown} context - Additional context
 */
export const logWarning = (message, context) => {
  if (isDevelopment) {
    // eslint-disable-next-line no-console
    console.warn(message, context);
  }
};

/**
 * Log an info message (development only).
 * @param {string} message - Info message
 * @param {unknown} context - Additional context
 */
export const logInfo = (message, context) => {
  if (isDevelopment) {
    // eslint-disable-next-line no-console
    console.info(message, context);
  }
};

/**
 * Log a debug message (development only).
 * @param {string} message - Debug message
 * @param {unknown} context - Additional context
 */
export const logDebug = (message, context) => {
  if (isDevelopment) {
    // eslint-disable-next-line no-console
    console.debug(message, context);
  }
};

export default {
  error: logError,
  warning: logWarning,
  info: logInfo,
  debug: logDebug,
};
