# Foursquare Placemaker Telegram Bot 🗺️🤖

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-✓-blue.svg)](https://core.telegram.org/bots/api)

A Telegram bot for the Foursquare Placemaker community that enables users to contribute to the global places database directly from their mobile devices.

![Foursquare Placemaker Bot Banner](https://your-image-url-here.png)

## 🌟 About Foursquare Placemakers

> "Placemakers are the dedicated, passionate members of our global open source community who contribute to our shared understanding of places around the world. Welcome to our community of builders, developers, and local experts who help others unlock the best experiences, anywhere in the world."

This bot makes the process of adding and updating place data more accessible to the Placemaker community, allowing contributions from anywhere using Telegram.

## ✨ Features

- **Location-Based Entry**: Start by sharing your current location to add nearby places
- **Guided Place Submission**: Step-by-step process for complete place information
- **Category Selection**: Choose from common place categories or enter custom ones
- **Rich Place Attributes**: Add detailed information including:
  - Contact information (phone, website, email)
  - Operating hours
  - Chain status
  - Amenities (WiFi, parking, outdoor seating, etc.)
- **Photo Uploads**: Submit up to 3 photos of the place (storefront, interior, features)
- **Foursquare Map Integration**: Explore existing Foursquare location data through an embedded web app
- **Conversational Interface**: User-friendly keyboard buttons and inline options

## 🌆 Map Integration Web-App

The Mini App within the Telegram bot is served by [Fused](https://www.fused.io/):
1. Foursquare Location Data [UDF](https://github.com/fusedio/udfs/tree/main/public/Foursquare_Open_Source_Places)



## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- A Telegram account
- A Telegram Bot Token from [@BotFather](https://t.me/botfather)

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/foursquare-placemaker-bot.git
   cd FSQ_Placemaker_Bot
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Replace the placeholder token in the code with your own bot token:
   ```python
   application = Application.builder().token("YOUR_BOT_TOKEN_HERE").build()
   ```

4. Run the bot:
   ```bash
   python bot.py
   ```

## 🔧 Configuration

The bot can be configured to suit different needs:

- Modify the categories in the `name_handler` function
- Add or remove attributes in the `chain_status_handler` function
- Configure the web app URL for Foursquare data exploration

## 📱 Usage

1. Start a chat with your bot on Telegram
2. Use the `/start` command to begin
3. Choose to share your location or explore the Foursquare data
4. Follow the guided process to add a new place
5. Upload photos if available
6. Confirm the submission

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit your changes (`git commit -m 'Add some amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 🔄 Workflow

The bot implements a conversation flow with 10 states:

1. LOCATION: User shares their location or accesses the web app
2. NAME: User enters the name of the place
3. CATEGORY: User selects or types a category
4. ADDRESS: User provides the full address
5. CONTACT: User enters contact information
6. HOURS: User specifies operating hours
7. CHAIN_STATUS: User indicates if the place is part of a chain
8. ATTRIBUTES: User selects applicable attributes
9. PHOTOS: User uploads photos (optional)
10. CONFIRM: User reviews and confirms the submission



---

<p align="center">Made with ❤️ for the Placemaker community</p>
