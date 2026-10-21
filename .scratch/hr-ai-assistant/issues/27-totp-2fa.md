# 27: TOTP 2FA (optional)

**What to build:** Any user can optionally enable TOTP two-factor auth on their own login. After enabling, login requires password plus a current code; the password-reset recovery path still works. Small, self-contained slice on the auth skeleton. (Spec §10 Auth.)

**Blocked by:** 10 (Org & auth walking skeleton).

**Status:** ready-for-agent

- [ ] Enable flow with QR/secret provisioning; disable with password confirmation
- [ ] Enabled users must supply a valid TOTP code at login, alongside the password
- [ ] Password reset remains a working recovery path; cookie sessions behave sensibly with 2FA on
