import requests
import streamlit as st

# ==========================================
# API CONFIG
# ==========================================

API_URL = (
    "http://172.20.10.6:8000/resolve"
)

# ==========================================
# PAGE CONFIG
# ==========================================

st.set_page_config(
    page_title="Enterprise Ticket Resolution",
    layout="wide"
)

# ==========================================
# TITLE
# ==========================================

st.title(
    "Enterprise Ticket Resolution Assistant"
)

st.write(
    "Enter an issue description and retrieve resolution recommendations."
)

# ==========================================
# INPUT
# ==========================================

issue_description = st.text_area(
    "Issue Description",
    height=200
)

# ==========================================
# SUBMIT
# ==========================================

if st.button(
    "Resolve Issue"
):

    if not issue_description.strip():

        st.warning(
            "Please enter an issue description."
        )

    else:

        with st.spinner(
            "Generating resolution..."
        ):

            try:

                response = requests.post(
                    API_URL,
                    json={
                        "issue":
                            issue_description
                    },
                    timeout=120
                )

                response.raise_for_status()

                result = response.json()

                resolution_steps = (
                    result.get(
                        "resolution_steps",
                        ""
                    )
                )

                source_tickets = (
                    result.get(
                        "source_tickets",
                        []
                    )
                )

                # =====================
                # NO ANSWER
                # =====================

                if not resolution_steps:

                    st.error(
                        "No sufficiently confident resolution was found."
                    )

                else:

                    st.subheader(
                        "Resolution Steps"
                    )

                    if isinstance(
                        resolution_steps,
                        list
                    ):

                        for step in resolution_steps:

                            st.write(
                                f"• {step}"
                            )

                    else:

                        st.write(
                            resolution_steps
                        )

                    st.subheader(
                        "Source Tickets"
                    )

                    for ticket in source_tickets:

                        ticket_id = (
                            ticket.get(
                                "ticket_id",
                                "Unknown"
                            )
                        )

                        similarity = (
                            ticket.get(
                                "similarity_distance"
                            )
                        )

                        if similarity is not None:

                            st.write(
                                f"{ticket_id} "
                                f"(Distance: {similarity})"
                            )

                        else:

                            st.write(
                                ticket_id
                            )

            except Exception as e:

                st.error(
                    f"Unable to generate a resolution. Please try again.API Error: {e}"
                )
                st.exception(e)