import config from "./config.js";

// The SDK comes from a CDN, so a content blocker can leave it undefined.
if (config.sentry && window.Sentry) {
  const { Sentry } = window;
  const { dsn, app_name, server_name } = config.sentry;
  Sentry.init({ dsn });
  // SENTRY_SDK_URL picks the version: setTags came in 5 and configureScope went
  // in 8. A throw here would stop every module main.js imports after this one.
  if (Sentry.setTags) {
    Sentry.setTags({ app_name, server_name });
  } else {
    Sentry.configureScope((scope) => {
      scope.setTag("app_name", app_name);
      scope.setTag("server_name", server_name);
    });
  }
}
