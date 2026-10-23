# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.7] - 2026-10-23

### Fixed
- Stopped the integration from being locked out by EPB's login rate limits (6 password logins per 15 minutes, 12 per 24 hours). It previously did a full password login whenever the access token expired (every 15 minutes), which hit the daily cap within hours and left the sensors unavailable.
- Fixed the options flow saving the update interval as a `timedelta`, which isn't JSON-serialisable. It's now stored as whole minutes, and existing `timedelta` values are still read.

### Changed
- Logins now use EPB's v2 login endpoint (`/web/api/v2/login/`), which is what epb.com uses and which returns a refresh token.
- Expired access tokens are renewed with the refresh token (`grant_type: REFRESH_TOKEN`), which doesn't count as a password login. A password login only happens when there is no refresh token or EPB rejects it. A rate-limit response (HTTP 429) is never answered with another login attempt.
- Tokens are saved in Home Assistant storage (`.storage/epb.<entry_id>`) so restarts and reloads reuse them. The tokens from the initial login in the config flow are reused for first setup instead of logging in a second time. Stored tokens are deleted when the integration is removed.
- The update interval is capped at 55 minutes because refresh tokens expire after 60 minutes.
- The options flow no longer passes `config_entry` to `OptionsFlow`, which Home Assistant has deprecated. The minimum Home Assistant version is now 2024.11.0.

## [1.0.6] - 2026-05-03

### Fixed
- Fixed inflated Energy Dashboard totals (e.g. multi-MWh spikes) caused by transient API parse failures returning `0.0`, which the `total_increasing` state class interpreted as a meter reset followed by a fresh increment. Missing values now yield `None` so sensors briefly become unavailable instead of synthesizing a reset (#3).
- Fixed `EPBCostSensor` warning: `state_class 'total_increasing' is impossible considering device_class 'monetary'`. Cost sensor now uses `state_class = total`, which is the correct pairing for monetary device classes (#3).
- Removed broad exception swallowing in `get_usage_data` that returned zeros on any error; failures now propagate so the coordinator marks the update failed and Home Assistant preserves the last known value.

## [1.0.4] - 2025-03-11

### Fixed
- Fixed cost sensor unit of measurement from "USD" to "$" to ensure compatibility with Home Assistant statistics

## [1.0.3] - 2025-03-11

### Fixed
- Fixed config flow registration to properly use the Home Assistant decorator pattern

## [1.0.2] - 2025-03-11

### Fixed
- Fixed integration setup issue where Home Assistant couldn't find the setup functions
- Fixed config flow implementation to use the correct class structure
- Fixed sensor implementation to properly access data from the coordinator
- Fixed sensor naming convention to follow the expected pattern
- Fixed GIS ID handling to correctly fetch usage data from the EPB API
- Fixed various type issues and linting errors

## [1.0.1] - 2025-03-09

### Changed
- Simplified project structure by merging the separate API package into the main integration
- Updated package metadata and dependencies

### Fixed
- Fixed package configuration for PyPI publishing

## [1.0.0] - 2025-03-09

### Added
- Initial release of the EPB (Electric Power Board) integration
- Connect to the EPB API to retrieve energy usage data
- Display energy usage and cost as sensors in Home Assistant
- Automatic data refresh at configurable intervals
- Support for multiple EPB accounts
- Configuration flow for easy setup through the UI

### Fixed
- Resolved type checking issues with Home Assistant's typing helpers
- Fixed dependency conflicts in test requirements

[1.0.4]: https://github.com/asachs01/ha-epb/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/asachs01/ha-epb/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/asachs01/ha-epb/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/asachs01/ha-epb/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/asachs01/ha-epb/releases/tag/v1.0.0
