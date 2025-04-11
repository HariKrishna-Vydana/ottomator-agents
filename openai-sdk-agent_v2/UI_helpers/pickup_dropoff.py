# /usr/bin/python

import streamlit as st
import uuid
import asyncio
from typing import Dict, Any
import streamlit as st


def render_dropoff_editor(data: Dict[str, Any]) -> Dict[str, Any]:
    """Render dropdowns for services inside a collapsible section with auto-update functionality."""
    updated_data = {"_default": {}}

    with st.expander("🚗 **Configure Dropoff Cars**", expanded=False):
        st.markdown(" Select the number of cars for each service:")

        service_items = list(data.get("_default", {}).items())
        num_columns = 3

        for i in range(0, len(service_items), num_columns):
            cols = st.columns(num_columns)
            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(service_items):
                    key, entry = service_items[idx]
                    service = entry.get("service", "Unknown Service")
                    current_value = entry.get("dropoff_cars", 0)

                    with col:
                        new_value = st.selectbox(
                            label=f"**:blue[{service}]**",  # Space avoids extra spacing from Streamlit
                            options=list(range(21)),
                            index=current_value,
                            key=f"dropdown_{key}",
                        )

                        updated_data["_default"][key] = {
                            "service": service,
                            "dropoff_cars": new_value
                        }

        total_cars = sum(entry["dropoff_cars"] for entry in updated_data["_default"].values())
        st.markdown(f"**Total Cars: {total_cars}**")

    return updated_data




