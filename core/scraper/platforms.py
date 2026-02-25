"""
Platform definitions for identity resolution.
Each entry maps a platform name to its URL template and an optional
CSS selector for extracting bio/description text from the profile page.
"""

PLATFORMS = [
    # --- Developer / Tech ---
    {"name": "github", "url": "https://github.com/{username}", "bio_selector": ".p-note .js-user-profile-bio"},
    {"name": "gitlab", "url": "https://gitlab.com/{username}", "bio_selector": ".profile-user-bio"},
    {"name": "bitbucket", "url": "https://bitbucket.org/{username}", "bio_selector": None},
    {"name": "codeberg", "url": "https://codeberg.org/{username}", "bio_selector": ".user-bio"},
    {"name": "stackoverflow", "url": "https://stackoverflow.com/users/{username}", "bio_selector": ".js-about-me-content"},
    {"name": "dev.to", "url": "https://dev.to/{username}", "bio_selector": ".profile-header__bio"},
    {"name": "hashnode", "url": "https://hashnode.com/@{username}", "bio_selector": None},
    {"name": "hackernews", "url": "https://news.ycombinator.com/user?id={username}", "bio_selector": "tr:has(td:contains('about')) td:nth-child(2)"},
    {"name": "replit", "url": "https://replit.com/@{username}", "bio_selector": None},
    {"name": "npm", "url": "https://www.npmjs.com/~{username}", "bio_selector": None},
    {"name": "pypi", "url": "https://pypi.org/user/{username}", "bio_selector": None},

    # --- Social Media ---
    {"name": "twitter", "url": "https://x.com/{username}", "bio_selector": "[data-testid='UserDescription']"},
    {"name": "instagram", "url": "https://www.instagram.com/{username}", "bio_selector": "meta[property='og:description']"},
    {"name": "facebook", "url": "https://www.facebook.com/{username}", "bio_selector": None},
    {"name": "tiktok", "url": "https://www.tiktok.com/@{username}", "bio_selector": "[data-e2e='user-bio']"},
    {"name": "snapchat", "url": "https://www.snapchat.com/add/{username}", "bio_selector": None},
    {"name": "threads", "url": "https://www.threads.net/@{username}", "bio_selector": None},
    {"name": "bluesky", "url": "https://bsky.app/profile/{username}", "bio_selector": None},
    {"name": "mastodon.social", "url": "https://mastodon.social/@{username}", "bio_selector": ".account__header__content"},

    # --- Content / Video ---
    {"name": "youtube", "url": "https://www.youtube.com/@{username}", "bio_selector": "#description-container"},
    {"name": "twitch", "url": "https://www.twitch.tv/{username}", "bio_selector": "[data-a-target='profile-panel-description']"},
    {"name": "dailymotion", "url": "https://www.dailymotion.com/{username}", "bio_selector": None},
    {"name": "vimeo", "url": "https://vimeo.com/{username}", "bio_selector": ".bio_info"},
    {"name": "rumble", "url": "https://rumble.com/user/{username}", "bio_selector": None},
    {"name": "kick", "url": "https://kick.com/{username}", "bio_selector": None},

    # --- Forums / Community ---
    {"name": "reddit", "url": "https://www.reddit.com/user/{username}", "bio_selector": None},
    {"name": "quora", "url": "https://www.quora.com/profile/{username}", "bio_selector": ".profile_description"},
    {"name": "discourse", "url": "https://meta.discourse.org/u/{username}", "bio_selector": ".bio"},

    # --- Professional ---
    {"name": "indeed", "url": "https://my.indeed.com/p/{username}", "bio_selector": None},
    {"name": "angel.co", "url": "https://angel.co/u/{username}", "bio_selector": None},
    {"name": "crunchbase", "url": "https://www.crunchbase.com/person/{username}", "bio_selector": None},

    # --- Creative / Portfolio ---
    {"name": "behance", "url": "https://www.behance.net/{username}", "bio_selector": ".UserInfo-bio"},
    {"name": "dribbble", "url": "https://dribbble.com/{username}", "bio_selector": ".bio"},
    {"name": "deviantart", "url": "https://{username}.deviantart.com", "bio_selector": None},
    {"name": "artstation", "url": "https://www.artstation.com/{username}", "bio_selector": None},
    {"name": "500px", "url": "https://500px.com/p/{username}", "bio_selector": None},
    {"name": "flickr", "url": "https://www.flickr.com/people/{username}", "bio_selector": ".profile-bio"},
    {"name": "unsplash", "url": "https://unsplash.com/@{username}", "bio_selector": None},

    # --- Music ---
    {"name": "soundcloud", "url": "https://soundcloud.com/{username}", "bio_selector": ".truncatedUserDescription"},
    {"name": "spotify", "url": "https://open.spotify.com/user/{username}", "bio_selector": None},
    {"name": "bandcamp", "url": "https://{username}.bandcamp.com", "bio_selector": None},
    {"name": "last.fm", "url": "https://www.last.fm/user/{username}", "bio_selector": ".header-bio"},

    # --- Gaming ---
    {"name": "steam", "url": "https://steamcommunity.com/id/{username}", "bio_selector": ".profile_summary"},
    {"name": "xbox", "url": "https://account.xbox.com/en-us/profile?gamertag={username}", "bio_selector": None},
    {"name": "chess.com", "url": "https://www.chess.com/member/{username}", "bio_selector": None},
    {"name": "lichess", "url": "https://lichess.org/@/{username}", "bio_selector": ".profile .bio"},

    # --- Blogging / Writing ---
    {"name": "medium", "url": "https://medium.com/@{username}", "bio_selector": None},
    {"name": "substack", "url": "https://{username}.substack.com", "bio_selector": None},
    {"name": "wordpress", "url": "https://{username}.wordpress.com", "bio_selector": None},
    {"name": "tumblr", "url": "https://{username}.tumblr.com", "bio_selector": None},
    {"name": "blogger", "url": "https://{username}.blogspot.com", "bio_selector": None},

    # --- Link Aggregators ---
    {"name": "linktree", "url": "https://linktr.ee/{username}", "bio_selector": None},
    {"name": "beacons", "url": "https://beacons.ai/{username}", "bio_selector": None},
    {"name": "bio.link", "url": "https://bio.link/{username}", "bio_selector": None},
    {"name": "carrd", "url": "https://{username}.carrd.co", "bio_selector": None},

    # --- Messaging / Chat ---
    {"name": "telegram", "url": "https://t.me/{username}", "bio_selector": ".tgme_page_description"},
    {"name": "discord", "url": "https://discord.com/users/{username}", "bio_selector": None},

    # --- Finance / Crypto ---
    {"name": "cashapp", "url": "https://cash.app/${username}", "bio_selector": None},
    {"name": "patreon", "url": "https://www.patreon.com/{username}", "bio_selector": None},
    {"name": "buymeacoffee", "url": "https://www.buymeacoffee.com/{username}", "bio_selector": None},
    {"name": "ko-fi", "url": "https://ko-fi.com/{username}", "bio_selector": None},

    # --- Other ---
    {"name": "pinterest", "url": "https://www.pinterest.com/{username}", "bio_selector": None},
    {"name": "goodreads", "url": "https://www.goodreads.com/{username}", "bio_selector": None},
    {"name": "slideshare", "url": "https://www.slideshare.net/{username}", "bio_selector": None},
    {"name": "gravatar", "url": "https://gravatar.com/{username}", "bio_selector": None},
    {"name": "about.me", "url": "https://about.me/{username}", "bio_selector": ".bio"},
    {"name": "keybase", "url": "https://keybase.io/{username}", "bio_selector": None},
]
