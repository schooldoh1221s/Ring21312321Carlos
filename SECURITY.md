# CARLO'S RING security notes

## What is protected

- The site uses a restrictive Content Security Policy in `index.html` and `helper.html`.
- Plugins and embedded objects are disabled with `object-src 'none'`.
- Form submissions and frames are limited to explicitly allowed destinations.
- No anti-DevTools redirects or debugger loops are used.
- External AI credentials must never be placed in client-side HTML or JavaScript.

## Important limitation

This is a static website. Anything shipped to a visitor's browser—including HTML, CSS, JavaScript, catalog data, and public asset URLs—can be viewed, copied, or downloaded. Client-side code cannot be made completely private.

For genuinely private logic or secrets, use a server-side API. Keep API keys, database credentials, moderation logic, and authorization checks on that server. Configure HTTP response headers at the hosting provider as well; an HTML meta CSP is useful defense-in-depth but cannot replace server headers.

## Deployment recommendations

- Enable HTTPS.
- Configure `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy` as HTTP headers.
- Do not commit API keys, tokens, passwords, or private files.
- Review third-party scripts before adding them.
- Use an approved backend for AI requests and rate-limit it.
