# Krisha Kaskelen

A student housing site for Kaskelen, Kazakhstan, built as a CSS 225 Web Development project.
People can find apartments near SDU University, see them on a map, read reviews, and send rental or purchase requests.

The frontend uses React and React Router. The backend uses Express and SQLite. The interface is available in English, Russian and Kazakh.

## Getting started

You need Node.js 22.13 or newer.

```bash
npm install
npm start
```

Then open http://localhost:3000. This one command builds the frontend and starts the server, which serves both the site and the API.

Do not open the HTML files directly or through Live Server, because the forms and data need the server.

For development with automatic reloading, run `npm run dev` and open http://localhost:5173.

To check the code:

```bash
npm test
npm run lint
```

## Features

- **Search:** filter ads by deal type, rooms, price, year built and district.
- **Map:** every ad with a known address has a pin on one 2GIS map, along with its straight-line distance to SDU.
- **Rent and buy requests:** a user sends a request with a date and a message, and the owner accepts or declines it.
- **Ad management:** owners can post, edit and delete their own ads. Deleting also removes the ad's photos, reviews, requests and chats.
- **Reviews:** users can leave one review per ad, and never on their own ad.
- **Favorites and chat:** users can save ads and message owners.
- **Moderation:** an AI model approves or rejects each ad and review, and gives a reason.

## Configuration

Copy `.env.example` to `.env`. The `.env` file must stay out of Git.

| Variable | Used for | Without it |
|---|---|---|
| `DGIS_API_KEY` | Map, address lookup and 2GIS data | The map and address lookup do not work |
| `GEMINI_API_KEY` | AI moderation through Google Gemini, which has a free tier. It takes priority over Claude | Falls back to `ANTHROPIC_API_KEY` |
| `ANTHROPIC_API_KEY` | AI moderation through Claude, which is paid | With neither key, local runs publish content unchecked and label it under "My ads". Production keeps it pending |
| `SERPAPI_KEY` | Importing public Google results with `npm run import` | The import command does not run |
| `MODERATION_MODEL` | Choosing the moderation model | Uses `gemini-flash-lite-latest` or `claude-opus-5-5` |
| `PORT` | Server port | Uses 3000 |

## Ads from krisha.kz

The site takes its ads from krisha.kz through a CSV file and a `photos` folder made by `krisha_parser.py`, a separate script that is not part of the app. Put both in the project folder, then run:

```bash
npm run import:krisha
```

The import replaces every earlier imported ad and every test ad, and keeps ads people posted on this site. Phone numbers are removed from the text, up to ten photos are kept per ad, and each ad goes through AI moderation. Ads priced per month become rentals, and the rest become sales.

The CSV file and the photos stay out of Git. The krisha.kz agreement forbids copying its listings without written permission, so get that permission before any public launch.

## Try the rental flow

Rent and buy requests work for ads that people post on this site. Imported ads link to their source page instead, because their owners are not on this site.

1. Create two accounts. With the first, post an ad.
2. With the second, press "Rent this" or "Buy this" on that ad and send the request.
3. With the first account, open "Requests" and accept it. The ad leaves the search and is marked as rented or sold.
4. Press "Return to search" on the ad page to open it again.

A request does not take payment or create a contract. It passes contact details to the owner and records the decision.

## How it works

- **2GIS key:** it stays on the server. The browser gets the map picture from `/api/map/image` and draws the pins itself.
- **Phone numbers:** the site and the server accept only 11-digit Kazakhstan numbers.
- **Moderation:** it runs in the background every 30 seconds and right after a submission. With a key set, an item with no decision stays hidden. Phone numbers are never sent to the AI provider.
- **Import:** it keeps only the title and short text from Google results and removes phone numbers. krisha.kz pages are never requested, because the site blocks automated access, so its ads come only from Google's text and their map position is approximate. The krisha.kz agreement forbids copying without written permission, so remove these ads before any public launch.
- **Old pages:** the original static site is in `legacy-static/`.

## Known limitations

- **2GIS reviews:** the demo key gets no access to review texts, so only the building rating and review count appear.
- **2GIS demo key:** it lasts one month and allows 1000 requests per service.
- **Gemini free tier:** Google may use free-tier prompts to improve its products, and the daily limit can change. When it runs out, new items wait and are retried automatically.
- **Google import:** it adds an ad only when Google's text shows a price and a usable Kaskelen address, so a run may add nothing.

## Photo credits

The hero image comes from [Unsplash](https://unsplash.com/license) and is free to use.
