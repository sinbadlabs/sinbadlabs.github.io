# sinbadlabs.github.io

Static website for [sinbadlabs.com](https://sinbadlabs.com), hosted by GitHub Pages.

## App Store redirects

App Store calls to action use `https://apps.sinbadlabs.com/colorpad`. The
Cloudflare Worker in `workers/app-store-redirect` reads Cloudflare's IP-derived
country code and redirects to the matching App Store storefront. It accepts
only countries in Apple's active storefront list. When the IP country is
unavailable or unsupported, it tries an explicit region from `Accept-Language`
before falling back to the US storefront.

The product page also includes Apple's Smart App Banner for Safari. The Worker
is the fallback used by ordinary links and browsers that do not support the
banner.

Deploy the Worker before publishing website changes that point to its custom
domain. Wrangler requires Node.js 22 or later:

```sh
cd workers/app-store-redirect
npm install
npx wrangler login
npm test
npm run deploy
```

The `apps.sinbadlabs.com` custom domain requires `sinbadlabs.com` to be an
active zone in the Cloudflare account used by Wrangler. Cloudflare creates and
manages the subdomain's DNS record and certificate during deployment.
