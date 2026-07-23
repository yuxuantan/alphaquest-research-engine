#!/usr/bin/env python3
"""Legacy Streamlit compatibility entrypoint.

The supported novice launcher uses ``alphaquest.studio.web``.  Keep this file
only for the explicit ``alphaquest studio start --legacy-streamlit`` fallback.
"""

from alphaquest.dashboard.studio_app import main


if __name__ == "__main__":
    main()
