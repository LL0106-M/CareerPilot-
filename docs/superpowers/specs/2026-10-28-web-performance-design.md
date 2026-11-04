# CareerPilot Web Performance Design

## Goal

Reduce first-load time over the current public tunnel without changing product behavior or visual composition.

## Design

The frontend keeps the existing three visual assets, but serves WebP variants sized for their largest rendered use: the character at 900 px square, the landscape at its existing dimensions, and the wordmark at 720 px wide. Versioned filenames allow safe immutable caching. Source references move to the versioned WebP files; the original PNG files are removed after visual verification.

The FastAPI application adds gzip response compression for compressible responses above 500 bytes. `SPAStaticFiles` marks `/assets/` responses as public, one-year, immutable resources, while HTML entry points remain `no-cache` so new deployments are discovered immediately. Hashed Vite bundles and explicitly versioned image filenames make this split safe.

React routes load with `React.lazy` behind one shared `Suspense` fallback. Authentication and routing remain in the initial bundle, but page modules—including Framer Motion and page-specific icons—download only when their route is rendered. A guest opening `/login` therefore does not load the authenticated homepage or knowledge pages.

## Verification

Automated tests cover cache headers, gzip, lazy loading at the login route, and optimized asset budgets. The production build must produce multiple route chunks, and public measurements must show compression/cache headers and a lower asset payload.
