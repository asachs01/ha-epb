# EPB Integration for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

<img src="logo.png" alt="EPB Company Logo" width="250" height="137">

Home Assistant integration for EPB (Electric Power Board) smart meter data.

## Features

- Real-time energy usage monitoring
- Cost tracking
- Multiple account support
- Configurable update intervals

## Installation

### HACS (Recommended)

1. Install [HACS](https://hacs.xyz/)
2. Go to HACS > Integrations
3. Click on the 3 dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL
6. Select "Integration" as the category
7. Click "ADD"
8. Search for "EPB"
9. Click "INSTALL"
10. Restart Home Assistant

### Manual

1. Copy the `custom_components/epb` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings > Devices & Services
2. Click "ADD INTEGRATION"
3. Search for "EPB"
4. Enter your EPB credentials
5. Configure update interval (optional)

## Sensors

This integration provides the following sensors for each EPB account:

### Month-to-Date Sensors (for Energy Dashboard)
- **EPB Energy** (kWh) - Cumulative month-to-date energy usage
- **EPB Cost** ($) - Cumulative month-to-date energy cost

### Daily Sensors (for dashboard display)
- **EPB Daily Energy** (kWh) - Today's energy usage
- **EPB Daily Cost** ($) - Today's cost

Each sensor includes additional attributes:
- Account ID

## Energy Dashboard Setup

To use this integration with Home Assistant's Energy Dashboard:

1. Go to **Settings → Dashboards → Energy**
2. Under **Electricity grid**, click **Add consumption**
3. Select **EPB Energy** (the month-to-date sensor)
4. Optionally, configure cost tracking with **EPB Cost**

> **Important:** Only use the month-to-date sensors (EPB Energy/Cost) in the Energy Dashboard. The daily sensors reset each day and should only be used for informational display on regular dashboards.

## Contributing

This is an active open-source project. Feel free to contribute by:

1. Reporting bugs
2. Suggesting enhancements
3. Creating pull requests

## License

This project is licensed under MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

A HUGE thank you to [bradwick](https://github.com/bradwick) for the inspiration for the project and for his Nodered flow that kicked this off.

---

[releases-shield]: https://img.shields.io/github/release/asachs01/ha-epb.svg?style=for-the-badge
[releases]: https://github.com/asachs01/ha-epb/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/asachs01/ha-epb.svg?style=for-the-badge
[commits]: https://github.com/asachs01/ha-epb/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/asachs01/ha-epb.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40asachs01-blue.svg?style=for-the-badge
[user_profile]: https://github.com/asachs01
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/aaronsachs
