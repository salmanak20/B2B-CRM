# B2B CRM Windows desktop build

## 1. Architecture

The Windows client uses Tauri 2 to package the existing Vite frontend. It calls the existing FastAPI API and Supabase-backed authentication and storage services. The browser build remains same-origin at `/api/v1`; desktop builds require an explicit API URL and produce static route files for Tauri's local application origin. No database, business logic, or CRM data is bundled locally. The client is online-only.

## 2. Required development tools

- Windows 10 or 11 x64.
- Node.js 22 and npm; use the committed `package-lock.json` with `npm ci`.
- Rust 1.90.0 and Cargo for the `x86_64-pc-windows-msvc` target. `src-tauri/rust-toolchain.toml` pins this toolchain.
- Visual Studio 2022 Build Tools with the MSVC C++ workload and a Windows SDK.
- Microsoft Edge WebView2 Runtime. Windows 11 includes it; the NSIS installer uses Tauri's WebView2 bootstrap behavior on supported Windows 10 systems.
- Tauri CLI 2.12.4 is installed through the npm lockfile. Tauri downloads or locates NSIS as part of the bundle build.

## 3. Local development

From `stitch_crm_pro_enterprise_suite`, install dependencies and set the API endpoint before starting the Tauri dev window:

```powershell
npm ci
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000/api/v1'
$env:RUSTUP_TOOLCHAIN = '1.90.0'
npm run tauri -- dev
```

The local backend must allow the Vite development origin `http://localhost:5173` in its development CORS configuration. The Vite server binds to loopback. The dev window uses Vite's `/login` route rewrite.

## 4. Environment configuration

`VITE_API_BASE_URL` is public client configuration, not a secret. Desktop builds require an absolute URL ending in `/api/v1`; HTTPS is required except for loopback development. Production builds default to `https://b2-b-crm.vercel.app/api/v1` in CI. No production credentials, Supabase service-role keys, or database credentials are included in the desktop bundle.

Optional `VITE_EXTERNAL_LINK_HOSTS` is a comma-separated list of additional exact hostnames approved for external browser links. Additions must be reviewed before packaging. The compiled Rust command repeats the HTTPS and host checks before calling the system browser.

## 5. Run the desktop app locally

```powershell
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000/api/v1'
npm run tauri -- dev
```

The first screen is the existing CRM login. Platform administration remains at `/platform-admin/login`; server-side authorization and MFA remain authoritative.

## 6. Build the production desktop package

On a configured Windows build machine:

```powershell
$env:VITE_API_BASE_URL = 'https://b2-b-crm.vercel.app/api/v1'
$env:RUSTUP_TOOLCHAIN = '1.90.0'
npm run build
npm run check
npm run desktop:build
npm run check:desktop
npm run tauri -- build --bundles nsis
```

This compiles a production desktop client only. It does not deploy to Vercel, edit production settings, or modify production data.

## 7. Installer output

Tauri writes the versioned installer under:

`stitch_crm_pro_enterprise_suite/src-tauri/target/release/bundle/nsis/`

GitHub Actions copies the NSIS output to `B2B-CRM-Setup.exe`. The native installer includes the B2B CRM icon, per-user installation, Start menu shortcut, desktop shortcut, and normal uninstall entry. Shortcut creation must be confirmed by the Windows install smoke test. The same CI artifact includes the resolved Rust `Cargo.lock` for review.

## 8. Install and uninstall

Run `B2B-CRM-Setup.exe` as the current user; administrator elevation is not configured. Uninstall through Windows Settings → Apps → Installed apps → B2B CRM. Session data is owned by the Tauri WebView profile; uninstall and reinstall lifecycle behavior still needs a Windows smoke test.

## 9. Authentication and password recovery

Login, logout, platform MFA, workspace selection, and authorization continue through the existing API. The client does not store passwords or Supabase tokens and does not assign roles based on email. Password recovery remains on the hosted `/login` website using the current email flow; the desktop app has no deep-link registration, so no Supabase redirect URL change is needed for this implementation. Cookie persistence, refresh, revocation, recovery handoff, and WebView2 third-party-cookie behavior have not yet been verified end to end.

## 10. API connectivity and production CORS prerequisites

The production API URL remains `https://b2-b-crm.vercel.app/api/v1`; no custom domain is used. A desktop WebView uses the secure Tauri origin `https://tauri.localhost` (`useHttpsScheme: true`). Before desktop sign-in can work in production, a separately approved backend configuration change must:

1. Add the exact origin `https://tauri.localhost` to `CORS_ORIGINS`, preserving every existing production origin.
2. Set `SESSION_COOKIE_SAMESITE=none` while retaining `COOKIE_SECURE=true`; the backend now validates that `SameSite=None` cannot be used without secure cookies. This applies to both session and recovery cookies.
3. Verify credentialed CORS preflight and login/logout from the Windows WebView2 client using a non-production test account, including the target machines' cookie policy.

These changes have not been applied. Until then, the desktop build may load but production authentication is not verified and should not be distributed for account use. The Supabase Site URL and hosted `/login` redirect remain as configured; no authentication settings were changed.

The Tauri CSP permits API connections only to the existing production host. If another API host is approved, update the CSP, native external-host policy, and build configuration together, then rebuild and test.

## 11. WebView2 prerequisites

Tauri uses the installed Microsoft Edge WebView2 runtime rather than embedding a separate browser. Windows 11 normally includes WebView2. The NSIS setup uses Tauri's WebView2 bootstrapper for supported Windows 10 machines. The installed-app launch and missing-runtime recovery path still require Windows 10/11 smoke testing.

## 12. Code signing

No approved code-signing certificate or signing key is configured. The workflow produces an unsigned installer; Windows SmartScreen may show an unknown-publisher warning. This package is not signed and is not ready for unrestricted commercial distribution.

## 13. Security considerations

- Tauri exposes no shell, filesystem, SQL, or unrestricted HTTP capability to the frontend.
- The main window is local bundled content; arbitrary remote websites are not loaded into it.
- External destinations are opened in the system browser after HTTPS and exact-host validation in both frontend and Rust.
- API sessions remain server-issued, HttpOnly cookies; production cross-site use requires the separately approved CORS and `SameSite=None; Secure` settings above.
- API authorization, tenant isolation, MFA, suspended-business checks, quotas, and Free Pilot rules stay server-side.
- File downloads use the existing authenticated API endpoint and preserve its authorization checks. Native dialogs and file export behavior still need installed-app verification.
- No auto-updater is configured.

## 14. Known limitations

- Rust, MSVC, and NSIS are unavailable in the current local machine environment; the Windows installer has not been generated locally.
- CI can build the installer, but installation, startup, resizing, WebView2 behavior, and uninstall have not yet been tested on Windows.
- Production desktop authentication is blocked on approved CORS/cookie settings and a safe end-to-end verification.
- There are no approved test credentials for live Super Admin or Business Owner workflows; production identity mapping and role assignment are not part of this work.
- Browser E2E tests do not by themselves verify Tauri session persistence, downloads, external links, or installer behavior.
- Production CRM release remains **NO-GO** pending the separate identity mapping, recovery, backup/restore, and migration prerequisites in `backend/SAAS_RELEASE_BLOCKERS.md` and `backend/SAAS_RECOVERY_PLAN.md`.

## 15. Troubleshooting

- **Desktop build says API is not configured:** set `VITE_API_BASE_URL` to an absolute URL ending in `/api/v1`.
- **Desktop route returns 404:** run `npm run desktop:build` and `npm run check:desktop`; the Vite desktop build emits route aliases used by Tauri.
- **Login request fails in production:** confirm the separately approved exact CORS origin and `SESSION_COOKIE_SAMESITE=none` with `COOKIE_SECURE=true`; verify the API host matches the CSP and the WebView is online.
- **External link is blocked:** allow only the exact HTTPS hostname after review through `VITE_EXTERNAL_LINK_HOSTS`, then rebuild. The Rust command rejects HTTP, non-default ports, and unapproved hosts.
- **NSIS build fails:** install the pinned Rust toolchain, Visual Studio 2022 MSVC workload, and Windows SDK; rerun from the frontend directory.
- **Installer launches but the window is blank:** verify the generated `dist/login.html`, `frontendDist`, CSP, and WebView2 runtime before changing any production settings.

## 16. CI artifact retrieval

The `Windows desktop build` workflow runs on pushes to `feature/windows-desktop-app`, pull requests to `main`, and manual dispatch. Open the successful workflow run in GitHub Actions and download the `B2B-CRM-Windows-x64` artifact. It contains the installer and generated `B2B-CRM-Cargo.lock`, and expires after 14 days. Review and commit the lockfile to `src-tauri/Cargo.lock` before describing later builds as dependency-locked. The workflow uses no production secrets and does not deploy.

## 17. Future release and update requirements

Before general distribution, obtain an approved Windows code-signing certificate, protect its private key in a secure signing service, sign the installer, and verify the signature and timestamp in CI. Any future updater must use signed update metadata, authenticated HTTPS, artifact integrity verification, rollback protection, and a documented key-rotation and recovery plan. Do not add automatic updates until those controls and a release process are approved.
