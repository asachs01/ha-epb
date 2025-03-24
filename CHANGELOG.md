# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-03-12

### Added
- Added support for handling hourly KWH resets from EPB meters
- Added new Raw Energy sensor to show current hour's usage
- Added hourly accumulation logic to properly track total energy usage

### Changed
- Changed energy sensor state class from TOTAL to TOTAL_INCREASING to better reflect the accumulating nature
- Enhanced the coordinator to detect and handle hourly resets with the 15-minute update interval

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

[1.1.0]: https://github.com/asachs01/ha-epb/compare/v1.0.4...v1.1.0
[1.0.4]: https://github.com/asachs01/ha-epb/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/asachs01/ha-epb/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/asachs01/ha-epb/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/asachs01/ha-epb/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/asachs01/ha-epb/releases/tag/v1.0.0
