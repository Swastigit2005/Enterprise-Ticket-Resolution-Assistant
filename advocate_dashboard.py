
import requests
import streamlit as st

from config import API_URL
from logger import logger

def render():
    logout_col1, logout_col2 = st.columns([9,1])

    with logout_col2:

        if st.button("Logout"):

            st.session_state.logged_in = False
            st.session_state.role = None

            st.rerun()
    # ---------------- STATE ----------------

    if "page" not in st.session_state:
        st.session_state.page = "queue"

    if "selected_ticket" not in st.session_state:
        st.session_state.selected_ticket = None

    if "resolution_text" not in st.session_state:
        st.session_state.resolution_text = ""

    if "navigation_stack" not in st.session_state:
        st.session_state.navigation_stack = []


    # ---------------- API ----------------

    def api_get(endpoint):

        try:

            response = requests.get(
                f"{API_URL}{endpoint}",
                timeout=30
            )

            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException:

            logger.exception(
                f"GET request failed : {endpoint}"
            )

            st.error(
                "Unable to connect to backend."
            )

            raise


    def api_post(endpoint):

        try:

            response = requests.post(
                f"{API_URL}{endpoint}",
                timeout=120
            )

            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException:

            logger.exception(
                f"POST request failed : {endpoint}"
            )

            st.error(
                "Unable to communicate with backend."
            )

            raise


    def api_put(
    endpoint,
    payload=None
    ):

        try:

            response = requests.put(
                f"{API_URL}{endpoint}",
                json=payload,
                timeout=60
            )

            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException:

            logger.exception(
                f"PUT request failed : {endpoint}"
            )

            st.error(
                "Unable to update ticket."
            )

            raise


    def get_relative_time(ticket_id):
        values = [
            "3 days ago",
            "5 days ago",
            "6 days ago",
            "1 week ago",
            "2 weeks ago"
        ]
        return values[hash(ticket_id) % len(values)]


    # ---------------- STYLING ----------------

    st.markdown("""
    <style>

    /* =========================
       GLOBAL PAGE
    ========================= */

    .stApp{
        background:#f7f9fc;
        color:#1e293b;
    }
    .main .block-container{
        max-width:1450px;
        padding-top:1.5rem;
    }

    /* =========================
       HEADER
    ========================= */

    h1{
        color:#173b6c !important;
        font-weight:700 !important;
    }

    /* =========================
       RADIO BUTTONS
    ========================= */

    div[role="radiogroup"]{
        background:white;
        padding:12px;
        border-radius:12px;
        border:1px solid #dbe4f0;
    }

    /* =========================
       TICKET LIST ROWS
    ========================= */

    .ticket-row{
        background:#ffffff;
        border:1px solid #dbe4f0;
        color:#1e293b;
        border-radius:14px;
        padding:18px;
        margin-bottom:12px;
        box-shadow:0 1px 2px rgba(0,0,0,0.04);
    }

    /* =========================
       METRIC CARDS
    ========================= */

    [data-testid="stMetric"]{
        background:white;
        border:1px solid #dbe4f0;
        border-radius:14px;
        padding:20px;
        box-shadow:0 1px 2px rgba(0,0,0,0.04);
    }

    [data-testid="stMetricLabel"]{
        color:#64748b;
        font-weight:600;
    }

    [data-testid="stMetricValue"]{
        color:#0f172a;
        font-weight:700;
    }

    /* =========================
       INPUTS
    ========================= */

    .stTextInput input{
        background:white !important;
        border:1px solid #dbe4f0 !important;
    }

    /* =========================
       TEXT AREA
    ========================= */

    .stTextArea textarea{
        background:#ffffff !important;
        color:#0f172a !important;
        border:1px solid #dbe4f0 !important;
        border-radius:10px !important;
        -webkit-text-fill-color:#0f172a !important;
    }
    /* =========================
       BUTTONS
    ========================= */

    .stButton > button{
        background:#2563eb;
        color:white;
        border:none;
        border-radius:8px;
        font-weight:600;
        height:44px;
    }

    .stButton > button:hover{
        background:#1d4ed8;
        color:white;
    }

    /* =========================
       DIVIDERS
    ========================= */

    hr{
        border-color:#dbe4f0;
    }

    /* =========================
       SUBHEADERS
    ========================= */

    h2, h3{
        color:#173b6c !important;
    }

    /* =========================
       INFO BOX
    ========================= */

    [data-testid="stInfo"]{
        background:#eef5ff;
        border:1px solid #c7ddff;
        color:#173b6c;
    }

    /* =========================
       SUCCESS BOX
    ========================= */

    [data-testid="stSuccess"]{
        border-radius:10px;
    }

    /* =========================
       SOURCE TICKET CARDS
    ========================= */

    [data-testid="stVerticalBlock"] div[data-testid="stContainer"]{
        border-radius:12px;
    }
    /* =====================================
       FORCE TEXT VISIBILITY
    ===================================== */

    /* General text */
    .stMarkdown,
    .stText,
    .stCaption {
        color:#1e293b !important;
    }

    /* Disabled field visibility */
    input[disabled] {
        color:#0f172a !important;
        -webkit-text-fill-color:#0f172a !important;
        opacity:1 !important;
    }

    textarea[disabled] {
        color:#0f172a !important;
        -webkit-text-fill-color:#0f172a !important;
        opacity:1 !important;
    }

    /* Captions */
    [data-testid="stCaptionContainer"] {
        color: #64748b !important;
    }

    /* Radio labels */
    .stRadio label,
    .stRadio div {
        color: #1e293b !important;
        font-weight: 500;
    }

    /* Ticket metadata */
    small {
        color: #64748b !important;
    }

    /* Text inputs */
    .stTextInput label,
    .stTextArea label {
        color: #173b6c !important;
        font-weight: 600;
    }

    /* Disabled inputs */
    .stTextInput input:disabled,
    .stTextArea textarea:disabled {
        color: #0f172a !important;
        opacity: 1 !important;
    }

    /* Markdown text */
    .stMarkdown,
    .stMarkdown p,
    .stMarkdown span {
        color: #1e293b !important;
    }

    /* Subtitles */
    h2, h3 {
        color: #173b6c !important;
    }

    /* Radio button text */
    div[role="radiogroup"] label {
        color: #1e293b !important;
    }

    /* Ticket count text */
    .stCaption {
        color: #64748b !important;
    }
    </style>
    """, unsafe_allow_html=True)


    # ---------------- QUEUE PAGE ----------------

    def render_queue():

        st.markdown("""
        <h1 style='text-align:center;color:#173b6c;'>
        Advocate Workspace
        </h1>

        <p style='text-align:center;color:#64748b;'>
        Ticket Resolution Console
        </p>
        """, unsafe_allow_html=True)

        view = st.radio(
            "Ticket Queue",
            [
                "All Tickets",
                "Open",
                "In Progress",
                "Resolved"
            ],
            horizontal=True
        )

        try:

            if view == "All Tickets":

                tickets = api_get("/tickets")

            elif view == "Open":

                tickets = api_get("/tickets/open")

            elif view == "In Progress":

                tickets = api_get("/tickets/inprogress")

            else:

                tickets = api_get("/tickets/resolved")

        except Exception:

            logger.exception(
                "Unable to load ticket queue."
            )

            st.error(
                "Unable to load ticket queue."
            )

            return

        st.subheader(
            f"{view} Tickets"
        )

        st.caption(
            f"{len(tickets)} tickets"
        )

        for ticket in tickets:

            status = ticket.get(
                "status",
                ""
            )

            if status.lower() == "resolved":

                display_date = get_relative_time(
                    ticket["ticket_id"]
                )

            else:

                display_date = (
                    ticket.get("assigned_date")
                    or ticket.get("ticket_date")
                    or "-"
                )

            st.markdown(
                "<div class='ticket-row'>",
                unsafe_allow_html=True
            )

            c1, c2, c3 = st.columns(
                [7, 2, 1]
            )

            with c1:

                st.markdown(
                    f"### {ticket['issue_title']}"
                )

                st.markdown(
                    f"**{ticket['ticket_id']}**"
                )

                st.caption(
                    f"👤 {ticket.get('customer_name','')}   |   ✉️ {ticket.get('customer_email','')}"
                )

            with c2:

                st.caption("Status")
                st.write(status)

                st.caption("Date")
                st.write(display_date)

            with c3:

                if st.button(
                    "Open Ticket",
                    key=f"open_{ticket['ticket_id']}",
                    use_container_width=True
                ):

                    logger.info(
                        f"Ticket opened : {ticket['ticket_id']}"
                    )

                    st.session_state.navigation_stack = []

                    st.session_state.selected_ticket = (
                        ticket["ticket_id"]
                    )

                    st.session_state.resolution_text = ""

                    st.session_state.page = "ticket"

                    st.rerun()


    # ---------------- TICKET PAGE ----------------

    def render_ticket():

        ticket_id = st.session_state.selected_ticket

        try:

            ticket = api_get(
                f"/ticket/{ticket_id}"
            )

        except Exception:

            logger.exception(
                f"Unable to load ticket : {ticket_id}"
            )

            st.error(
                "Unable to load ticket."
            )

            return

        if st.button("← Back"):

            logger.info(
                f"Back button clicked from ticket {ticket_id}"
            )

            if st.session_state.navigation_stack:

                st.session_state.selected_ticket = (
                    st.session_state.navigation_stack.pop()
                )

            else:

                st.session_state.page = "queue"
                st.session_state.selected_ticket = None

            st.session_state.resolution_text = ""
            st.rerun()

        st.markdown(
        f"""
        <h1 style='color:#173b6c'>
        {ticket.get("issue_title","")}
        </h1>
        """,
        unsafe_allow_html=True
    )

        m1, m2, m3, m4 = st.columns(4)

        with m1:
            st.metric("Ticket ID", ticket.get("ticket_id", ""))

        with m2:
            st.metric("Status", ticket.get("status", ""))

        with m3:
            st.metric("Assigned To", ticket.get("assigned_to", "-"))

        with m4:
            st.metric(
                "Assigned Date",
                ticket.get("assigned_date")
                or ticket.get("ticket_date")
                or "-"
            )

        st.divider()

        st.subheader("Customer Information")

        a, b = st.columns(2)

        with a:
            st.markdown(f'''
            <div style="background:white;padding:16px;border-radius:12px;border:1px solid #dbe4f0;">
                <div style="font-size:12px;color:#64748b;">Customer Name</div>
                <div style="font-size:18px;font-weight:600;color:#0f172a;">{ticket.get("customer_name","-")}</div>
            </div>
            ''', unsafe_allow_html=True)

        with b:
            st.markdown(f'''
            <div style="background:white;padding:16px;border-radius:12px;border:1px solid #dbe4f0;">
                <div style="font-size:12px;color:#64748b;">Customer Email</div>
                <div style="font-size:18px;font-weight:600;color:#0f172a;">{ticket.get("customer_email","-")}</div>
            </div>
            ''', unsafe_allow_html=True)

        st.markdown(f'''
        <div style="background:white;padding:16px;border-radius:12px;border:1px solid #dbe4f0;margin-top:10px;">
            <div style="font-size:12px;color:#64748b;">Issue Category</div>
            <div style="font-size:18px;font-weight:600;color:#0f172a;">{ticket.get("issue_category","-")}</div>
        </div>
        ''', unsafe_allow_html=True)

        st.markdown("#### Issue Description")
        st.markdown(f'''
        <div style="background:white;padding:18px;border-radius:12px;border:1px solid #dbe4f0;color:#0f172a;">
            {ticket.get("issue_description","-")}
        </div>
        ''', unsafe_allow_html=True)

        st.divider()

        if st.button(
            "Generate Resolution",
            type="primary",
            use_container_width=True
        ):

            try:

                result = api_post(
                    f"/ticket/{ticket_id}/generate-resolution"
                )

                st.session_state.resolution_text = (
                    result.get(
                        "resolution_generated",
                        ""
                    )
                )

                logger.info(
                    f"Resolution generated : {ticket_id}"
                )

                st.rerun()

            except Exception:

                logger.exception(
                    f"Resolution generation failed : {ticket_id}"
                )

                st.error(
                    "Unable to generate resolution."
                )
        if not st.session_state.resolution_text:
            st.session_state.resolution_text = (
            ticket.get("resolution_final", "")
            or ""
            )
        st.markdown("""
    <div style="
    background:#eef5ff;
    padding:15px;
    border-radius:10px;
    margin-bottom:15px;
    border-left:5px solid #2563eb;
    ">
    <h3 style="margin:0;color:#173b6c;">
    Resolution Workspace
    </h3>
    </div>
    """, unsafe_allow_html=True)
        
        st.subheader("Resolution Workspace")

        st.session_state.resolution_text = st.text_area(
            "Resolution",
            value=st.session_state.resolution_text,
            height=320
        )

        s1, s2 = st.columns(2)

        with s1:

            if st.button(
                "Save Resolution",
                use_container_width=True
            ):

                try:

                    api_put(
                        f"/ticket/{ticket_id}/save-resolution",
                        {
                            "resolution":
                            st.session_state.resolution_text
                        }
                    )

                    logger.info(
                        f"Resolution saved : {ticket_id}"
                    )

                    st.success(
                        "Resolution saved"
                    )

                except Exception:

                    logger.exception(
                        f"Failed to save resolution : {ticket_id}"
                    )

                    st.error(
                        "Unable to save resolution."
                    )

        with s2:

            if st.button(
                "Mark Resolved",
                use_container_width=True
            ):

                try:

                    api_put(
                        f"/ticket/{ticket_id}/resolve"
                    )

                    logger.info(
                        f"Ticket resolved : {ticket_id}"
                    )

                    st.success(
                        "Ticket resolved"
                    )

                except Exception:

                    logger.exception(
                        f"Failed to resolve ticket : {ticket_id}"
                    )

                    st.error(
                        "Unable to resolve ticket."
                    )

        st.divider()

        st.markdown("""
    <div style="
    background:#eef5ff;
    padding:15px;
    border-radius:10px;
    margin-bottom:15px;
    border-left:5px solid #2563eb;
    ">
    <h3 style="margin:0;color:#173b6c;">
    Source Tickets
    </h3>
    </div>
    """, unsafe_allow_html=True)

        try:

            refs = api_get(
                f"/ticket/{ticket_id}/references"
            )

        except Exception:

            logger.exception(
                f"Unable to fetch source tickets : {ticket_id}"
            )

            refs = []

        if not refs:
            st.info("No source tickets found.")
        else:

            for idx, ref in enumerate(refs):

                with st.container(border=True):

                    st.markdown(
                        f"**{ref['source_ticket_id']}**"
                    )

                    st.write(
                        ref.get("issue_title", "")
                    )

                    st.caption(
                        ref.get("status", "")
                    )

                    if st.button(
                        "Open Source Ticket",
                        key=f"src_{idx}"
                    ):

                        st.session_state.navigation_stack.append(
                            ticket_id
                        )

                        logger.info(
                            f"Opened source ticket : {ref['source_ticket_id']}"
                        )

                        st.session_state.selected_ticket = (
                            ref["source_ticket_id"]
                        )

                        st.session_state.resolution_text = ""

                        st.rerun()


    if st.session_state.page == "queue":
        render_queue()
    else:
        render_ticket()