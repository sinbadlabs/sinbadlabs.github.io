const DEFAULT_STOREFRONT = "us";
const COLORPAD_PATH = "/app/happy-colorpad/id6768400422";
const COLORPAD_ROUTES = new Set(["/colorpad", "/colorpad/"]);

// Active territories listed by Apple as of 2026-09-16:
// https://developer.apple.com/help/app-store-connect/reference/app-information/app-store-localizations
const APPLE_STOREFRONTS = new Set(
  (
    "AF AL DZ AO AI AG AR AM AU AT AZ BS BH BB BY BE BZ BJ BM BT BO BA BW " +
    "BR VG BN BG BF KH CM CA CV KY TD CL CN CO CD CG CR CI HR CY CZ DK DM " +
    "DO EC EG SV EE SZ FJ FI FR GA GM GE DE GH GR GD GT GW GY HN HK HU IS " +
    "IN ID IQ IE IL IT JM JP JO KZ KE XK KW KG LA LV LB LR LY LT LU MO MG " +
    "MW MY MV ML MT MR MU MX FM MD MN ME MS MA MZ MM NA NR NP NL NZ NI NE " +
    "NG MK NO OM PK PW PA PG PY PE PH PL PT QA KR RO RU RW ST SA SN RS SC " +
    "SL SG SK SI SB ZA ES LK KN LC VC SR SE CH TW TJ TZ TH TO TT TN TR TM " +
    "TC UG UA AE GB US UY UZ VU VE VN YE ZM ZW"
  ).split(" "),
);

export function storefrontForCountry(country) {
  if (typeof country !== "string") {
    return undefined;
  }

  const normalizedCountry = country.toUpperCase();
  if (!APPLE_STOREFRONTS.has(normalizedCountry)) {
    return undefined;
  }

  return normalizedCountry.toLowerCase();
}

export function storefrontForAcceptLanguage(acceptLanguage) {
  if (typeof acceptLanguage !== "string") {
    return undefined;
  }

  const candidates = acceptLanguage
    .split(",")
    .slice(0, 20)
    .map((entry, index) => {
      const [languageTag, ...parameters] = entry.trim().split(";");
      const qualityParameter = parameters.find((parameter) =>
        parameter.trim().toLowerCase().startsWith("q="),
      );
      const parsedQuality = qualityParameter
        ? Number.parseFloat(qualityParameter.trim().slice(2))
        : 1;
      const quality = Number.isFinite(parsedQuality) ? parsedQuality : 0;

      if (!languageTag || languageTag === "*" || quality <= 0) {
        return undefined;
      }

      try {
        const region = new Intl.Locale(languageTag.replace(/_/g, "-")).region;
        const storefront = storefrontForCountry(region);
        return storefront ? { storefront, quality, index } : undefined;
      } catch (_error) {
        return undefined;
      }
    })
    .filter(Boolean)
    .sort((left, right) => right.quality - left.quality || left.index - right.index);

  return candidates[0]?.storefront;
}

export function storefrontForRequest(request) {
  const country = request.cf?.country ?? request.headers.get("CF-IPCountry");
  return (
    storefrontForCountry(country) ??
    storefrontForAcceptLanguage(request.headers.get("Accept-Language")) ??
    DEFAULT_STOREFRONT
  );
}

export function appStoreUrlForStorefront(storefront) {
  return `https://apps.apple.com/${storefront}${COLORPAD_PATH}`;
}

function redirectToAppStore(request) {
  return new Response(null, {
    status: 302,
    headers: {
      "Cache-Control": "private, no-store",
      Location: appStoreUrlForStorefront(storefrontForRequest(request)),
      Vary: "Accept-Language, CF-IPCountry",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export default {
  fetch(request) {
    const url = new URL(request.url);

    if (!COLORPAD_ROUTES.has(url.pathname)) {
      return new Response("Not found", { status: 404 });
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", {
        status: 405,
        headers: { Allow: "GET, HEAD" },
      });
    }

    return redirectToAppStore(request);
  },
};
