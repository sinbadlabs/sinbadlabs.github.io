import assert from "node:assert/strict";
import test from "node:test";

import worker, {
  appStoreUrlForStorefront,
  storefrontForAcceptLanguage,
  storefrontForCountry,
  storefrontForRequest,
} from "../src/index.js";

function request({
  acceptLanguage,
  country,
  countryHeader,
  method = "GET",
  path = "/colorpad",
} = {}) {
  const headers = new Headers();
  if (acceptLanguage !== undefined) {
    headers.set("Accept-Language", acceptLanguage);
  }
  if (countryHeader !== undefined) {
    headers.set("CF-IPCountry", countryHeader);
  }

  return {
    cf: country === undefined ? undefined : { country },
    headers,
    method,
    url: `https://apps.sinbadlabs.com${path}`,
  };
}

test("normalizes Cloudflare country codes for App Store storefronts", () => {
  assert.equal(storefrontForCountry("CN"), "cn");
  assert.equal(storefrontForCountry("gb"), "gb");
});

test("rejects missing and unsupported storefront countries", () => {
  assert.equal(storefrontForCountry(undefined), undefined);
  assert.equal(storefrontForCountry("T1"), undefined);
  assert.equal(storefrontForCountry("XX"), undefined);
  assert.equal(storefrontForCountry("IR"), undefined);
  assert.equal(storefrontForCountry("AQ"), undefined);
});

test("extracts supported explicit regions from Accept-Language", () => {
  assert.equal(storefrontForAcceptLanguage("zh-CN,zh;q=0.9"), "cn");
  assert.equal(storefrontForAcceptLanguage("zh"), undefined);
  assert.equal(storefrontForAcceptLanguage("fa-IR,en-GB;q=0.8"), "gb");
  assert.equal(storefrontForAcceptLanguage("en-US;q=0.7,zh-CN;q=0.9"), "cn");
});

test("uses IP country before language and US as the final fallback", () => {
  assert.equal(
    storefrontForRequest(request({ country: "CN", acceptLanguage: "en-US" })),
    "cn",
  );
  assert.equal(
    storefrontForRequest(request({ country: "T1", acceptLanguage: "zh-CN" })),
    "cn",
  );
  assert.equal(storefrontForRequest(request()), "us");
});

test("uses the Cloudflare country header when request.cf is unavailable", () => {
  assert.equal(storefrontForRequest(request({ countryHeader: "JP" })), "jp");
});

test("builds a storefront-specific ColorPad product URL", () => {
  assert.equal(
    appStoreUrlForStorefront("cn"),
    "https://apps.apple.com/cn/app/happy-colorpad/id6768400422",
  );
});

test("redirects a China request without caching the result", async () => {
  const response = await worker.fetch(request({ country: "CN" }));

  assert.equal(response.status, 302);
  assert.equal(
    response.headers.get("location"),
    "https://apps.apple.com/cn/app/happy-colorpad/id6768400422",
  );
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  assert.equal(response.headers.get("vary"), "Accept-Language, CF-IPCountry");
});

test("supports HEAD requests", async () => {
  const response = await worker.fetch(
    request({ country: "US", method: "HEAD", path: "/colorpad/" }),
  );

  assert.equal(response.status, 302);
  assert.equal(
    response.headers.get("location"),
    "https://apps.apple.com/us/app/happy-colorpad/id6768400422",
  );
});

test("rejects unsupported methods", async () => {
  const response = await worker.fetch(request({ method: "POST" }));

  assert.equal(response.status, 405);
  assert.equal(response.headers.get("allow"), "GET, HEAD");
});

test("does not redirect unknown paths", async () => {
  const response = await worker.fetch(request({ path: "/unknown" }));

  assert.equal(response.status, 404);
});
