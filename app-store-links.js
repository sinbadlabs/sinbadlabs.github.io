(function () {
  "use strict";

  var defaultStorefront = "us";
  var appPath = "/app/happy-colorpad/id6768400422";
  var locales = navigator.languages && navigator.languages.length
    ? navigator.languages
    : [navigator.language];

  function storefrontForLocale(locale) {
    if (!locale) {
      return undefined;
    }

    var normalizedLocale = locale.replace(/_/g, "-");

    if (typeof Intl.Locale === "function") {
      try {
        var parsedLocale = new Intl.Locale(normalizedLocale);
        var region = parsedLocale.region || parsedLocale.maximize().region;

        if (/^[A-Z]{2}$/.test(region || "")) {
          return region.toLowerCase();
        }
      } catch (_error) {
        // Fall through to the lightweight BCP 47 parser below.
      }
    }

    var parts = normalizedLocale.split("-");
    for (var index = 1; index < parts.length; index += 1) {
      if (/^[A-Za-z]{2}$/.test(parts[index])) {
        return parts[index].toLowerCase();
      }
    }

    return undefined;
  }

  var storefront = storefrontForLocale(locales[0]) || defaultStorefront;

  document.querySelectorAll("[data-app-store-link]").forEach(function (link) {
    link.href = "https://apps.apple.com/" + storefront + appPath;
  });
})();
